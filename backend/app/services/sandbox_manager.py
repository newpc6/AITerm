import asyncio
import logging
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from app.repositories.sandbox_config import SandboxConfigRepository

logger = logging.getLogger("aiterm")


class SandboxMode:
    HOST = "host"
    SANDBOX = "sandbox"
    DOCKER = "docker"


class SandboxManager:
    def __init__(self):
        self._repo = SandboxConfigRepository()
        self._config = None
        self._paths = None
        self._dangerous = None
        self._blacklist = None
        self._whitelist = None
        self._containers: Dict[int, str] = {}

    async def reload(self):
        self._config = await self._repo.get_config()
        self._paths = await self._repo.list_paths()
        self._dangerous = await self._repo.list_dangerous_patterns()
        self._blacklist = await self._repo.list_blacklist()
        self._whitelist = await self._repo.list_whitelist()
        self._config_cached = None
        self._paths_cached = None

    async def _ensure_loaded(self):
        if self._config is None:
            await self.reload()

    @property
    async def mode(self) -> str:
        await self._ensure_loaded()
        return self._config.mode if self._config else "sandbox"

    def mode_sync(self) -> str:
        if self._config:
            return self._config.mode
        return "sandbox"

    @property
    def base_paths(self) -> List[str]:
        if self._paths:
            return [p.path for p in self._paths]
        return []

    async def _get_config(self):
        await self._ensure_loaded()
        return self._config

    async def get_mode(self) -> str:
        return await self.mode

    async def get_rules_prompt(self) -> str:
        c = await self._get_config()
        return c.rules_prompt if c else ""

    async def get_dangerous_patterns(self) -> List[Tuple[str, str, str]]:
        await self._ensure_loaded()
        return [(p.pattern, p.description, p.scope) for p in (self._dangerous or [])]

    async def get_blacklist_commands(self):
        await self._ensure_loaded()
        return self._blacklist or []

    async def get_whitelist_commands(self):
        await self._ensure_loaded()
        return self._whitelist or []

    def get_user_workspace(self, user_id: int, username: str = "") -> str:
        paths = self.base_paths
        base = paths[0] if paths else os.path.join(os.getcwd(), "workspaces")
        safe_username = username or f"user_{user_id}"
        return os.path.normpath(os.path.join(base, safe_username))

    def ensure_user_workspace(self, user_id: int, username: str = "") -> str:
        workspace = self.get_user_workspace(user_id, username)
        os.makedirs(workspace, exist_ok=True)
        for sub in ["chats", "downloads", "temp"]:
            os.makedirs(os.path.join(workspace, sub), exist_ok=True)
        logger.info(
            f"Created workspace for user {user_id} ({username}): {workspace}")
        return workspace

    def get_chat_workspace(self, user_id: int, chat_id: str, username: str = "") -> str:
        workspace = self.get_user_workspace(user_id, username)
        chat_dir = os.path.join(workspace, "chats", str(chat_id))
        os.makedirs(chat_dir, exist_ok=True)
        return chat_dir

    def validate_path(self, path: str, user_id: int = None, username: str = "") -> bool:
        if self.mode_sync() == SandboxMode.HOST:
            return True
        base = self.base_paths
        if not base:
            return True
        abs_path = os.path.abspath(path).lower()
        allowed = [os.path.abspath(bp).lower() for bp in base]
        if user_id is not None:
            allowed.append(self.get_user_workspace(user_id, username).lower())
        return any(abs_path.startswith(a) for a in allowed)

    async def validate_command(self, command: str, user_id: int = None, username: str = "") -> Tuple[bool, str]:
        mode = await self.mode
        if mode == SandboxMode.HOST:
            is_dangerous, reason = await self._check_dangerous(command)
            if is_dangerous:
                return False, f"Dangerous command in host mode: {reason}. Confirm to proceed."
            return True, ""

        if mode == SandboxMode.DOCKER:
            is_dangerous, reason = await self._check_dangerous(command)
            if is_dangerous:
                return False, f"Dangerous command: {reason}"
            return True, ""

        is_dangerous, reason = await self._check_dangerous(command)
        if is_dangerous:
            return False, f"Dangerous command: {reason}"

        if not self.base_paths:
            return True, ""
        return await self._check_paths_in_command(command, user_id, username)

    async def _check_dangerous(self, command: str) -> Tuple[bool, str]:
        patterns = await self.get_dangerous_patterns()
        cmd_lower = command.lower()
        for pat, desc, scope in patterns:
            if pat.lower() in cmd_lower:
                return True, desc
        return False, ""

    async def _check_paths_in_command(self, command: str, user_id: int = None, username: str = "") -> Tuple[bool, str]:
        path_re = re.compile(r'["\']([^"\']+)["\']|\s([^\s]+)')
        workspace = self.get_user_workspace(
            user_id, username) if user_id is not None else None
        for match in path_re.finditer(command):
            path = match.group(1) or match.group(2)
            if not path or len(path) < 2:
                continue
            if os.path.isabs(path) or "/" in path or "\\" in path:
                if not self.validate_path(path, user_id, username=username):
                    info = f"Allowed: {', '.join(self.base_paths)}"
                    if workspace:
                        info += f", workspace: {workspace}"
                    return False, f"Path '{path}' outside sandbox. {info}"
        return True, ""

    async def require_confirm(self) -> bool:
        c = await self._get_config()
        return c.require_confirm if c else True

    def _container_name(self, user_id: int) -> str:
        return f"aiterm-user-{user_id}"

    def is_docker_available(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    async def ensure_container(self, user_id: int, username: str = "") -> bool:
        mode = await self.mode
        if mode != SandboxMode.DOCKER:
            return True
        if not self.is_docker_available():
            logger.error("Docker mode enabled but docker is not available")
            return False

        c = await self._get_config()
        name = self._container_name(user_id)

        result = subprocess.run(
            ["docker", "inspect", name], capture_output=True, text=True)
        if result.returncode == 0:
            self._containers[user_id] = name
            return True

        workspace = self.get_user_workspace(user_id, username)
        os.makedirs(workspace, exist_ok=True)

        cmd = [
            "docker", "run", "-d",
            "--name", name,
            "--network", c.docker_network,
            "--memory", c.docker_memory,
            "--cpus", str(c.docker_cpu),
            "--restart", "unless-stopped",
            "-v", f"{workspace}:/workspace:rw",
            "-w", "/workspace",
            c.docker_image,
            "tail", "-f", "/dev/null",
        ]
        logger.info(f"Creating container: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"Failed to create container {name}: {result.stderr}")
            return False

        self._containers[user_id] = name
        logger.info(f"Created container {name} for user {user_id}")
        return True

    async def docker_exec(self, user_id: int, command: str, chat_id: str = None, timeout: int = None) -> Tuple[int, str, str]:
        c = await self._get_config()
        if not timeout:
            timeout = c.docker_timeout if c else 300

        name = self._container_name(user_id)
        workdir = f"/workspace/chats/{chat_id}" if chat_id else "/workspace"
        wrapped = f'cd {workdir} 2>/dev/null || mkdir -p {workdir} && cd {workdir}; export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"; {command}'

        exec_cmd = ["docker", "exec", "-w",
                    "/workspace", name, "bash", "-lc", wrapped]
        logger.info(f"Docker exec [{name}]: {command[:100]}")

        proc = await asyncio.create_subprocess_exec(*exec_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_bytes.decode(
                'utf-8', errors='replace') if stdout_bytes else ""
            stderr = stderr_bytes.decode(
                'utf-8', errors='replace') if stderr_bytes else ""
            return proc.returncode or 0, stdout, stderr
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return -1, "", f"Command timed out after {timeout}s"

    async def execute_command(self, command: str, user_id: int = None, chat_id: str = None, timeout: int = None) -> Tuple[int, str, str]:
        mode = await self.mode
        if mode == SandboxMode.DOCKER and user_id is not None:
            if not await self.ensure_container(user_id):
                raise RuntimeError("Docker container not available")
            return await self.docker_exec(user_id, command, chat_id, timeout)

        return await self._host_exec(command, timeout or 300)

    async def _host_exec(self, command: str, timeout: int) -> Tuple[int, str, str]:
        import platform
        if platform.system() == "Windows":
            wrapped = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
            cmd = ["powershell.exe", "-NoProfile",
                   "-ExecutionPolicy", "Bypass", "-Command", wrapped]
        else:
            wrapped = f'export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"; {command}'
            cmd = ["/bin/bash", "-lc", wrapped]

        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_bytes.decode(
                'utf-8', errors='replace') if stdout_bytes else ""
            stderr = stderr_bytes.decode(
                'utf-8', errors='replace') if stderr_bytes else ""
            return proc.returncode or 0, stdout, stderr
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return -1, "", f"Command timed out after {timeout}s"

    def cleanup_user_workspace(self, user_id: int, username: str = "") -> bool:
        try:
            mode = self.mode_sync()
            if mode == SandboxMode.DOCKER:
                name = self._container_name(user_id)
                subprocess.run(["docker", "rm", "-f", name],
                               capture_output=True, text=True, timeout=10)
                self._containers.pop(user_id, None)
                logger.info(f"Removed container {name} for user {user_id}")

            workspace = self.get_user_workspace(user_id, username)
            if os.path.exists(workspace):
                shutil.rmtree(workspace)
                logger.info(f"Cleaned up workspace for user {user_id}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to cleanup workspace for user {user_id}: {e}")
            return False

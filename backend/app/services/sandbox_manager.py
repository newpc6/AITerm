import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("aiterm")


class SandboxMode:
    HOST = "host"
    SANDBOX = "sandbox"
    DOCKER = "docker"


DANGEROUS_PATTERNS = [
    ("rm -rf /", "system-wide deletion"),
    ("del /s /q C:\\", "system-wide deletion"),
    ("format ", "disk formatting"),
    ("mkfs.", "filesystem creation"),
    ("dd if=", "raw disk write"),
    ("> /dev/sd", "raw disk write"),
    ("shutdown", "system shutdown"),
    ("reboot", "system reboot"),
    ("init 0", "system shutdown"),
    ("halt", "system halt"),
    ("poweroff", "power off"),
    ("chmod 777 /", "permissive root permissions"),
    (":(){ :|:& };:", "fork bomb"),
    ("wget -O /etc/", "system config overwrite"),
    ("curl.*> /etc/", "system config overwrite"),
]


class SandboxManager:
    def __init__(self, settings):
        self.settings = settings
        self._containers: Dict[int, str] = {}

    @property
    def mode(self) -> str:
        return getattr(self.settings, 'sandbox_mode', 'sandbox') or 'sandbox'

    @property
    def base_paths(self) -> List[str]:
        return getattr(self.settings, 'sandbox_paths', []) or []

    @property
    def docker_image(self) -> str:
        return getattr(self.settings, 'docker_image', 'python:3.11-slim') or 'python:3.11-slim'

    @property
    def docker_network(self) -> str:
        return getattr(self.settings, 'docker_network', 'none') or 'none'

    @property
    def docker_memory_limit(self) -> str:
        return getattr(self.settings, 'docker_memory_limit', '512m') or '512m'

    @property
    def docker_cpu_limit(self) -> float:
        val = getattr(self.settings, 'docker_cpu_limit', 1.0)
        return float(val) if val else 1.0

    @property
    def docker_timeout_seconds(self) -> int:
        val = getattr(self.settings, 'docker_timeout_seconds', 300)
        return int(val) if val else 300

    def is_docker_available(self) -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_user_workspace(self, user_id: int, username: str = "") -> str:
        base = self.base_paths[0] if self.base_paths else os.path.join(
            os.getcwd(), "workspaces")
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
        if self.mode == SandboxMode.HOST:
            return True
        if not self.base_paths:
            return True

        abs_path = os.path.abspath(path).lower()
        allowed = [os.path.abspath(bp).lower() for bp in self.base_paths]
        if user_id is not None:
            allowed.append(self.get_user_workspace(user_id, username).lower())

        return any(abs_path.startswith(a) for a in allowed)

    def validate_command(self, command: str, user_id: int = None, username: str = "") -> Tuple[bool, str]:
        if self.mode == SandboxMode.HOST:
            is_dangerous, reason = self._check_dangerous_command(command)
            if is_dangerous:
                return False, f"Dangerous command in host mode: {reason}. Confirm to proceed."
            return True, ""

        if self.mode == SandboxMode.DOCKER:
            is_dangerous, reason = self._check_dangerous_command(command)
            if is_dangerous:
                return False, f"Dangerous command: {reason}"
            return True, ""

        if not self.base_paths:
            return True, ""
        return self._check_paths_in_command(command, user_id, username)

    def _check_dangerous_command(self, command: str) -> Tuple[bool, str]:
        cmd_lower = command.lower()
        for pattern, desc in DANGEROUS_PATTERNS:
            if pattern.lower() in cmd_lower:
                return True, desc
        return False, ""

    def _check_paths_in_command(self, command: str, user_id: int = None, username: str = "") -> Tuple[bool, str]:
        path_pattern = re.compile(r'["\']([^"\']+)["\']|\s([^\s]+)')
        workspace = self.get_user_workspace(
            user_id, username) if user_id is not None else None

        for match in path_pattern.finditer(command):
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

    def _container_name(self, user_id: int) -> str:
        return f"aiterm-user-{user_id}"

    async def ensure_container(self, user_id: int, username: str = "") -> bool:
        if self.mode != SandboxMode.DOCKER:
            return True
        if not self.is_docker_available():
            logger.error("Docker mode enabled but docker is not available")
            return False

        name = self._container_name(user_id)
        workspace = self.get_user_workspace(user_id, username)

        result = subprocess.run(
            ["docker", "inspect", name], capture_output=True, text=True
        )
        if result.returncode == 0:
            self._containers[user_id] = name
            return True

        os.makedirs(workspace, exist_ok=True)

        cmd = [
            "docker", "run", "-d",
            "--name", name,
            "--network", self.docker_network,
            "--memory", self.docker_memory_limit,
            "--cpus", str(self.docker_cpu_limit),
            "--restart", "unless-stopped",
            "-v", f"{workspace}:/workspace:rw",
            "-w", "/workspace",
            self.docker_image,
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

    async def docker_exec(
        self, user_id: int, command: str, chat_id: str = None, timeout: int = None
    ) -> Tuple[int, str, str]:
        if not timeout:
            timeout = self.docker_timeout_seconds

        name = self._container_name(user_id)
        workdir = f"/workspace/chats/{chat_id}" if chat_id else "/workspace"
        wrapped = f'cd {workdir} 2>/dev/null || mkdir -p {workdir} && cd {workdir}; export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"; {command}'

        exec_cmd = ["docker", "exec", "-w",
                    "/workspace", name, "bash", "-lc", wrapped]
        logger.info(f"Docker exec [{name}]: {command[:100]}")

        proc = await asyncio.create_subprocess_exec(
            *exec_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
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

    async def execute_command(
        self, command: str, user_id: int = None, chat_id: str = None, timeout: int = None
    ) -> Tuple[int, str, str]:
        if self.mode == SandboxMode.DOCKER and user_id is not None:
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

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
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
            if self.mode == SandboxMode.DOCKER:
                name = self._container_name(user_id)
                subprocess.run(
                    ["docker", "rm", "-f", name],
                    capture_output=True, text=True, timeout=10
                )
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

import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("aiterm")


class WorkspaceService:
    def __init__(self, settings):
        self.settings = settings

    @property
    def sandbox_mode(self) -> str:
        return getattr(self.settings, 'sandbox_mode', 'sandbox')

    @property
    def base_paths(self) -> List[str]:
        return getattr(self.settings, 'sandbox_paths', []) or []

    def get_user_workspace(self, user_id: int, username: str = "") -> str:
        base = self.base_paths[0] if self.base_paths else os.path.join(os.getcwd(), "workspaces")
        safe_username = username or f"user_{user_id}"
        workspace_path = os.path.join(base, safe_username)
        return os.path.normpath(workspace_path)

    def ensure_user_workspace(self, user_id: int, username: str = "") -> str:
        workspace = self.get_user_workspace(user_id, username)
        os.makedirs(workspace, exist_ok=True)

        chat_dir = os.path.join(workspace, "chats")
        downloads_dir = os.path.join(workspace, "downloads")
        temp_dir = os.path.join(workspace, "temp")

        for dir_path in [chat_dir, downloads_dir, temp_dir]:
            os.makedirs(dir_path, exist_ok=True)

        logger.info(f"Created workspace for user {user_id} ({username}): {workspace}")
        return workspace

    def get_chat_workspace(self, user_id: int, chat_id: str, username: str = "") -> str:
        workspace = self.get_user_workspace(user_id, username)
        chat_dir = os.path.join(workspace, "chats", str(chat_id))
        os.makedirs(chat_dir, exist_ok=True)
        return chat_dir

    def validate_path(self, path: str, user_id: int = None, chat_id: str = None, username: str = "") -> bool:
        if self.sandbox_mode == "host":
            return True

        if not self.base_paths:
            return True

        abs_path = os.path.abspath(path).lower()

        allowed_paths = []
        for base_path in self.base_paths:
            allowed_paths.append(os.path.abspath(base_path).lower())

        if user_id is not None:
            workspace = self.get_user_workspace(user_id, username).lower()
            allowed_paths.append(workspace)

        for allowed in allowed_paths:
            if abs_path.startswith(allowed):
                return True

        return False

    def validate_command(self, command: str, user_id: int = None, username: str = "") -> tuple:
        if self.sandbox_mode == "host":
            is_dangerous, pattern = self._check_dangerous_command(command)
            if is_dangerous:
                return False, f"Dangerous command detected in host mode: {pattern}. Use sandbox mode or confirm."
            return True, ""

        if not self.base_paths:
            return True, ""

        return self._check_paths_in_command(command, user_id, username)

    def _check_dangerous_command(self, command: str) -> tuple:
        dangerous_patterns = [
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

        cmd_lower = command.lower()
        for pattern_str, description in dangerous_patterns:
            if pattern_str.lower() in cmd_lower:
                return True, description

        return False, ""

    def _check_paths_in_command(self, command: str, user_id: int = None, username: str = "") -> tuple:
        import re

        path_pattern = re.compile(r'["\']([^"\']+)["\']|\s([^\s]+)')

        workspace = None
        if user_id is not None:
            workspace = self.get_user_workspace(user_id, username)

        for match in path_pattern.finditer(command):
            path = match.group(1) or match.group(2)
            if not path or len(path) < 2:
                continue

            if os.path.isabs(path) or "/" in path or "\\" in path:
                if not self.validate_path(path, user_id, username=username):
                    allowed_info = f"Allowed paths: {', '.join(self.base_paths)}"
                    if workspace:
                        allowed_info += f", user workspace: {workspace}"
                    return False, f"Path '{path}' is outside sandbox. {allowed_info}"

        return True, ""

    def is_sandbox_enabled(self) -> bool:
        return self.sandbox_mode == "sandbox" and bool(self.base_paths)

    def cleanup_user_workspace(self, user_id: int, username: str = "") -> bool:
        try:
            workspace = self.get_user_workspace(user_id, username)
            if os.path.exists(workspace):
                shutil.rmtree(workspace)
                logger.info(f"Cleaned up workspace for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup workspace for user {user_id}: {e}")
            return False

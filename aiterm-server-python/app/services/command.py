import asyncio
import platform
import subprocess
import sys
import threading
import traceback
import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.models import Node, NodeCreate, NodeStatus

logger = logging.getLogger("aiterm")

_executor = ThreadPoolExecutor(max_workers=4)

_running_processes: Dict[str, subprocess.Popen] = {}
_cancelled_tasks: set = set()
_process_threads: Dict[str, threading.Thread] = {}


def register_process(task_id: str, proc: subprocess.Popen):
    _running_processes[task_id] = proc
    logger.info(f"Registered process for task {task_id}, PID: {proc.pid}")


def unregister_process(task_id: str):
    if task_id in _running_processes:
        del _running_processes[task_id]
        logger.info(f"Unregistered process for task {task_id}")
    if task_id in _process_threads:
        del _process_threads[task_id]


def kill_process(task_id: str) -> bool:
    _cancelled_tasks.add(task_id)
    
    if task_id in _running_processes:
        proc = _running_processes[task_id]
        try:
            proc.kill()
            logger.info(f"Killed process for task {task_id}, PID: {proc.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to kill process for task {task_id}: {e}")
    return False


class CommandResult:
    def __init__(
        self,
        lines: List[Tuple[str, str]],
        exit_code: int = 0,
        timed_out: bool = False,
        cancelled: bool = False,
        error: Optional[Exception] = None
    ):
        self.lines = lines
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.cancelled = cancelled
        self.error = error


COMMAND_TIMEOUT = 300


def _run_sync_command(command: str, timeout: int, task_id: Optional[str] = None) -> CommandResult:
    proc = None
    stdout_lines: List[str] = []
    stderr_lines: List[str] = []
    cancelled = False
    
    try:
        if platform.system() == "Windows":
            wrapped_command = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
            proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", wrapped_command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
        else:
            proc = subprocess.Popen(
                ["sh", "-lc", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

        if task_id and proc:
            register_process(task_id, proc)

        def read_output(stream, output_list):
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        output_list.append(line)
            except:
                pass

        stdout_thread = threading.Thread(target=read_output, args=(proc.stdout, stdout_lines))
        stderr_thread = threading.Thread(target=read_output, args=(proc.stderr, stderr_lines))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        start_time = datetime.now()
        check_interval = 0.5
        
        while proc.poll() is None:
            if task_id and task_id in _cancelled_tasks:
                logger.info(f"Task {task_id} cancelled, terminating process")
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except:
                        pass
                cancelled = True
                _cancelled_tasks.discard(task_id)
                break
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                logger.info(f"Command timeout after {timeout} seconds")
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except:
                        pass
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                lines = []
                if stdout_lines:
                    lines.append(("stdout", "".join(stdout_lines).strip()))
                if stderr_lines:
                    lines.append(("stderr", "".join(stderr_lines).strip()))
                if not lines:
                    lines.append(("stderr", f"命令执行超时，已在 {timeout} 秒后终止。"))
                
                if task_id:
                    unregister_process(task_id)
                return CommandResult(
                    lines=lines,
                    exit_code=-1,
                    timed_out=True,
                    error=TimeoutError()
                )
            
            threading.Event().wait(check_interval)

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        lines = []
        if stdout_lines:
            output_text = "".join(stdout_lines).strip()
            if output_text:
                lines.append(("stdout", output_text))

        if stderr_lines:
            error_text = "".join(stderr_lines).strip()
            if error_text:
                lines.append(("stderr", error_text))

        if cancelled:
            if not lines:
                lines.append(("stdout", "进程已被用户终止。"))
            if task_id:
                unregister_process(task_id)
            return CommandResult(
                lines=lines,
                exit_code=-1,
                cancelled=True
            )

        if not lines and proc.returncode == 0:
            lines = [("stdout", "命令执行成功，无输出。")]

        if not lines and proc.returncode != 0:
            lines = [("stderr", f"命令执行失败，退出码: {proc.returncode}")]

        if task_id:
            unregister_process(task_id)
        return CommandResult(
            lines=lines,
            exit_code=proc.returncode or 0
        )

    except FileNotFoundError as e:
        if task_id:
            unregister_process(task_id)
        return CommandResult(
            lines=[("stderr", f"找不到命令解释器: {e.filename or 'powershell.exe'}")],
            exit_code=127,
            error=e
        )
    except PermissionError as e:
        if task_id:
            unregister_process(task_id)
        return CommandResult(
            lines=[("stderr", f"权限不足: {str(e)}")],
            exit_code=126,
            error=e
        )
    except Exception as e:
        if task_id:
            unregister_process(task_id)
        error_msg = str(e) or type(e).__name__
        return CommandResult(
            lines=[("stderr", f"命令执行失败: {error_msg}")],
            exit_code=1,
            error=e
        )


async def execute_command(command: str, timeout: int = COMMAND_TIMEOUT, task_id: Optional[str] = None) -> CommandResult:
    logger.info(f"execute_command called: command='{command}', timeout={timeout}, task_id={task_id}")
    
    if not command or not command.strip():
        return CommandResult(
            lines=[("stderr", "未生成可执行命令。")],
            exit_code=1,
            error=Exception("Empty command")
        )

    if task_id:
        _cancelled_tasks.discard(task_id)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _run_sync_command, command, timeout, task_id)
    return result


def cancel_command(task_id: str) -> bool:
    return kill_process(task_id)


def detect_platform(node: Optional[Node] = None) -> str:
    if node is None or node.id == "1" or node.host in ["127.0.0.1", "localhost", "::1"]:
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
    return ""


def describe_node(node: Node) -> str:
    if node.id == "1" or node.host in ["127.0.0.1", "localhost", "::1"]:
        system = detect_platform(node)
        if system:
            return f"本地节点 ({system})"
    return f"{node.name} ({node.host}:{node.port})"

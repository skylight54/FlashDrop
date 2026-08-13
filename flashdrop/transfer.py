from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import List, Optional

from PySide6.QtCore import QThread, Signal


CODE_PATTERN = re.compile(r"Wormhole code is:\s*(\S+)")
RECEIVED_PATTERN = re.compile(r"Received file written to:\s*(.+?)\s*$")
# tqdm 进度行形如 " 60%|████    | 120M/200M [00:00<00:00, 1.17GB/s]"
PROGRESS_PATTERN = re.compile(r"(\d+)%")
# tqdm 用 \r 原地刷新进度，因此需要同时按 \r\n / \r / \n 切分
_LINE_SEP_RE = re.compile(r"\r\n|\r|\n")


def _creation_flags() -> int:
    if os.name == "nt":
        return subprocess.CREATE_NO_WINDOW
    return 0


def wormhole_command() -> List[str]:
    """返回用来启动 magic-wormhole CLI 的基础命令。"""
    if getattr(sys, "frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable), "wormhole_cli.exe")
        if os.path.exists(exe):
            return [exe]
        raise RuntimeError("找不到随应用打包的 wormhole_cli.exe")

    command = shutil.which("wormhole")
    if command:
        return [command]

    scripts_dir = os.path.join(sys.prefix, "Scripts")
    candidate = os.path.join(scripts_dir, "wormhole.exe")
    if os.path.exists(candidate):
        return [candidate]

    raise RuntimeError("找不到 wormhole 命令，请先安装 magic-wormhole")


def _parse_progress_detail(line: str) -> str:
    """从 tqdm 进度行提取 "120M/200M · 1.17GB/s" 这类可读文本。"""
    parts = line.split("|", 2)
    if len(parts) < 3:
        return ""
    rest = parts[2].strip()
    fraction = rest.split(" [", 1)[0].strip()
    if not fraction:
        return ""
    rate_match = re.search(r",\s*([^\]]+)", rest)
    rate = rate_match.group(1).strip() if rate_match else ""
    if rate and rate not in ("?", "?B/s", "0.00B/s"):
        return f"{fraction} · {rate}"
    return fraction


class TransferWorker(QThread):
    """在后台线程运行 wormhole CLI，并通过信号回传进度。"""

    code_ready = Signal(str)
    status = Signal(str)
    progress = Signal(int, str)  # 百分比, 可读详情（如 "120M/200M · 1.17GB/s"）
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, args: List[str], cwd: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._args = list(args)
        self._cwd = cwd
        self._proc: Optional[subprocess.Popen] = None
        self._cancelled = False
        self._stderr_tail: List[str] = []
        self._received_path = ""

    def cancel(self) -> None:
        self._cancelled = True
        self._kill_process_tree()

    def _kill_process_tree(self) -> None:
        """终止整个进程树。PyInstaller onefile 会派生子进程，只杀父进程会残留孤儿进程。"""
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=_creation_flags(),
                )
            except Exception:
                pass
        try:
            proc.terminate()
        except Exception:
            pass

    def run(self) -> None:
        try:
            base = wormhole_command()
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        cmd = base + self._args
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self._cwd,
                creationflags=_creation_flags(),
            )
        except Exception as exc:
            self.failed.emit(f"无法启动传输进程：{exc}")
            return

        for line in self._iter_stderr_lines():
            line = line.strip()
            if not line:
                continue

            code_match = CODE_PATTERN.search(line)
            if code_match:
                self.code_ready.emit(code_match.group(1))

            received_match = RECEIVED_PATTERN.search(line)
            if received_match:
                self._received_path = received_match.group(1).strip()

            progress_match = PROGRESS_PATTERN.search(line)
            if progress_match:
                self.progress.emit(int(progress_match.group(1)), _parse_progress_detail(line))
                continue

            self._stderr_tail.append(line)
            if len(self._stderr_tail) > 200:
                self._stderr_tail = self._stderr_tail[-200:]
            self.status.emit(line)

        retcode = self._proc.wait()

        stdout = self._proc.stdout
        if stdout is not None:
            try:
                stdout.read()
            except Exception:
                pass

        if self._cancelled:
            self.cancelled.emit()
        elif retcode == 0:
            self.succeeded.emit(self._received_path)
        else:
            self.failed.emit(self._error_text() or f"传输失败（退出码 {retcode}）")

    def _iter_stderr_lines(self):
        stream = self._proc.stderr
        pending = ""
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            pending += chunk
            while True:
                match = _LINE_SEP_RE.search(pending)
                if match is None:
                    break
                yield pending[: match.start()]
                pending = pending[match.end():]
        if pending:
            yield pending

    def _error_text(self) -> str:
        lines = [line for line in self._stderr_tail if line.strip()]
        return "\n".join(lines[-6:])

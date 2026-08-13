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


class TransferWorker(QThread):
    """在后台线程运行 wormhole CLI，并通过信号回传进度。"""

    code_ready = Signal(str)
    status = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

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
        proc = self._proc
        if proc is not None and proc.poll() is None:
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
                bufsize=1,
                cwd=self._cwd,
                creationflags=_creation_flags(),
            )
        except Exception as exc:
            self.failed.emit(f"无法启动传输进程：{exc}")
            return

        stderr = self._proc.stderr
        assert stderr is not None
        for raw in stderr:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            self._stderr_tail.append(line)
            if len(self._stderr_tail) > 200:
                self._stderr_tail = self._stderr_tail[-200:]

            code_match = CODE_PATTERN.search(line)
            if code_match:
                self.code_ready.emit(code_match.group(1))

            received_match = RECEIVED_PATTERN.search(line)
            if received_match:
                self._received_path = received_match.group(1).strip()

            self.status.emit(line)

        retcode = self._proc.wait()

        stdout = self._proc.stdout
        if stdout is not None:
            try:
                stdout.read()
            except Exception:
                pass

        if self._cancelled:
            self.failed.emit("已取消")
        elif retcode == 0:
            self.succeeded.emit(self._received_path)
        else:
            self.failed.emit(self._error_text() or f"传输失败（退出码 {retcode}）")

    def _error_text(self) -> str:
        lines = [line for line in self._stderr_tail if line.strip()]
        return "\n".join(lines[-6:])

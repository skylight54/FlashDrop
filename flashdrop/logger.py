"""应用日志：把传输过程的关键信息写到文件，方便事后排查（如“为什么传得慢”）。

日志文件位置：
- Windows：%LOCALAPPDATA%/FlashDrop/logs/flashdrop.log
- 其它平台：~/.flashdrop/logs/flashdrop.log

采用轮转策略：单个文件超过 1MB 时滚动，最多保留 5 个备份。
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER_NAME = "flashdrop"

_logger: logging.Logger | None = None
_log_file: str = ""


def log_dir() -> Path:
    """返回日志目录（不保证已创建）。"""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "FlashDrop" / "logs"
    return Path.home() / ".flashdrop" / "logs"


def setup_logging() -> logging.Logger:
    """初始化应用日志，可重复调用（幂等）。"""
    global _logger, _log_file
    if _logger is not None:
        return _logger

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S"
    )

    directory = log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        _log_file = str(directory / "flashdrop.log")
        handler = RotatingFileHandler(
            _log_file, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except OSError:
        _log_file = ""

    # 开发环境（未打包）额外输出到控制台，便于调试
    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    return _logger or setup_logging()


def log_file() -> str:
    """当前日志文件路径（可能为空字符串，表示未成功创建）。"""
    return _log_file


def log_directory() -> str:
    return str(log_dir())

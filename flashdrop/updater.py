from __future__ import annotations

import json
import re
import urllib.request
from typing import Tuple

from PySide6.QtCore import QThread, Signal

from . import __version__


REPO = "skylight54/FlashDrop"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def _parse_version(tag: str) -> Tuple[int, int, int]:
    """把 v0.2.1 这类标签解析成可比较的三元组。"""
    cleaned = tag.lstrip("vV")
    parts = re.split(r"[.\-]", cleaned)[:3]
    nums = []
    for part in parts:
        match = re.match(r"\d+", part)
        nums.append(int(match.group()) if match else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


class UpdateChecker(QThread):
    """在后台查询 GitHub 最新发布版本。"""

    result_ready = Signal(bool, str, str)

    def run(self) -> None:
        try:
            request = urllib.request.Request(
                API_URL,
                headers={
                    "User-Agent": "FlashDrop-Updater",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            latest = str(data.get("tag_name", "")).strip()
            url = str(data.get("html_url", "")).strip()
            has_update = bool(latest) and _parse_version(latest) > _parse_version(__version__)
            self.result_ready.emit(has_update, latest, url)
        except Exception:
            self.result_ready.emit(False, "", "")

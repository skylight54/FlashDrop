"""从 Asset/Idle.webp 生成多尺寸 Windows 图标 Asset/icon.ico。

在项目根目录执行：

    python tools/make_icon.py
"""

from __future__ import annotations

import os
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def _build_ico(source: QImage, sizes: tuple[int, ...]) -> bytes:
    entries: list[bytes] = []
    images: list[bytes] = []
    offset = 6 + 16 * len(sizes)
    for size in sizes:
        image = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        png = _png_bytes(image)
        # ICO 目录项：宽度/高度为 0 表示 256，PNG 条目用 32bpp。
        dim = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset))
        images.append(png)
        offset += len(png)

    header = struct.pack("<HHH", 0, 1, len(sizes))
    return header + b"".join(entries) + b"".join(images)


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_path = os.path.join(root, "Asset", "Idle.webp")
    target_path = os.path.join(root, "Asset", "icon.ico")

    source = QImage(source_path)
    if source.isNull():
        print(f"无法读取 {source_path}")
        return 1

    ico = _build_ico(source, SIZES)
    with open(target_path, "wb") as fh:
        fh.write(ico)
    print(f"已生成 {target_path}（{len(ico)} 字节，{len(SIZES)} 种尺寸）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

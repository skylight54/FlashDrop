"""冒烟测试：离屏启动界面，验证状态图片与菜单可用。

在项目根目录执行：

    python -m tests.smoke_test
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenu

from flashdrop import __version__
from flashdrop.app import MainWindow, asset_dir, state_pixmap


def main() -> int:
    print("version", __version__)
    print("asset_dir", asset_dir())

    app = QApplication([])

    for state in ("idle", "wait", "success", "fail"):
        pixmap = state_pixmap(state)
        print(state, "loaded" if pixmap is not None else "MISSING")

    window = MainWindow()
    print("window ok")
    print("send idle", window.send_tab.state_image.pixmap() is not None)
    print("recv idle", window.receive_tab.state_image.pixmap() is not None)

    menus = window.menuBar().findChildren(QMenu)
    print("menus", [(m.title(), [a.text() for a in m.actions()]) for m in menus])

    window.send_tab.state_image.set_state("success")
    window.receive_tab.state_image.set_state("fail")
    print("send success", window.send_tab.state_image.pixmap() is not None)
    print("recv fail", window.receive_tab.state_image.pixmap() is not None)

    window.close()
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

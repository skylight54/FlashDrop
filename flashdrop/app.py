from __future__ import annotations

import collections
import os
import sys
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__, logger
from .transfer import TransferWorker
from .updater import UpdateChecker


APP_NAME = "即传 FlashDrop"


STATE_IMAGES = {
    "idle": "Idle.webp",
    "wait": "Waiting.jpg",
    "success": "Success.jpg",
    "fail": "Fail.jpg",
}


def asset_dir() -> str:
    """返回随应用打包或位于项目根目录的 Asset 图片目录。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "Asset")


_pixmap_cache: dict = {}


def state_pixmap(state: str, size: int = 160):
    key = (state, size)
    cached = _pixmap_cache.get(key)
    if cached is not None:
        return cached
    path = os.path.join(asset_dir(), STATE_IMAGES[state])
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    _pixmap_cache[key] = scaled
    return scaled


STYLESHEET = """
QMainWindow, QWidget {
    background: #FAF3E8;
    color: #4A3420;
    font-size: 14px;
}
QLabel#tabTitle {
    font-size: 22px;
    font-weight: 700;
    color: #3E2B1A;
}
QLabel#subtitle {
    color: #8A7358;
    font-size: 13px;
}
QLabel#codeValue {
    font-family: Consolas, "Courier New", monospace;
    font-size: 26px;
    font-weight: 700;
    color: #C96A16;
    background: #FDEDD9;
    border: 1px solid #F0C896;
    border-radius: 8px;
    padding: 16px;
}
QFrame#transferPanel {
    background: #FFFDF9;
    border: 1px solid #EAD9BE;
    border-radius: 10px;
}
QListWidget, QLineEdit, QTextEdit, QPlainTextEdit {
    background: #FFFDF9;
    border: 1px solid #EAD9BE;
    border-radius: 8px;
    padding: 6px;
    selection-background-color: #F6D9B4;
    selection-color: #4A3420;
}
QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background: #F6D9B4;
    color: #4A3420;
}
QPushButton {
    background: #FFFDF9;
    border: 1px solid #EAD9BE;
    border-radius: 8px;
    padding: 8px 14px;
    color: #5C4126;
}
QPushButton:hover {
    background: #F6EBD8;
    border-color: #E0C79E;
}
QPushButton:pressed {
    background: #F0DFC2;
}
QPushButton:disabled {
    color: #C2AE93;
    background: #F5EDE0;
    border-color: #EAD9BE;
}
QPushButton#primary {
    background: #E0822D;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #C96A16;
}
QPushButton#primary:pressed {
    background: #B25E12;
}
QPushButton#primary:disabled {
    background: #E8C29A;
    color: #FFF9F0;
}
QProgressBar {
    border: none;
    background: #EFE3D0;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: #4A3420;
}
QProgressBar::chunk {
    background: #E0822D;
    border-radius: 5px;
}
QTabWidget::pane {
    border: none;
}
QTabBar::tab {
    background: transparent;
    padding: 10px 22px;
    color: #8A7358;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover {
    color: #4A3420;
}
QTabBar::tab:selected {
    color: #C96A16;
    border-bottom: 2px solid #E0822D;
    font-weight: 600;
}
"""


def default_download_dir() -> str:
    return str(Path.home() / "Downloads")


def app_icon() -> QIcon:
    """返回应用图标（由 Asset/Idle.webp 生成）。"""
    path = os.path.join(asset_dir(), "icon.ico")
    icon = QIcon(path)
    return icon if not icon.isNull() else QIcon()


def _std_icon(name: str) -> QIcon:
    """返回 QStyle 标准图标（如 SP_DirIcon），缺失时返回空图标。"""
    standard = getattr(QStyle.StandardPixmap, name, None)
    if standard is None:
        return QIcon()
    return QApplication.style().standardIcon(standard)


class LogViewerDialog(QDialog):
    """查看运行日志的对话框，自动刷新最近内容。"""

    _TAIL_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("运行日志")
        self.resize(760, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.path_label = QLabel(f"日志文件：{logger.log_file() or '（日志文件未创建）'}")
        self.path_label.setObjectName("subtitle")
        self.path_label.setWordWrap(True)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self.view.font()
        font.setPointSize(10)
        self.view.setFont(font)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        refresh_btn = QPushButton("刷新")
        open_dir_btn = QPushButton("打开日志文件夹")
        close_btn = QPushButton("关闭")
        for button in (refresh_btn, open_dir_btn, close_btn):
            buttons.addWidget(button)

        layout.addWidget(self.path_label)
        layout.addWidget(self.view, 1)
        layout.addLayout(buttons)

        refresh_btn.clicked.connect(self._reload)
        open_dir_btn.clicked.connect(self._open_dir)
        close_btn.clicked.connect(self.accept)

        self._reload()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._reload)
        self._timer.start(2000)

    def _reload(self) -> None:
        path = logger.log_file()
        if not path or not os.path.exists(path):
            self.view.setPlainText("（暂无日志）")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = collections.deque(fh, maxlen=self._TAIL_LINES)
            self.view.setPlainText("".join(lines))
        except OSError as exc:
            self.view.setPlainText(f"读取日志失败：{exc}")

    def _open_dir(self) -> None:
        directory = logger.log_directory()
        if directory and os.path.isdir(directory):
            QDesktopServices.openUrl(QUrl.fromLocalFile(directory))


class StateImage(QLabel):
    """按传输状态显示对应图片的标签。"""

    def __init__(self, state: str = "idle", parent=None):
        super().__init__(parent)
        self.setFixedSize(170, 170)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(state)

    def set_state(self, state: str) -> None:
        pixmap = state_pixmap(state)
        if pixmap is not None:
            self.setPixmap(pixmap)
        else:
            self.clear()


class _TransferPanel(QFrame):
    """发送/接收共用的进度展示区域。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("transferPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.log)

    def clear(self) -> None:
        self.status_label.setText("")
        self.log.clear()
        self.progress.setRange(0, 0)

    def set_progress(self, percent: int) -> None:
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(max(0, min(100, percent)))


class SendTab(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[str] = []
        self._worker: Optional[TransferWorker] = None
        self._code = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        title = QLabel("发送文件")
        title.setObjectName("tabTitle")
        subtitle = QLabel("选择文件或文件夹，生成暗号后把暗号告诉对方")
        subtitle.setObjectName("subtitle")

        self.state_image = StateImage("idle")

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("添加文件")
        self.add_dir_btn = QPushButton("添加文件夹")
        self.remove_btn = QPushButton("移除选中")
        self.clear_btn = QPushButton("清空")
        self.add_files_btn.setIcon(_std_icon("SP_FileIcon"))
        self.add_dir_btn.setIcon(_std_icon("SP_DirIcon"))
        self.remove_btn.setIcon(_std_icon("SP_TrashIcon"))
        for button in (self.add_files_btn, self.add_dir_btn, self.remove_btn, self.clear_btn):
            file_buttons.addWidget(button)

        self.start_btn = QPushButton("开始发送")
        self.start_btn.setObjectName("primary")

        code_row = QHBoxLayout()
        self.code_value = QLabel("")
        self.code_value.setObjectName("codeValue")
        self.code_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.copy_btn = QPushButton("复制暗号")
        code_row.addWidget(self.code_value, 1)
        code_row.addWidget(self.copy_btn)

        self.panel = _TransferPanel()
        self.panel.progress.setRange(0, 0)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.hide()
        self.code_value.hide()
        self.copy_btn.hide()
        self.panel.hide()

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.state_image, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.file_list, 1)
        root.addLayout(file_buttons)
        root.addWidget(self.start_btn)
        root.addLayout(code_row)
        root.addWidget(self.panel)
        root.addWidget(self.cancel_btn)

        self.add_files_btn.clicked.connect(self._add_files)
        self.add_dir_btn.clicked.connect(self._add_dir)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear)
        self.start_btn.clicked.connect(self._start)
        self.copy_btn.clicked.connect(self._copy_code)
        self.cancel_btn.clicked.connect(self._cancel)


    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择要发送的文件", "", "所有文件 (*)")
        for path in files:
            if path and path not in self._files:
                self._files.append(path)
                self.file_list.addItem(path)

    def _add_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择要发送的文件夹", "")
        if path and path not in self._files:
            self._files.append(path)
            self.file_list.addItem(path)

    def _remove_selected(self) -> None:
        for item in list(self.file_list.selectedItems()):
            path = item.text()
            if path in self._files:
                self._files.remove(path)
            self.file_list.takeItem(self.file_list.row(item))

    def _clear(self) -> None:
        self._files.clear()
        self.file_list.clear()

    def _start(self) -> None:
        if not self._files:
            QMessageBox.warning(self, APP_NAME, "请先选择要发送的文件或文件夹。")
            return
        args = ["send", "--no-qr"] + self._files
        self._begin_transfer(args, cwd=None)

    def _begin_transfer(self, args: List[str], cwd: Optional[str]) -> None:
        self._code = ""
        self.code_value.setText("")
        self.code_value.show()
        self.copy_btn.setEnabled(False)
        self.copy_btn.show()
        self.panel.show()
        self.panel.clear()
        self.panel.status_label.setText("正在准备…")
        self.cancel_btn.show()
        self._set_busy(True)
        self.state_image.set_state("wait")

        self._worker = TransferWorker(args, cwd=cwd, parent=self)
        self._worker.code_ready.connect(self._on_code_ready)
        self._worker.status.connect(self._on_status)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percent: int, detail: str) -> None:
        self.panel.set_progress(percent)
        text = f"发送中… {percent}%"
        if detail:
            text += f"（{detail}）"
        self.panel.status_label.setText(text)

    def _on_cancelled(self) -> None:
        self.panel.status_label.setText("已取消。")
        self.panel.progress.setRange(0, 1)
        self.panel.progress.setValue(0)
        self.state_image.set_state("idle")
        self._code = ""
        self.code_value.setText("")
        self.code_value.hide()
        self.copy_btn.hide()

    def _on_code_ready(self, code: str) -> None:
        self._code = code
        self.code_value.setText(code)
        self.copy_btn.setEnabled(True)
        self.panel.status_label.setText("等待对方输入暗号…")

    def _on_status(self, text: str) -> None:
        self.panel.log.appendPlainText(text)

    def _on_succeeded(self, _received_path: str) -> None:
        self.panel.status_label.setText("发送完成。")
        self.panel.progress.setRange(0, 1)
        self.panel.progress.setValue(1)
        self.state_image.set_state("success")

    def _on_failed(self, message: str) -> None:
        self.panel.status_label.setText("发送失败。")
        self.state_image.set_state("fail")
        QMessageBox.critical(self, APP_NAME, message or "发送失败。")

    def _on_finished(self) -> None:
        self._set_busy(False)
        self.cancel_btn.hide()
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        self.file_list.setEnabled(not busy)
        self.add_files_btn.setEnabled(not busy)
        self.add_dir_btn.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.start_btn.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _copy_code(self) -> None:
        if self._code:
            QApplication.clipboard().setText(self._code)
            self.panel.status_label.setText("暗号已复制。")

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()


class ReceiveTab(QWidget):
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[TransferWorker] = None
        self._output_dir = default_download_dir()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(14)

        title = QLabel("接收文件")
        title.setObjectName("tabTitle")
        subtitle = QLabel("输入对方提供的暗号，文件会保存到你选择的位置")
        subtitle.setObjectName("subtitle")

        self.state_image = StateImage("idle")

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("输入暗号，例如 3-tomorrow-concert")

        dir_label = QLabel("保存位置")
        dir_label.setObjectName("subtitle")
        dir_row = QHBoxLayout()
        self.dir_value = QLabel(self._output_dir)
        self.dir_value.setWordWrap(True)
        self.browse_btn = QPushButton("选择位置")
        self.browse_btn.setIcon(_std_icon("SP_DirOpenIcon"))
        dir_row.addWidget(self.dir_value, 1)
        dir_row.addWidget(self.browse_btn)

        self.start_btn = QPushButton("开始接收")
        self.start_btn.setObjectName("primary")

        self.panel = _TransferPanel()
        self.cancel_btn = QPushButton("取消")
        self.open_btn = QPushButton("打开接收位置")
        self.open_btn.setIcon(_std_icon("SP_DirOpenIcon"))
        self.cancel_btn.hide()
        self.open_btn.hide()
        self.panel.hide()

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self.state_image, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.code_input)
        root.addWidget(dir_label)
        root.addLayout(dir_row)
        root.addWidget(self.start_btn)
        root.addWidget(self.panel)
        root.addWidget(self.cancel_btn)
        root.addWidget(self.open_btn)
        root.addStretch(1)

        self.browse_btn.clicked.connect(self._browse)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(self._cancel)
        self.open_btn.clicked.connect(self._open_dir)


    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择保存位置", self._output_dir)
        if path:
            self._output_dir = path
            self.dir_value.setText(path)

    def _start(self) -> None:
        code = self.code_input.text().strip()
        if not code:
            QMessageBox.warning(self, APP_NAME, "请输入暗号。")
            return
        if not self._output_dir:
            QMessageBox.warning(self, APP_NAME, "请选择保存位置。")
            return
        os.makedirs(self._output_dir, exist_ok=True)
        args = ["receive", "--accept-file", code]
        self._begin_transfer(args, cwd=self._output_dir)

    def _begin_transfer(self, args: List[str], cwd: Optional[str]) -> None:
        self.panel.show()
        self.panel.clear()
        self.panel.status_label.setText("正在等待发送方…")
        self.cancel_btn.show()
        self.open_btn.hide()
        self._set_busy(True)
        self.state_image.set_state("wait")

        self._worker = TransferWorker(args, cwd=cwd, parent=self)
        self._worker.status.connect(self._on_status)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percent: int, detail: str) -> None:
        self.panel.set_progress(percent)
        text = f"接收中… {percent}%"
        if detail:
            text += f"（{detail}）"
        self.panel.status_label.setText(text)

    def _on_cancelled(self) -> None:
        self.panel.status_label.setText("已取消，残留的临时文件可手动删除。")
        self.panel.progress.setRange(0, 1)
        self.panel.progress.setValue(0)
        self.state_image.set_state("idle")

    def _on_status(self, text: str) -> None:
        self.panel.log.appendPlainText(text)

    def _on_succeeded(self, received_path: str) -> None:
        self.panel.status_label.setText("接收完成。")
        self.panel.progress.setRange(0, 1)
        self.panel.progress.setValue(1)
        self.state_image.set_state("success")
        if received_path:
            self.panel.status_label.setText(f"接收完成：{received_path}")
        self.open_btn.show()

    def _on_failed(self, message: str) -> None:
        self.panel.status_label.setText("接收失败。")
        self.state_image.set_state("fail")
        QMessageBox.critical(self, APP_NAME, message or "接收失败。")

    def _on_finished(self) -> None:
        self._set_busy(False)
        self.cancel_btn.hide()
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        self.code_input.setEnabled(not busy)
        self.browse_btn.setEnabled(not busy)
        self.start_btn.setEnabled(not busy)
        self.busy_changed.emit(busy)

    def _open_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_dir))

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(680, 620)

        self.tabs = QTabWidget()
        self.send_tab = SendTab()
        self.receive_tab = ReceiveTab()
        self.tabs.addTab(self.send_tab, "发送")
        self.tabs.addTab(self.receive_tab, "接收")
        self.setCentralWidget(self.tabs)

        self.send_tab.busy_changed.connect(self._on_busy_changed)
        self.receive_tab.busy_changed.connect(self._on_busy_changed)

        self._update_checker: Optional[UpdateChecker] = None
        self._build_menu()
        self._auto_check_updates()

    def _on_busy_changed(self, _busy: bool) -> None:
        busy = self.send_tab._worker is not None or self.receive_tab._worker is not None
        self.tabs.tabBar().setEnabled(not busy)

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("帮助")
        log_action = help_menu.addAction("查看日志")
        check_action = help_menu.addAction("检查更新")
        about_action = help_menu.addAction("关于 FlashDrop")
        log_action.triggered.connect(self._show_logs)
        check_action.triggered.connect(self._check_updates_manual)
        about_action.triggered.connect(self._show_about)

    def _show_logs(self) -> None:
        dialog = getattr(self, "_log_dialog", None)
        if dialog is None:
            dialog = LogViewerDialog(self)
            self._log_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def closeEvent(self, event) -> None:
        checker = self._update_checker
        if checker is not None and checker.isRunning():
            checker.wait(15000)
        super().closeEvent(event)

    def _start_update_check(self, silent: bool) -> None:
        if self._update_checker is not None and self._update_checker.isRunning():
            return
        self._update_checker = UpdateChecker(self)
        self._update_checker.result_ready.connect(
            lambda has_update, latest, url: self._on_update_result(
                has_update, latest, url, silent=silent
            )
        )
        self._update_checker.start()

    def _auto_check_updates(self) -> None:
        self._start_update_check(silent=True)

    def _check_updates_manual(self) -> None:
        self._start_update_check(silent=False)

    def _on_update_result(
        self, has_update: bool, latest: str, url: str, silent: bool = False
    ) -> None:
        if has_update:
            box = QMessageBox(self)
            box.setWindowTitle(APP_NAME)
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"发现新版本 {latest}")
            box.setInformativeText(f"当前版本：{__version__}\n最新版本：{latest}")
            open_button = box.addButton("打开下载页", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("稍后", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is open_button and url:
                QDesktopServices.openUrl(QUrl(url))
        elif not silent:
            QMessageBox.information(self, APP_NAME, "当前已是最新版本。")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            APP_NAME,
            f"即传 FlashDrop\n版本 {__version__}\n\n一个点对点传文件的桌面应用。",
        )


def main() -> int:
    app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(STYLESHEET)
    logger.setup_logging()
    window = MainWindow()
    window.show()
    return app.exec()

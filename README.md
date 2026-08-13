# 即传 FlashDrop

一个点对点传文件的桌面应用。发送方选择文件后生成一个暗号，接收方输入暗号即可直传，双方同时在线即可，文件默认点对点直连，数据经过端到端加密。

## 界面状态

界面通过图片直观反馈当前进度：

| 状态 | 含义 |
| --- | --- |
| idle（待机） | 尚未开始发送或接收文件 |
| wait（等待） | 等待对方输入暗号，或等待自己接收 |
| success（成功） | 发送 / 接收成功 |
| fail（失败） | 传输失败，并弹出错误提示 |

## 功能

- **发送**：选择文件或文件夹，生成暗号，把暗号发给对方。
- **接收**：输入暗号，选择保存位置，直接接收。
- **检查更新**：菜单「帮助 → 检查更新」自动查询 GitHub 最新发布版本，启动时也会静默检查。

## 运行（开发环境）

```powershell
python -m pip install -r requirements.txt
python main.py
```

冒烟测试（离屏验证界面可用）：

```powershell
python -m tests.smoke_test
```

## 项目结构

```
flashdrop/
├── app.py        # 界面与交互逻辑（发送 / 接收 / 状态展示）
├── transfer.py   # 传输内核封装（后台线程运行 wormhole）
├── updater.py    # 检查更新（查询 GitHub Releases）
├── __init__.py   # 包信息与版本号
└── __main__.py   # python -m flashdrop 入口
Asset/            # 状态图片（idle / wait / success / fail）与应用图标 icon.ico
main.py           # 程序入口
wormhole_cli.py   # wormhole CLI 的薄封装，用于打包
build.ps1         # PyInstaller 打包脚本
tests/            # 冒烟测试
tools/            # 辅助脚本（make_icon.py：从 Idle.webp 生成 icon.ico）
```

## 打包成可执行文件

```powershell
.\build.ps1
```

打包结果在 `dist\FlashDrop\`，把整个文件夹压缩后发给对方即可。对方无需安装 Python。

## 发布与更新

「检查更新」依赖 GitHub Releases。发布新版本时，打一个形如 `v0.3.0` 的 tag 并创建 Release，客户端会自动提示升级。

## 依赖

- `magic-wormhole`：点对点传输内核。
- `PySide6`：桌面界面。

## 许可证

[MIT](LICENSE)

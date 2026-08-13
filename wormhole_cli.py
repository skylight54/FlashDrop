"""magic-wormhole CLI 的薄封装，用于随应用一起打包成独立可执行文件。"""

from wormhole.cli.cli import wormhole


if __name__ == "__main__":
    wormhole()

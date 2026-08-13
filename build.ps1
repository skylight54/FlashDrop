$ErrorActionPreference = "Stop"

$VenvPython = ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "创建干净打包环境..."
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt pyinstaller
}

Write-Host "打包 wormhole 辅助程序..."
& $VenvPython -m PyInstaller `
  --noconfirm --clean --onefile --console `
  --name wormhole_cli `
  --hidden-import twisted.internet.selectreactor `
  --hidden-import txaio.tx `
  --collect-submodules spake2.parameters `
  --collect-data autobahn `
  wormhole_cli.py

Write-Host "打包 FlashDrop 主程序..."
$iconArgs = @()
if (Test-Path "Asset\icon.ico") {
    $iconArgs = @("--icon", "Asset\icon.ico")
}

& $VenvPython -m PyInstaller `
  --noconfirm --clean --windowed --onedir `
  --name FlashDrop `
  --add-data "Asset;Asset" `
  @iconArgs `
  main.py

Write-Host "合并可执行文件..."
Copy-Item -Force "dist\wormhole_cli.exe" "dist\FlashDrop\wormhole_cli.exe"

Write-Host "打包完成：dist\FlashDrop\FlashDrop.exe"

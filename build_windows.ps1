$ErrorActionPreference = 'Stop'

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name DesktopOrganizer --collect-all pystray --collect-all PIL main.py
Write-Host "Build complete: dist\DesktopOrganizer.exe"

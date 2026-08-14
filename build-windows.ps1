$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "PDF-Template-Editor" `
    --add-data "assets/DejaVuSans.ttf;assets" `
    launcher.py

Write-Host "Windows executable created at dist/PDF-Template-Editor.exe"

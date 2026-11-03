@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name RoofStudio_v0.6 roofstudio.py
pause

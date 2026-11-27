@echo off
cd /d "%~dp0"
echo ES-Share Windows .exe olusturuluyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --name ES-Share --add-data "ui\dist;ui\dist" --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 app.py
echo.
echo Tamamlandi! Dosya konumu: dist\ES-Share.exe
pause


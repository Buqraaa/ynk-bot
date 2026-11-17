@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ============================================
echo   YNK BOT - GELISTIRME MODU
echo ============================================
echo.
echo Bot kaynak kodlardan baslatiliyor.
echo Kod degisikligi yaptiysan bu pencereyi kapatip
echo tekrar GELISTIR.bat dosyasina cift tikla.
echo.
python bot.py
if errorlevel 1 pause

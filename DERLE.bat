@echo off
chcp 65001 >nul
cd /d "%~dp0"
tasklist /FI "IMAGENAME eq YNK-BOT.exe" 2>nul | find /I "YNK-BOT.exe" >nul
if not errorlevel 1 (
    echo.
    echo Once YNK BOT uygulamasini kapatin, sonra tekrar deneyin.
    pause
    exit /b 1
)
echo.
echo ============================================
echo   YNK BOT - EXE DERLEME
echo ============================================
echo.
echo Derleme basladi, 1-2 dakika surer...
echo.
python -m PyInstaller --noconfirm --clean bot.spec
if errorlevel 1 goto hata
copy /Y "dist\bot.exe" "YNK-BOT.exe" >nul
if errorlevel 1 goto hata
echo.
echo ============================================
echo   TAMAM: YNK-BOT.exe guncellendi.
echo   Masaustundeki "YNK BOT" kisayolundan acabilirsin.
echo ============================================
pause
exit /b 0

:hata
echo.
echo ============================================
echo   HATA: Derleme basarisiz oldu.
echo   Yukaridaki kirmizi mesaji kontrol et.
echo ============================================
pause
exit /b 1

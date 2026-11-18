@echo off
chcp 65001 >nul
cd /d "C:\Users\ozkay\OneDrive\Masaüstü\YNK BOT"
echo ==============================
echo   YNK BOT - GitHub Push
echo ==============================
echo.
git add .
git commit -m "update: %date% %time%"
git push origin main
echo.
if %errorlevel%==0 (
    echo Push basarili! Railway otomatik deploy edecek.
) else (
    echo Push basarisiz. Hata yukarida.
)
echo.
pause
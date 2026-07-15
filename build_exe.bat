@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] PyInstaller をインストール...
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2/3] exe をビルド中...
py -3 -m PyInstaller --noconfirm NikkeBounceAim.spec
if errorlevel 1 goto :fail

echo [3/3] 配布フォルダを作成...
set OUT=dist\NikkeBounceAim_配布
if exist "%OUT%" rmdir /s /q "%OUT%"
mkdir "%OUT%"
copy /Y "dist\NikkeBounceAim.exe" "%OUT%\NikkeBounceAim.exe" >nul
copy /Y "取説.txt" "%OUT%\取説.txt" >nul

echo.
echo 完了: %OUT%
echo   - NikkeBounceAim.exe
echo   - 取説.txt
echo.
explorer "%OUT%"
goto :eof

:fail
echo.
echo ビルドに失敗しました。
pause
exit /b 1

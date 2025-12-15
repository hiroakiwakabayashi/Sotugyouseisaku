@echo off
setlocal

REM 仮想環境を有効化
IF EXIST venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM 念のため最新版をインストール
pip install -r requirements.txt

REM exe ビルド（まずはフォルダ形式で）
py -m PyInstaller ^
  --noconfirm --clean ^
  --onedir --windowed ^
  --name KaoKintai ^
  --collect-all cv2 ^
  --collect-all tkcalendar ^
  --add-data "config;config" ^
  --add-data "data;data" ^
  --add-data "app\config;app\config" ^
  app\main.py

echo.
echo Build finished. See the dist\KaoKintai folder.
pause

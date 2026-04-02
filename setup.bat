@echo off
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
echo セットアップ完了。 run.bat で起動できます。

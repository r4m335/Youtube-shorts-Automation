@echo off
cd /d "%~dp0"
echo Starting YouTube Shorts Pipeline Setup...
IF NOT EXIST logs mkdir logs

echo Running Pipeline...
call .\venv\Scripts\Activate.bat
python main.py >> logs\cron.log 2>&1

echo Pipeline run complete.

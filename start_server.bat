@echo off
echo Starting Django server...
cd D:\Major\Project\Website
start "" python manage.py runserver
timeout /t 5 >nul
start http://127.0.0.1:8000/


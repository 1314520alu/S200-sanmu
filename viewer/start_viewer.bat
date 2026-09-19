@echo off
cd /d "%~dp0"
echo Serving viewer from: %CD%
echo URL: http://127.0.0.1:18765/
start "" http://127.0.0.1:18765/index.html
py -3 "C:\Users\alu\AppData\Local\Temp\s200_viewer_server.py"

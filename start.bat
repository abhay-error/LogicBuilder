@echo off
cd /d "%~dp0"
where python >nul 2>nul && (python server.py %* & goto :eof)
where py >nul 2>nul && (py -3 server.py %* & goto :eof)
echo Python 3.9+ not found. Install it from https://www.python.org/downloads/ and tick "Add to PATH".
pause

@echo off
rem Double-click to install Ollama and download the local AI tutor models.
rem Options are passed through, e.g.  setup-ai.bat -Profile standard -Yes   or   setup-ai.bat -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-ai.ps1" %*
echo.
pause

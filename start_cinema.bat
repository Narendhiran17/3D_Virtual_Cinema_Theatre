@echo off
title 3D Virtual Cinema Theatre Launcher
echo ============================================================
echo      HORIZON GRAND CINEPLEX - 3D VIRTUAL THEATRE
echo ============================================================
echo.
echo Launching 3D Cinema Web Application on http://localhost:3000/
echo.

cd /d "%~dp0app"

:: Open the default browser to the web app
start "" http://localhost:3000/

:: Start the Vite server
npm run dev

pause

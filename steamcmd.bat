@echo off
set ROOT_DIR=%~dp0
title CS 1.6

cls
echo (%time%) Downloading SteamCMD...

:: Ensure steamcmd exists
if not exist "%ROOT_DIR%steamcmd\steamcmd.exe" (
    mkdir "%ROOT_DIR%steamcmd"
    powershell -Command "Invoke-WebRequest -Uri https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -OutFile '%ROOT_DIR%steamcmd\steamcmd.zip'"
    powershell -Command "Expand-Archive -Path '%ROOT_DIR%steamcmd\steamcmd.zip' -DestinationPath '%ROOT_DIR%steamcmd'"
    del "%ROOT_DIR%steamcmd\steamcmd.zip"
)

echo (%time%) Checking SteamCMD status...

start /wait %ROOT_DIR%steamcmd\steamcmd.exe +login anonymous +quit

echo (%time%) SteamCMD downloaded. You can close this window now.

pause
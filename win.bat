@echo off
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: Prevent window from closing
if not defined in_subprocess (set in_subprocess=1 & cmd /k "%~f0" & exit)

title CS 1.6 Dedicated Server
if not exist win.ini copy NUL win.ini
for /f "tokens=*" %%S in (win.ini) do set "%%S"
cls

:: --- 1. STEAMCMD CHECK ---
if exist "%ROOT_DIR%steamcmd\steamcmd.exe" goto check_update
echo (%time%) ERROR: SteamCMD.exe not found in %ROOT_DIR%steamcmd\
echo Download from https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip and extract to 
echo %ROOT_DIR%steamcmd\steamcmd.exe or run steamcmd.bat to download it
pause
exit

:check_update
:: --- 2. LIVE PROGRESS (No-File Method) ---
echo (%time%) Checking Steam for updates...
echo.

:: We run the command and check for the success string inside the SAME pipeline
powershell -ExecutionPolicy Bypass -Command "$process = Start-Process -FilePath '%ROOT_DIR%steamcmd\steamcmd.exe' -ArgumentList '+force_install_dir ../server', '+login anonymous', '+app_set_config 90 mod cstrike', '+app_update 90 -beta steam_legacy validate', '+quit' -Wait -NoNewWindow -PassThru; exit $process.ExitCode"

:: SteamCMD usually returns 0 on success. If it loops, we double-check the files.
if errorlevel 1 goto retry_update
goto update_confirmed

:retry_update
echo.
echo (%time%) SteamCMD reported an issue or incomplete update. Retrying...
timeout /t 5 >nul
goto check_update

:update_confirmed
echo.
echo (%time%) Update confirmed!

:start
:: --- 3. LAUNCH ---
echo (%time%) Finalizing mod files...
xcopy "%ROOT_DIR%cstrike\*" "%ROOT_DIR%server\cstrike\" /K /S /E /I /H /Y >NUL 2>&1
xcopy "%ROOT_DIR%%custom_folder%\*" "%ROOT_DIR%server\cstrike\" /K /S /E /I /H /Y >NUL 2>&1

:: Fix for the !m_bMounted error
echo 10 > "%ROOT_DIR%server\steam_appid.txt"

:: Build launch args from win.ini settings
set "LAUNCH_ARGS=-game cstrike -console +port %cs16_port% +maxplayers %cs16_players% +map %cs16_map% +sys_ticrate %cs16_ticrate% +net_public_adr %ip_internet%"
if defined rcon_password set "LAUNCH_ARGS=%LAUNCH_ARGS% +rcon_password %rcon_password%"
if defined server_password set "LAUNCH_ARGS=%LAUNCH_ARGS% +sv_password %server_password%"
if defined sv_lan set "LAUNCH_ARGS=%LAUNCH_ARGS% +sv_lan %sv_lan%"

echo (%time%) Launching HLDS...
cd /d "%ROOT_DIR%server"
start hlds.exe %LAUNCH_ARGS%

echo.
echo Server window opened. Press any key here to restart it.
pause
goto check_update

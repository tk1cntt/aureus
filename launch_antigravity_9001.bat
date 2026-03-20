@echo off
set "IDE_PATH=C:\Users\Admin\AppData\Local\Programs\Antigravity\Antigravity.exe"
set "PORT=9001"
set "WORKSPACE=D:\Aureus"
:: Create a unique user data directory to force a new process and debugging port
set "USER_DATA=%APPDATA%\Antigravity-Aureus-9001"

echo Launching Antigravity on port %PORT% with workspace %WORKSPACE%...
echo Using isolated User Data Dir: %USER_DATA%

start "" "%IDE_PATH%" --remote-debugging-port=%PORT% --inspect=%PORT% --user-data-dir="%USER_DATA%" --new-window "%WORKSPACE%"
echo Attempted launch. Please wait a few seconds and check netstat.
exit

@echo off
REM Keep your proxy for 翻墙, but bypass localhost so MCP Bridge can reach Hub:8900
REM HTTP_PROXY stays; NO_PROXY forces direct connect to 127.0.0.1 / localhost

if not defined HTTP_PROXY set "HTTP_PROXY=http://127.0.0.1:7890"
if not defined HTTPS_PROXY set "HTTPS_PROXY=%HTTP_PROXY%"

set "NO_PROXY=127.0.0.1,localhost,::1,*.local"
set "no_proxy=%NO_PROXY%"

start "" "C:\Program Files\lceda-pro\lceda-pro.exe"
echo.
echo LCEDA started.
echo   HTTP_PROXY = %HTTP_PROXY%
echo   NO_PROXY   = %NO_PROXY%
echo Keep Cursor open so jlceda Hub listens on ws://127.0.0.1:8900/bridge/ws
echo.
pause

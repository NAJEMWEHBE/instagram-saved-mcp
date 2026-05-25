@echo off
REM ===================================================================
REM  instagram-saved-mcp - Windows installer
REM  Installs uv (if missing), then registers the MCP server in the
REM  Claude Desktop config. No manual terminal use required afterwards.
REM ===================================================================
echo.
echo ==================================================
echo   instagram-saved-mcp  -  Windows installer
echo ==================================================
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo [1/2] Installing uv ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
) else (
  echo [1/2] uv already installed.
)
echo.

echo [2/2] Registering 'instagram-saved' in Claude Desktop config ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$cfg = Join-Path $env:APPDATA 'Claude\claude_desktop_config.json'; $dir = Split-Path $cfg; if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }; if (Test-Path $cfg) { try { $json = Get-Content $cfg -Raw | ConvertFrom-Json } catch { $json = [pscustomobject]@{} } } else { $json = [pscustomobject]@{} }; if (-not $json.mcpServers) { $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }; $server = [pscustomobject]@{ command = 'uvx'; args = @('instagram-saved-mcp') }; $json.mcpServers | Add-Member -NotePropertyName 'instagram-saved' -NotePropertyValue $server -Force; $json | ConvertTo-Json -Depth 10 | Set-Content $cfg -Encoding UTF8; Write-Host ('Updated ' + $cfg)"
echo.

echo ==================================================
echo   Done. Next steps:
echo   1) Fully restart Claude Desktop.
echo   2) Ask it to run refresh_index with the path to
echo      your Instagram export ZIP, e.g.:
echo        refresh_index("C:\Users\you\Downloads\instagram-export.zip")
echo ==================================================
echo.
pause

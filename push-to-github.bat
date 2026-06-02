@echo off
chcp 65001 >nul
echo ══════════════════════════════════════
echo   Push to GitHub — Token Reward Bot
echo ══════════════════════════════════════
echo.

where gh >nul 2>&1
if errorlevel 1 (
    echo [!] GitHub CLI not found. Install: winget install GitHub.cli
    pause
    exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
    echo Login to GitHub first:
    gh auth login
    echo.
)

echo Creating repo and pushing...
gh repo create token-reward-bot --public --source=. --remote=origin --push

if errorlevel 1 (
    echo.
    echo Manual fallback:
    echo   1. Create repo at https://github.com/new named token-reward-bot
    echo   2. git remote add origin https://github.com/mhmdalira/token-reward-bot.git
    echo   3. git push -u origin main
)

pause

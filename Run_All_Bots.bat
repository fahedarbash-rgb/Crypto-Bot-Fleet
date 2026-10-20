@echo off
title Crypto Bot Fleet Launcher

echo Launching Full Crypto Bot Fleet...

start "Sniper Scalper Bot" cmd /k "cd /d "%~dp0sniper_scalper_bot" && python trading_bot_scalper.py"
start "Strict Bot" cmd /k "cd /d "%~dp0Strict Bot" && python trading_bot.py"
start "Global Bot" cmd /k "cd /d "%~dp0global_bot" && python trading_bot_global.py"
start "Balanced Bot" cmd /k "cd /d "%~dp0balanced_bot" && python balanced_bot.py"
start "Flexible Bot" cmd /k "cd /d "%~dp0flexible_bot" && python trading_bot_flexible.py"
start "Telegram Listener" cmd /k "cd /d "%~dp0telegram_bot" && python telegram_listener.py"

echo All 5 Trading Bots + Telegram Listener Launched Successfully!
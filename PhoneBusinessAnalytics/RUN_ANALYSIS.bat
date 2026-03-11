@echo off
echo.
echo ========================================
echo   Running all analysis scripts...
echo ========================================
echo.

echo --- PROFIT ANALYSIS ---
cd analysis
python profit_analysis.py

echo.
echo --- INVENTORY ANALYSIS ---
python inventory_analysis.py

echo.
echo --- MARKET TRACKER ---
python market_tracker.py

cd ..
echo.
echo ========================================
echo   Done! Scroll up to read the results.
echo ========================================
pause

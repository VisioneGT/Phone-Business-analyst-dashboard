@echo off
echo.
echo ========================================
echo   Phone Business Analytics - Setup
echo ========================================
echo.

echo Step 1: Installing required libraries...
pip install pandas plotly dash
echo.

echo Step 2: Creating the database...
cd database
python setup_db.py
cd ..
echo.

echo ========================================
echo   Setup complete!
echo.
echo   To run analysis, open PowerShell and:
echo   cd analysis
echo   python profit_analysis.py
echo   python inventory_analysis.py
echo   python market_tracker.py
echo.
echo   To open the dashboard:
echo   cd dashboard
echo   python app.py
echo   Then go to http://127.0.0.1:8050
echo ========================================
echo.
pause

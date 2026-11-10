@echo off
REM RotorLab launcher - works from any directory or by double-clicking.
cd /d "%~dp0"
if not exist ".venv\Scripts\streamlit.exe" (
    echo Virtual environment not found. Creating it and installing dependencies...
    python -m venv .venv || goto :error
    ".venv\Scripts\pip.exe" install -r requirements.txt || goto :error
)
echo Starting RotorLab at http://localhost:8501  (press Ctrl+C to stop)
".venv\Scripts\streamlit.exe" run app.py --server.port 8501
goto :eof

:error
echo Setup failed. See messages above.
pause

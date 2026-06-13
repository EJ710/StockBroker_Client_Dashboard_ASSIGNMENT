@echo off
REM ---------------------------------------------------------------------------
REM Windows launcher for the backend (equivalent of run.sh).
REM Creates a virtualenv on first run, installs deps, then starts the API.
REM Usage (from the backend folder):  run.bat
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

if not exist ".venv\" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo Starting API on http://localhost:8000  (docs at /docs)
uvicorn app.main:app --reload --port 8000

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

REM Port is configurable via the PORT env var (default 8000) in case 8000 is busy.
if "%PORT%"=="" set PORT=8000
echo Starting API on http://localhost:%PORT%  (docs at /docs)
uvicorn app.main:app --reload --port %PORT%

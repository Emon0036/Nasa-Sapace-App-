@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
set "FRONTEND_ROOT=%PROJECT_ROOT%frontend"

if not exist "%PYTHON_EXE%" (
  echo Project Python environment not found: "%PYTHON_EXE%"
  echo Create a Python 3.12 environment and install requirements.txt. See README.md.
  exit /b 1
)
if not exist "%FRONTEND_ROOT%\node_modules" (
  echo Frontend dependencies are missing.
  echo Run "npm.cmd install" in "%FRONTEND_ROOT%" first.
  exit /b 1
)

curl.exe -fsS "http://127.0.0.1:8000/api/health" >nul 2>&1
if errorlevel 1 (
  echo Starting FastAPI in a separate window...
  start "Lunar Horizon API" /D "%PROJECT_ROOT%" "%PYTHON_EXE%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
  for /L %%I in (1,1,30) do (
    curl.exe -fsS "http://127.0.0.1:8000/api/health" >nul 2>&1
    if not errorlevel 1 goto API_READY
    timeout /t 1 /nobreak >nul
  )
  echo FastAPI did not become healthy within 30 seconds. Check the API window.
  exit /b 1
) else (
  echo FastAPI is already healthy at http://127.0.0.1:8000.
)

:API_READY
curl.exe -fsS "http://127.0.0.1:5173/" >nul 2>&1
if not errorlevel 1 (
  echo React is already available at http://127.0.0.1:5173/.
  exit /b 0
)

echo Starting React. Keep this terminal and the API window open.
pushd "%FRONTEND_ROOT%"
call npm.cmd run dev
set "VITE_EXIT=%ERRORLEVEL%"
popd
exit /b %VITE_EXIT%

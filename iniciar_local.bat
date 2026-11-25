@echo off
REM Windows: abre la API y la interfaz
set PY=python
if exist venv\Scripts\python.exe set PY=venv\Scripts\python.exe
start "API" cmd /k "%PY% -m uvicorn api:app --port 8000"
timeout /t 4 >nul
set API_URL=http://localhost:8000
%PY% -m streamlit run app_streamlit.py
pause

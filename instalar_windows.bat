@echo off
REM Windows: crea el entorno con Python 3.12 e instala las librerias (se hace UNA sola vez)
py install 3.12
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Listo. Ahora abri iniciar_local.bat
pause

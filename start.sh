#!/bin/bash
# Levanta la API (puerto 8000) y la interfaz (puerto 7860) en el mismo contenedor
uvicorn api:app --host 127.0.0.1 --port 8000 &
sleep 3
API_URL=http://127.0.0.1:8000 streamlit run app_streamlit.py --server.port ${PORT:-7860} --server.address 0.0.0.0 --server.headless true

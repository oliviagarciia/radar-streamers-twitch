#!/bin/bash
# Mac/Linux: abre la API y la interfaz (necesita haber hecho "pip install -r requirements.txt")
uvicorn api:app --port 8000 &
sleep 3
API_URL=http://localhost:8000 streamlit run app_streamlit.py

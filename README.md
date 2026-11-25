---
title: Radar de streamers de Twitch
emoji: 📈
sdk: docker
app_port: 7860
---

# Radar de streamers de Twitch

Servicio + interfaz para usar el modelo del TP3 (Random Forest que predice el crecimiento de seguidores
2020 → 2024). Proyecto de Ciencia de Datos Aplicada (ITBA) – Abril Lombardo y Olivia García.

## Cómo está armado

```
Interfaz (Streamlit)  ──HTTP──▶  API (FastAPI)  ──▶  model_service.py  ──▶  modelo .joblib
   app_streamlit.py                api.py             (lógica del modelo)    modelo/
```

| Archivo | Para qué sirve |
|---|---|
| `model_service.py` | Carga el modelo y predice. No sabe nada de web. |
| `utils_twitch.py` | Arma las variables del modelo (la misma función del entrenamiento). |
| `api.py` | API REST: recibe datos, valida y devuelve resultados. Maneja errores. |
| `app_streamlit.py` | Interfaz web que consume la API. |
| `modelo/` | Modelo guardado (`.joblib`), metadatos y predicciones de referencia. |
| `datos/streamers_ejemplo.csv` | 15 canales para probar el ranking. |
| `tests/test_api.py` | Pruebas automáticas (`pytest -q`). |
| `preparar_referencia.py` | Regenera la referencia y el ejemplo desde el dataset 2020. |

## Correrlo en tu computadora

Necesitás Python **3.12** (las versiones más nuevas, como la 3.15, todavía no sirven con estas librerías).

**Windows (lo más fácil):** doble click en `instalar_windows.bat` (una sola vez) y después en `iniciar_local.bat`.

A mano:

```bash
pip install -r requirements.txt
```

Después, en **dos terminales**:

```bash
uvicorn api:app --port 8000                      # 1) la API (docs en http://localhost:8000/docs)
streamlit run app_streamlit.py                   # 2) la interfaz (http://localhost:8501)
```

Atajo: `iniciar_local.bat` (Windows) o `./iniciar_local.sh` (Mac/Linux) hacen las dos cosas.
Si la API está en otra dirección, definí la variable `API_URL` antes de abrir la interfaz.

## Qué datos pide

Una fila por streamer, con los datos del **último año** del canal:

| Campo (API / CSV) | Qué es |
|---|---|
| `seguidores` | seguidores actuales |
| `seguidores_ganados` | seguidores que sumó en el año (puede ser negativo) |
| `viewers_promedio` / `viewers_pico` | promedio y máximo de viewers |
| `horas_transmitidas` | horas de stream en el año |
| `views_ganadas` | visualizaciones sumadas en el año |
| `partner`, `contenido_adulto`, `idioma`, `categoria` | opcionales |
| `horas_vistas` | opcional; si falta se estima (viewers promedio × horas × 1,04) |

También acepta los nombres originales del dataset de Kaggle (`followers`, `followers gained`, etc.).

## Ejemplo de uso de la API

```bash
curl -X POST http://localhost:8000/predecir -H "Content-Type: application/json" -d '{
  "seguidores": 45000, "seguidores_ganados": 30000, "viewers_promedio": 1800,
  "viewers_pico": 7500, "horas_transmitidas": 900, "views_ganadas": 1500000,
  "idioma": "Spanish", "categoria": "Just Chatting"}'
```

Devuelve el crecimiento esperado (%), los seguidores estimados, el percentil frente a canales de referencia
y una categoría de oportunidad (Baja / Media / Alta / Muy alta).

## Publicarlo en internet (Hugging Face Spaces, gratis)

1. Crear cuenta en huggingface.co → *New Space* → SDK **Docker** (plantilla en blanco).
2. Subir todo el contenido de esta carpeta al Space (con el botón *Files → Upload*, o con git).
3. Esperar 2–5 minutos a que construya. Queda en `https://huggingface.co/spaces/<usuario>/<nombre>`.

Alternativa: Render.com (Web Service con Docker, apuntando al repositorio de GitHub).
En el plan gratis puede tardar ~1 minuto en "despertar": abrilo antes de la demo.

## Límites (para ser honestas)

Es un prototipo entrenado con 359 canales y dos cortes (2020 y 2024), con sesgo de supervivencia y sin datos
de chat ni engagement. Sirve para ordenar candidatos, no para garantizar resultados.

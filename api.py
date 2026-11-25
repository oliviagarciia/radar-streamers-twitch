"""API REST del proyecto: expone el modelo de crecimiento de streamers de Twitch.

Endpoints:
  GET  /salud           -> responde "ok" si el servicio está vivo y el modelo cargado
  GET  /info            -> datos del modelo (métricas, idiomas y categorías conocidas)
  POST /predecir        -> recibe UN streamer (JSON) y devuelve su crecimiento esperado
  POST /ranking         -> recibe una LISTA de streamers (JSON) y devuelve el ranking
  POST /ranking/csv     -> igual que /ranking pero subiendo un archivo CSV

Cómo correrla:  uvicorn api:app --port 8000     (documentación automática en /docs)
"""
import io
import logging

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from model_service import ErrorDeEntrada, ServicioModelo

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("twitch-api")

app = FastAPI(
    title="Predicción de crecimiento de streamers de Twitch",
    description="Estima cuánto se espera que crezca (en seguidores) un streamer y arma rankings "
                "de candidatos. Proyecto de Ciencia de Datos Aplicada (ITBA).",
    version="1.0.0",
)
servicio = ServicioModelo()  # se carga una sola vez al arrancar
MAX_FILAS = 5000


# ---------- formato de entrada y salida ----------
class Streamer(BaseModel):
    nombre: str = Field("", max_length=80, description="Nombre del canal (opcional)")
    seguidores: int = Field(..., ge=0, le=200_000_000, description="Seguidores actuales")
    seguidores_ganados: int = Field(..., ge=-50_000_000, le=200_000_000,
                                    description="Seguidores que sumó en el último año (puede ser negativo)")
    viewers_promedio: float = Field(..., ge=0, le=5_000_000, description="Viewers promedio por stream")
    viewers_pico: float = Field(..., ge=0, le=10_000_000, description="Máximo de viewers simultáneos")
    horas_transmitidas: float = Field(..., ge=0, le=9000, description="Horas transmitidas en el año")
    views_ganadas: int = Field(..., ge=0, le=5_000_000_000, description="Visualizaciones sumadas en el año")
    horas_vistas: float | None = Field(None, ge=0, description="Horas vistas en total (opcional, se estima)")
    partner: bool = Field(True, description="¿Es partner de Twitch?")
    contenido_adulto: bool = Field(False, description="¿Su contenido es para mayores (mature)?")
    idioma: str = Field("English", max_length=40)
    categoria: str = Field("Just Chatting", max_length=80, description="Juego o categoría principal")


class ListaStreamers(BaseModel):
    streamers: list[Streamer] = Field(..., min_length=1, max_length=MAX_FILAS)


# ---------- manejo de errores ----------
@app.exception_handler(ErrorDeEntrada)
async def manejar_error_entrada(_: Request, exc: ErrorDeEntrada):
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(RequestValidationError)
async def manejar_error_validacion(_: Request, exc: RequestValidationError):
    # Convierte el error técnico de pydantic en un mensaje entendible
    problemas = []
    for e in exc.errors()[:5]:
        campo = ".".join(str(p) for p in e["loc"] if p not in ("body", "streamers"))
        problemas.append(f"{campo or 'dato'}: {e['msg']}")
    return JSONResponse(status_code=422, content={"error": "Datos inválidos. " + " | ".join(problemas)})


@app.exception_handler(HTTPException)
async def manejar_http(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(Exception)
async def manejar_error_inesperado(_: Request, exc: Exception):
    log.exception("Error inesperado")
    return JSONResponse(status_code=500, content={"error": "Error interno al calcular la predicción."})


# ---------- endpoints ----------
@app.get("/salud")
def salud():
    return {"estado": "ok", "modelo": servicio.meta["modelo"]}


@app.get("/info")
def info():
    return servicio.info()


def _a_tabla(streamers: list[Streamer]) -> pd.DataFrame:
    return pd.DataFrame([s.model_dump() for s in streamers])


def _a_lista(resultado: pd.DataFrame) -> list[dict]:
    r = resultado.copy()
    r["crecimiento_pct"] = r["crecimiento_pct"].round(1)
    r["multiplicador"] = r["multiplicador"].round(2)
    r["crecimiento_log"] = r["crecimiento_log"].round(3)
    r["percentil_referencia"] = r["percentil_referencia"].round(1)
    return r.to_dict(orient="records")


@app.post("/predecir")
def predecir(streamer: Streamer):
    resultado = servicio.predecir(_a_tabla([streamer]))
    return _a_lista(resultado)[0]


@app.post("/ranking")
def ranking(datos: ListaStreamers):
    resultado = servicio.predecir(_a_tabla(datos.streamers))
    return {"cantidad": len(resultado), "resultados": _a_lista(resultado)}


@app.post("/ranking/csv")
async def ranking_csv(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    try:
        tabla = pd.read_csv(io.BytesIO(contenido))
    except Exception:
        raise HTTPException(status_code=400, detail="No pude leer el archivo: tiene que ser un CSV.")
    if len(tabla) == 0:
        raise HTTPException(status_code=400, detail="El CSV no tiene filas con datos.")
    if len(tabla) > MAX_FILAS:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_FILAS} filas por archivo.")
    resultado = servicio.predecir(tabla)
    return {"cantidad": len(resultado), "resultados": _a_lista(resultado)}

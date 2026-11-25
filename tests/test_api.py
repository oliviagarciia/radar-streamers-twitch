"""Pruebas automáticas de la API. Correr con:  pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from api import app  # noqa: E402

cliente = TestClient(app)
STREAMER = {
    "nombre": "demo", "seguidores": 50000, "seguidores_ganados": 20000, "viewers_promedio": 1500,
    "viewers_pico": 6000, "horas_transmitidas": 900, "views_ganadas": 900000,
    "partner": True, "contenido_adulto": False, "idioma": "Spanish", "categoria": "Just Chatting",
}


def test_salud():
    r = cliente.get("/salud")
    assert r.status_code == 200 and r.json()["estado"] == "ok"


def test_info():
    r = cliente.get("/info")
    assert r.status_code == 200 and r.json()["entrenado_con_canales"] == 359


def test_predecir_un_streamer():
    r = cliente.post("/predecir", json=STREAMER)
    assert r.status_code == 200
    d = r.json()
    assert d["multiplicador"] > 0 and 0 <= d["percentil_referencia"] <= 100


def test_categoria_e_idioma_desconocidos_no_rompen():
    r = cliente.post("/predecir", json={**STREAMER, "idioma": "Klingon", "categoria": "Juego raro"})
    assert r.status_code == 200


def test_faltan_campos():
    r = cliente.post("/predecir", json={"seguidores": 100})
    assert r.status_code == 422 and "error" in r.json()


def test_numero_negativo_invalido():
    r = cliente.post("/predecir", json={**STREAMER, "seguidores": -5})
    assert r.status_code == 422


def test_ranking_ordenado():
    chico = {**STREAMER, "nombre": "chico", "seguidores": 5000, "seguidores_ganados": 4500}
    r = cliente.post("/ranking", json={"streamers": [STREAMER, chico]})
    assert r.status_code == 200
    res = r.json()["resultados"]
    assert [x["ranking"] for x in res] == [1, 2]
    assert res[0]["crecimiento_log"] >= res[1]["crecimiento_log"]


def test_ranking_csv_plantilla():
    with open(Path(__file__).resolve().parents[1] / "datos" / "streamers_ejemplo.csv", "rb") as f:
        r = cliente.post("/ranking/csv", files={"archivo": ("ejemplo.csv", f, "text/csv")})
    assert r.status_code == 200 and r.json()["cantidad"] == 15


def test_csv_con_columnas_faltantes():
    r = cliente.post("/ranking/csv", files={"archivo": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 400 and "Faltan columnas" in r.json()["error"]


def test_csv_vacio():
    r = cliente.post("/ranking/csv", files={"archivo": ("x.csv", b"", "text/csv")})
    assert r.status_code == 400

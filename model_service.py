"""Lógica del modelo: carga el modelo guardado y hace predicciones.

Este archivo NO sabe nada de web (ni de FastAPI ni de Streamlit): solo recibe datos,
arma las variables y devuelve el crecimiento esperado. La API lo usa como una "caja".
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from utils_twitch import construir_features  # la misma función que se usó al entrenar

CARPETA = Path(__file__).parent / "modelo"
RUTA_MODELO = CARPETA / "modelo_crecimiento_twitch.joblib"
RUTA_META = CARPETA / "modelo_crecimiento_twitch_meta.json"
RUTA_REFERENCIA = CARPETA / "referencia_predicciones.npy"

# Cómo se llaman las columnas en la entrada (nombre en el CSV -> nombre interno) y su factor de unidad.
# Se aceptan los nombres en español de la plantilla y los del dataset original de Kaggle.
ALIAS_COLUMNAS = {
    "followers_2020": [("seguidores", 1), ("followers", 1)],
    "followers_gained_2020": [("seguidores_ganados", 1), ("followers gained", 1)],
    "avg_viewers_2020": [("viewers_promedio", 1), ("average viewers", 1)],
    "peak_viewers_2020": [("viewers_pico", 1), ("peak viewers", 1)],
    "stream_time_2020": [("horas_transmitidas", 60), ("stream time", 1)],  # interno: minutos
    "views_gained_2020": [("views_ganadas", 1), ("views gained", 1)],
    "watch_time_2020": [("horas_vistas", 60), ("watch time", 1)],  # opcional, interno: minutos
    "partnered": [("partner", 1), ("partnered", 1)],
    "mature": [("contenido_adulto", 1), ("mature", 1)],
    "language": [("idioma", 1), ("language", 1)],
    "first_category": [("categoria", 1), ("first category", 1)],
    "nombre": [("nombre", 1), ("screen name", 1)],
}
OBLIGATORIAS = ["followers_2020", "followers_gained_2020", "avg_viewers_2020",
                "peak_viewers_2020", "stream_time_2020", "views_gained_2020"]
NUMERICAS = ["followers_2020", "followers_gained_2020", "avg_viewers_2020", "peak_viewers_2020",
             "stream_time_2020", "views_gained_2020", "watch_time_2020"]


class ErrorDeEntrada(ValueError):
    """Los datos que llegaron no sirven (faltan columnas, hay textos donde van números, etc.)."""


class ServicioModelo:
    def __init__(self):
        self.modelo = joblib.load(RUTA_MODELO)
        with open(RUTA_META, encoding="utf-8") as f:
            self.meta = json.load(f)
        self.idiomas_top = self.meta["idiomas_top"]
        self.categorias_top = self.meta["categorias_top"]
        # predicciones del modelo sobre canales de referencia (para decir "queda mejor que el X%")
        self.referencia = np.sort(np.load(RUTA_REFERENCIA)) if RUTA_REFERENCIA.exists() else None

    # ---------- preparación de la entrada ----------
    def normalizar_entrada(self, df_crudo: pd.DataFrame) -> pd.DataFrame:
        """Pasa cualquier tabla con columnas conocidas al formato interno del modelo."""
        columnas = {c.strip().lower(): c for c in df_crudo.columns}
        salida = pd.DataFrame(index=df_crudo.index)
        faltan = []
        for interno, opciones in ALIAS_COLUMNAS.items():
            for nombre, factor in opciones:
                if nombre in columnas:
                    serie = df_crudo[columnas[nombre]]
                    if interno in NUMERICAS:
                        serie = pd.to_numeric(serie, errors="coerce") * factor
                    salida[interno] = serie
                    break
            else:
                if interno in OBLIGATORIAS:
                    faltan.append(ALIAS_COLUMNAS[interno][0][0])
        if faltan:
            raise ErrorDeEntrada("Faltan columnas obligatorias: " + ", ".join(faltan))

        malos = salida[OBLIGATORIAS].isna().any(axis=1)
        if malos.any():
            filas = [int(i) + 2 for i in salida.index[malos][:5]]
            raise ErrorDeEntrada(
                "Hay valores vacíos o que no son números en las columnas numéricas "
                f"(por ejemplo en las filas {filas} del archivo).")

        if "watch_time_2020" not in salida or salida["watch_time_2020"].isna().all():
            # estimación: en el dataset, el watch time es ~1,04 x viewers promedio x tiempo de stream
            salida["watch_time_2020"] = salida["avg_viewers_2020"] * salida["stream_time_2020"] * 1.04
        salida["watch_time_2020"] = salida["watch_time_2020"].fillna(
            salida["avg_viewers_2020"] * salida["stream_time_2020"] * 1.04)

        salida["partnered"] = salida.get("partnered", True)
        salida["mature"] = salida.get("mature", False)
        for col in ("partnered", "mature"):
            salida[col] = salida[col].map(_a_booleano)
        salida["language"] = salida.get("language", "English")
        salida["language"] = salida["language"].fillna("English").astype(str).str.strip()
        salida["first_category"] = salida.get("first_category", "Just Chatting")
        salida["first_category"] = salida["first_category"].fillna("Sin dato").astype(str).str.strip()
        salida["nombre"] = salida.get("nombre", pd.Series(index=salida.index, dtype=object))
        salida["nombre"] = salida["nombre"].fillna("").astype(str)
        return salida

    # ---------- predicción ----------
    def predecir(self, df_crudo: pd.DataFrame) -> pd.DataFrame:
        entrada = self.normalizar_entrada(df_crudo)
        X = construir_features(entrada, self.idiomas_top, self.categorias_top)
        pred = self.modelo.predict(X)  # = ln(seguidores_2024 / seguidores_2020)
        res = pd.DataFrame({
            "nombre": entrada["nombre"].values,
            "seguidores_actuales": entrada["followers_2020"].round().astype(int).values,
            "crecimiento_log": pred,
            "multiplicador": np.exp(pred),
            "crecimiento_pct": (np.exp(pred) - 1) * 100,
            "seguidores_estimados": (entrada["followers_2020"].values * np.exp(pred)).round().astype(int),
        })
        res["percentil_referencia"] = self._percentil(pred)
        res["categoria_oportunidad"] = res["percentil_referencia"].map(etiqueta_oportunidad)
        res["ranking"] = res["crecimiento_log"].rank(ascending=False, method="first").astype(int)
        return res.sort_values("ranking").reset_index(drop=True)

    def _percentil(self, pred):
        if self.referencia is None:
            return np.full(len(pred), np.nan)
        return np.searchsorted(self.referencia, pred, side="right") / len(self.referencia) * 100

    def info(self) -> dict:
        return {
            "modelo": self.meta["modelo"],
            "objetivo": self.meta["objetivo"],
            "entrenado_con_canales": self.meta["filas_entrenamiento"],
            "metricas_validacion_cruzada": self.meta["metricas_validacion_cruzada"],
            "idiomas": self.idiomas_top,
            "categorias": self.categorias_top,
        }


def _a_booleano(valor) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "1", "si", "sí", "yes", "y", "verdadero")
    return bool(valor)


def etiqueta_oportunidad(percentil) -> str:
    if pd.isna(percentil):
        return "Sin referencia"
    if percentil >= 90:
        return "Muy alta"
    if percentil >= 75:
        return "Alta"
    if percentil >= 50:
        return "Media"
    return "Baja"

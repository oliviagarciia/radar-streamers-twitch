"""Genera los archivos de apoyo a partir del dataset 2020 (se corre una sola vez).

1) modelo/referencia_predicciones.npy: lo que predice el modelo para los canales de 2020 que
   pasan el umbral de audiencia. Sirve para decir "este canal queda mejor que el X% de la referencia".
2) datos/streamers_ejemplo.csv: una lista chica de canales para probar el ranking en la demo.

Uso:  python preparar_referencia.py ruta/a/TwitchDataSet.csv
"""
import sys

import numpy as np
import pandas as pd

from model_service import ServicioModelo, RUTA_REFERENCIA

ruta_csv = sys.argv[1]
df = pd.read_csv(ruta_csv)
servicio = ServicioModelo()
umbral = servicio.meta["umbral_viewers_2020_percentil_25"]

ref = df[df["average viewers"] >= umbral].copy()
pred = servicio.predecir(ref.rename(columns={"screen name": "screen name"}))
np.save(RUTA_REFERENCIA, pred["crecimiento_log"].values)
print("Canales de referencia:", len(ref))

# ejemplo para la demo: 15 canales medianos, idiomas variados, mezclados al azar
candidatos = df[df["average viewers"].between(1300, 6000)
                & df["language"].isin(["Spanish", "English", "Portuguese", "French"])]
ejemplo = candidatos.sample(15, random_state=7)
plantilla = pd.DataFrame({
    "nombre": ejemplo["screen name"].values,
    "seguidores": ejemplo["followers"].values,
    "seguidores_ganados": ejemplo["followers gained"].values,
    "viewers_promedio": ejemplo["average viewers"].values,
    "viewers_pico": ejemplo["peak viewers"].values,
    "horas_transmitidas": (ejemplo["stream time"] / 60).round(1).values,
    "views_ganadas": ejemplo["views gained"].values,
    "partner": ejemplo["partnered"].values,
    "contenido_adulto": ejemplo["mature"].values,
    "idioma": ejemplo["language"].values,
    "categoria": ejemplo["first category"].values,
})
plantilla.to_csv("datos/streamers_ejemplo.csv", index=False)
print("Ejemplo guardado:", len(plantilla), "filas")

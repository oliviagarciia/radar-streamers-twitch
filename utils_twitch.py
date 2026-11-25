
import numpy as np
import pandas as pd

NUM_COLS = ["log_followers", "log_avg_viewers", "log_peak_viewers", "log_stream_time",
            "log_watch_time", "slog_followers_gained", "log_views_gained", "past_growth_rate"]
BIN_COLS = ["partnered", "mature"]
CAT_COLS = ["language_grp", "category_grp"]


def _a_binario(serie):
    return serie.map({True: 1, False: 0, "True": 1, "False": 0}).fillna(0).astype(int)


def construir_features(df, idiomas_top, categorias_top):
    # Arma las variables de entrada del modelo a partir de datos del corte 2020
    X = pd.DataFrame(index=df.index)
    X["log_followers"] = np.log1p(df["followers_2020"].clip(lower=0))
    X["log_avg_viewers"] = np.log1p(df["avg_viewers_2020"].clip(lower=0))
    X["log_peak_viewers"] = np.log1p(df["peak_viewers_2020"].clip(lower=0))
    X["log_stream_time"] = np.log1p(df["stream_time_2020"].clip(lower=0))
    X["log_watch_time"] = np.log1p(df["watch_time_2020"].clip(lower=0))
    ganados = df["followers_gained_2020"]
    X["slog_followers_gained"] = np.sign(ganados) * np.log1p(np.abs(ganados))
    X["log_views_gained"] = np.log1p(df["views_gained_2020"].clip(lower=0))

    inicio = df["followers_2020"] - ganados
    previo = np.where(inicio > 0, ganados / inicio, np.nan)
    X["past_growth_rate"] = pd.Series(previo, index=df.index).clip(lower=-1, upper=10).fillna(10)

    X["partnered"] = _a_binario(df["partnered"])
    X["mature"] = _a_binario(df["mature"])
    X["language_grp"] = df["language"].where(df["language"].isin(idiomas_top), "Other")
    categoria = df["first_category"].fillna("Sin dato")
    X["category_grp"] = categoria.where(categoria.isin(categorias_top), "Other")
    return X

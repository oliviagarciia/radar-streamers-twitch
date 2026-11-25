"""Interfaz web (Streamlit) que consume la API del modelo.

Cómo correrla (con la API ya andando en otra terminal):  streamlit run app_streamlit.py
La dirección de la API se toma de la variable de entorno API_URL (por defecto, la local).
"""
import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Radar de streamers de Twitch", page_icon="📈", layout="wide")


# ---------- comunicación con la API ----------
def llamar_api(metodo, ruta, **kwargs):
    """Hace el pedido a la API y devuelve (datos, mensaje_de_error)."""
    try:
        r = requests.request(metodo, API_URL + ruta, timeout=60, **kwargs)
    except requests.exceptions.RequestException:
        return None, ("No pude conectarme con el servicio del modelo. "
                      "Si recién se abrió la página, esperá unos segundos y probá de nuevo.")
    try:
        cuerpo = r.json()
    except ValueError:
        return None, f"Respuesta inesperada del servicio (código {r.status_code})."
    if r.status_code != 200:
        return None, cuerpo.get("error", "Ocurrió un error al calcular.")
    return cuerpo, None


@st.cache_data(ttl=300, show_spinner=False)
def traer_info():
    return llamar_api("GET", "/info")


EJEMPLO = {"nombre": "Canal de ejemplo", "seguidores": 45000, "seguidores_ganados": 30000,
           "viewers_promedio": 1800, "viewers_pico": 7500, "horas_transmitidas": 900,
           "views_ganadas": 1500000, "partner": True, "contenido_adulto": False,
           "idioma": "Spanish", "categoria": "Just Chatting"}
OTRA = "Otra (no está en la lista)"


def formato(n):
    return f"{int(n):,}".replace(",", ".")


# ---------- encabezado ----------
st.title("📈 Radar de streamers de Twitch")
st.markdown("Estimá **cuánto se espera que crezca un streamer** (en seguidores) y armá un "
            "**ranking de candidatos** para sponsorear antes de que se vuelvan caros.")

info, error_info = traer_info()
if error_info:
    st.error(error_info)
    st.stop()

tab1, tab2, tab3 = st.tabs(["🎯 Un streamer", "📋 Ranking de varios (CSV)", "ℹ️ Sobre el modelo"])

# ---------- pestaña 1: un streamer ----------
with tab1:
    st.subheader("Cargá los datos del streamer")
    st.caption("Son los datos del último año del canal. Podés usar los valores de ejemplo para probar.")
    if st.button("Cargar ejemplo"):
        st.session_state["ej"] = True
    d = EJEMPLO if st.session_state.get("ej") else {}

    with st.form("form_streamer"):
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre del canal (opcional)", d.get("nombre", ""))
        seguidores = c1.number_input("Seguidores actuales", min_value=0, step=1000,
                                     value=d.get("seguidores", 20000))
        ganados = c1.number_input("Seguidores ganados en el año", step=500,
                                  value=d.get("seguidores_ganados", 5000),
                                  help="Puede ser negativo si perdió seguidores.")
        v_prom = c2.number_input("Viewers promedio por stream", min_value=0, step=50,
                                 value=d.get("viewers_promedio", 800))
        v_pico = c2.number_input("Viewers pico (máximo simultáneo)", min_value=0, step=100,
                                 value=d.get("viewers_pico", 3000))
        horas = c2.number_input("Horas transmitidas en el año", min_value=0.0, step=10.0,
                                value=float(d.get("horas_transmitidas", 600)))
        views = c3.number_input("Visualizaciones ganadas en el año", min_value=0, step=10000,
                                value=d.get("views_ganadas", 500000))
        idioma = c3.selectbox("Idioma", info["idiomas"] + ["Otro"],
                              index=info["idiomas"].index(d["idioma"]) if d.get("idioma") in info["idiomas"] else 0)
        categoria = c3.selectbox("Categoría principal", info["categorias"] + [OTRA],
                                 index=info["categorias"].index(d["categoria"]) if d.get("categoria") in info["categorias"] else 0)
        c4, c5, _ = st.columns(3)
        partner = c4.checkbox("Es partner de Twitch", value=d.get("partner", True))
        adulto = c5.checkbox("Contenido para mayores (mature)", value=d.get("contenido_adulto", False))
        enviar = st.form_submit_button("Calcular crecimiento esperado", type="primary")

    if enviar:
        payload = {"nombre": nombre, "seguidores": int(seguidores), "seguidores_ganados": int(ganados),
                   "viewers_promedio": float(v_prom), "viewers_pico": float(v_pico),
                   "horas_transmitidas": float(horas), "views_ganadas": int(views), "partner": partner,
                   "contenido_adulto": adulto, "idioma": "Other" if idioma == "Otro" else idioma,
                   "categoria": "Other" if categoria == OTRA else categoria}
        with st.spinner("Consultando el modelo..."):
            res, err = llamar_api("POST", "/predecir", json=payload)
        if err:
            st.error(err)
        else:
            st.session_state["ultimo"] = res

    res = st.session_state.get("ultimo")
    if res:
        st.divider()
        titulo = res["nombre"] or "El streamer"
        st.subheader(f"Resultado: {titulo}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Crecimiento esperado", f"+{res['crecimiento_pct']:,.0f}%".replace(",", "."))
        m2.metric("Seguidores hoy → estimados", f"{formato(res['seguidores_actuales'])} → {formato(res['seguidores_estimados'])}")
        m3.metric("Queda mejor que el", f"{res['percentil_referencia']:.0f}% de los canales")
        m4.metric("Oportunidad", res["categoria_oportunidad"])
        st.progress(min(max(res["percentil_referencia"] / 100, 0.0), 1.0))
        st.info("El crecimiento se estima a unos 4 años, como lo aprendió el modelo (2020 → 2024). "
                "Sirve para **ordenar candidatos**, no como una garantía: el resultado es una estimación.")

# ---------- pestaña 2: ranking ----------
with tab2:
    st.subheader("Subí una lista de streamers y obtené el ranking")
    st.markdown("El archivo **CSV** necesita estas columnas: `seguidores`, `seguidores_ganados`, "
                "`viewers_promedio`, `viewers_pico`, `horas_transmitidas`, `views_ganadas`. "
                "Opcionales: `nombre`, `partner`, `contenido_adulto`, `idioma`, `categoria`.")
    try:
        with open("datos/streamers_ejemplo.csv", "rb") as f:
            plantilla = f.read()
        st.download_button("Descargar archivo de ejemplo", plantilla, "streamers_ejemplo.csv", "text/csv")
    except FileNotFoundError:
        plantilla = None

    archivo = st.file_uploader("Archivo CSV", type=["csv"])
    usar_ejemplo = plantilla is not None and st.checkbox("Usar el archivo de ejemplo (15 canales)")
    contenido = archivo.getvalue() if archivo else (plantilla if usar_ejemplo else None)

    if contenido is not None and st.button("Armar ranking", type="primary"):
        with st.spinner("Calculando..."):
            res, err = llamar_api("POST", "/ranking/csv", files={"archivo": ("lista.csv", contenido, "text/csv")})
        if err:
            st.error(err)
        else:
            st.session_state["ranking"] = pd.DataFrame(res["resultados"])

    tabla = st.session_state.get("ranking")
    if tabla is not None:
        st.divider()
        top = st.slider("Mostrar los primeros", 1, len(tabla), min(10, len(tabla)))
        vista = tabla.head(top).rename(columns={
            "ranking": "Puesto", "nombre": "Canal", "seguidores_actuales": "Seguidores hoy",
            "crecimiento_pct": "Crecimiento esperado (%)", "seguidores_estimados": "Seguidores estimados",
            "percentil_referencia": "Mejor que el (%)", "categoria_oportunidad": "Oportunidad"})
        cols = ["Puesto", "Canal", "Seguidores hoy", "Crecimiento esperado (%)", "Seguidores estimados",
                "Mejor que el (%)", "Oportunidad"]
        st.dataframe(vista[cols], hide_index=True, use_container_width=True)
        st.bar_chart(vista.set_index("Canal")["Crecimiento esperado (%)"])
        st.download_button("Descargar ranking completo (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                           "ranking_streamers.csv", "text/csv")

# ---------- pestaña 3: sobre el modelo ----------
with tab3:
    m = info["metricas_validacion_cruzada"]
    st.subheader("Cómo funciona")
    st.markdown(f"""
- **Modelo:** {info['modelo']}, entrenado con **{info['entrenado_con_canales']} canales**.
- **Qué predice:** el crecimiento de seguidores entre 2020 y 2024, en logaritmo (`{info['objetivo']}`).
- **Qué devuelve esta página:** el crecimiento esperado y la posición del canal frente a otros canales de referencia.
- **Cómo se evaluó** (validación cruzada de 5 partes): error promedio (MAE) **{m['MAE (media)']}**, \
R² **{m['R2 (media)']}**, correlación de ranking (Spearman) **{m['Spearman']}**.
""")
    st.subheader("Límites que conviene tener presentes")
    st.markdown("""
- Son pocos datos y solo dos cortes en el tiempo (2020 y 2024).
- Solo vimos canales que llegaron al top 1000 de 2024 (sesgo de supervivencia).
- El modelo se apoya mucho en cuánto venía creciendo el canal: sigue la tendencia, no explica sus causas.
- No hay datos de chat ni de engagement.
- Es un **prototipo**: sirve para armar una lista corta de candidatos, no para asegurar resultados.
""")

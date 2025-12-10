import io
import requests
import pandas as pd
from datetime import datetime
from dateutil.parser import parse as parse_date
import streamlit as st

# ==============================
# CONFIGURACIÓN
# ==============================

URL_LOGIN = "https://web-sl.repman.co/v2/acceso/login"
URL_REPORTE = "https://repman.co/sl2/reportes/salidaHornoTurnos"  # si falla, se podría probar el host web-sl
CSV_SEP = ";"


# ==============================
# FUNCIONES
# ==============================

def iniciar_sesion(codigo: str, contrasena: str) -> requests.Session:
    """Login en repman con usuario / contraseña / centro CC06."""
    ses = requests.Session()

    payload = {
        "usuario": F011,
        "contrasena": 12345,
        "centro": "CC06",
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }

    resp = ses.post(URL_LOGIN, json=payload, headers=headers)

    if resp.status_code != 200:
        raise Exception(
            f"Error al hacer login. HTTP {resp.status_code}\n"
            f"Respuesta: {resp.text[:300]}"
        )

    return ses


def descargar_csv(ses: requests.Session) -> pd.DataFrame:
    """Descarga el CSV de salida de horno con la sesión autenticada y lo devuelve como DataFrame."""
    resp = ses.get(URL_REPORTE)

    if resp.status_code != 200:
        raise Exception(
            f"Error al descargar archivo. HTTP {resp.status_code}\n"
            f"Respuesta: {resp.text[:300]}"
        )

    # Leemos directamente desde memoria
    df = pd.read_csv(io.BytesIO(resp.content), sep=CSV_SEP)

    # Limpieza básica de tipos
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    if "turno" in df.columns:
        df["turno"] = pd.to_numeric(df["turno"], errors="coerce").astype("Int64")

    if "cantidad" in df.columns:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").astype("Int64")

    return df


def aplicar_filtros(
    df: pd.DataFrame,
    fecha_desde,
    fecha_hasta,
    turno,
    linea,
    codigo_sap,
) -> pd.DataFrame:

    df_fil = df.copy()

    if fecha_desde is not None:
        df_fil = df_fil[df_fil["fecha"] >= fecha_desde]

    if fecha_hasta is not None:
        df_fil = df_fil[df_fil["fecha"] <= fecha_hasta]

    if turno is not None and turno != "Todos":
        df_fil = df_fil[df_fil["turno"] == int(turno)]

    if linea:
        df_fil = df_fil[df_fil["linea"] == linea]

    if codigo_sap:
        df_fil = df_fil[df_fil["codigoSAP"] == codigo_sap]

    return df_fil


# ==============================
# APP STREAMLIT
# ==============================

st.set_page_config(page_title="Salida de Horno", layout="wide")

st.title("📦 Salida de Horno - Descarga y Filtro")

st.markdown(
    "Aplicación para descargar el reporte de **Salida de Horno por Turnos**, "
    "filtrarlo y exportar los resultados."
)

with st.form("login_y_filtros"):
    st.subheader("1️⃣ Credenciales de acceso")

    codigo = st.text_input("Código (usuario)", value="", max_chars=10)
    contrasena = st.text_input("Contraseña", type="password", value="")

    st.caption("El centro se usa fijo como **CC06** dentro de la app.")

    st.subheader("2️⃣ Filtros del reporte")

    col1, col2 = st.columns(2)

    with col1:
        fecha_desde = st.date_input("Fecha desde", value=None)
    with col2:
        fecha_hasta = st.date_input("Fecha hasta", value=None)

    turno = st.selectbox("Turno", options=["Todos", "1", "2", "3"])
    linea = st.text_input("Línea (ej: 'LV&PD', 'TQ', 'TZ AA')", value="")
    codigo_sap = st.text_input("Código SAP (ej: 'O14191035')", value="")

    ejecutar = st.form_submit_button("🔄 Descargar y filtrar")

if ejecutar:
    if not codigo or not contrasena:
        st.error("Por favor ingresa tu código y contraseña.")
    else:
        try:
            with st.spinner("Iniciando sesión..."):
                ses = iniciar_sesion(codigo, contrasena)

            with st.spinner("Descargando y leyendo CSV..."):
                df = descargar_csv(ses)

            # Convertimos fechas de date_input a datetime
            f_desde_dt = datetime.combine(fecha_desde, datetime.min.time()) if fecha_desde else None
            f_hasta_dt = datetime.combine(fecha_hasta, datetime.max.time()) if fecha_hasta else None

            df_filtrado = aplicar_filtros(
                df,
                fecha_desde=f_desde_dt,
                fecha_hasta=f_hasta_dt,
                turno=turno,
                linea=linea.strip() or None,
                codigo_sap=codigo_sap.strip() or None,
            )

            st.success(f"Registros totales: {len(df)} | Después de filtrar: {len(df_filtrado)}")

            if len(df_filtrado) == 0:
                st.warning("No hay datos con esos criterios.")
            else:
                st.subheader("📄 Tabla filtrada")
                st.dataframe(df_filtrado, use_container_width=True)

                # CSV para descargar
                csv_buffer = io.StringIO()
                df_filtrado.to_csv(csv_buffer, sep=CSV_SEP, index=False)
                csv_bytes = csv_buffer.getvalue().encode("utf-8")

                st.download_button(
                    label="⬇️ Descargar CSV filtrado",
                    data=csv_bytes,
                    file_name="salida_horno_turnos_filtrado.csv",
                    mime="text/csv",
                )

        except Exception as e:
            st.error(f"Ocurrió un error: {e}")

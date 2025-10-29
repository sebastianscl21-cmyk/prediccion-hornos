import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Configuración de la página ---
st.set_page_config(page_title="Predicción de salida de hornos", page_icon="🔥", layout="centered")
st.title("🔥 Predicción de salida de hornos")

# --- Paso 1: Ingreso de tiempos de cocción ---
st.markdown("### Paso 1️⃣ — Ingresar tiempos de cocción (en horas)")

col1, col2, col3, col4 = st.columns(4)
with col1:
    horno1 = st.number_input("Horno 1 (h)", min_value=0.0, step=0.1)
with col2:
    horno2 = st.number_input("Horno 2 (h)", min_value=0.0, step=0.1)
with col3:
    horno3 = st.number_input("Horno 3 (h)", min_value=0.0, step=0.1)
with col4:
    horno4 = st.number_input("Horno 4 (h)", min_value=0.0, step=0.1)

horno_tiempos = {1: horno1, 2: horno2, 3: horno3, 4: horno4}

st.write(f"**Tiempos ingresados:** H1 = {horno1} h | H2 = {horno2} h | H3 = {horno3} h | H4 = {horno4} h")

if any(v == 0 for v in horno_tiempos.values()):
    st.warning("⚠️ Ingresa todos los tiempos de cocción antes de continuar.")
    st.stop()

# --- Paso 2: Selección de turno ---
st.markdown("### Paso 2️⃣ — Selecciona el turno a analizar")

turno = st.selectbox(
    "Selecciona el turno:",
    ["6:00 a.m. – 2:00 p.m.", "2:00 p.m. – 10:00 p.m.", "10:00 p.m. – 6:00 a.m."]
)

if turno == "6:00 a.m. – 2:00 p.m.":
    hora_inicio, hora_fin = "06:00", "14:00"
elif turno == "10:00 p.m. – 6:00 a.m.":
    hora_inicio, hora_fin = "22:00", "06:00"
else:
    hora_inicio, hora_fin = "14:00", "22:00"

st.info(f"Analizando piezas que saldrán entre **{hora_inicio}** y **{hora_fin}**.")

# --- Paso 3: Cargar archivo ---
st.markdown("### Paso 3️⃣ — Cargar archivo de producción (.csv o .xlsx)")
archivo = st.file_uploader("Selecciona tu archivo", type=["csv", "xlsx", "xls"])

if archivo is not None:
    try:
        if archivo.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(archivo)
        else:
            try:
                df = pd.read_csv(archivo, sep=";")
            except Exception:
                archivo.seek(0)
                df = pd.read_csv(archivo, sep=",")
        df.columns = df.columns.str.strip()
    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        df = None
else:
    df = None

if df is not None:
    st.success(f"✅ Archivo cargado correctamente ({df.shape[0]} filas × {df.shape[1]} columnas)")
    st.dataframe(df.head(), use_container_width=True)

    columnas_necesarias = {"fechaCaptura", "hora", "horno", "cantidad", "material"}
    if not columnas_necesarias.issubset(df.columns):
        st.error(f"⚠️ El archivo debe contener las columnas: {', '.join(columnas_necesarias)}")
        st.stop()

    # --- Normalización del número de horno ---
    df["horno"] = df["horno"].astype(str).str.extract(r"(\d+)").astype(float)

    # --- Conversión robusta de fecha y hora ---
    def parse_hora(h):
        try:
            return datetime.strptime(str(h).strip(), "%H:%M").time()
        except:
            try:
                return datetime.strptime(str(h).strip(), "%H:%M:%S").time()
            except:
                return pd.NaT

    try:
        df["fechaCaptura"] = pd.to_datetime(df["fechaCaptura"].astype(str), errors="coerce")
        df["hora"] = df["hora"].apply(parse_hora)
    except Exception as e:
        st.error(f"❌ Error al convertir columnas de fecha u hora: {e}")
        st.stop()

    # --- Eliminar filas con formato inválido ---
    if df["fechaCaptura"].isna().any() or df["hora"].isna().any():
        st.warning("⚠️ Algunas filas tienen formato de fecha u hora no reconocido y serán omitidas.")
        df = df.dropna(subset=["fechaCaptura", "hora"])

    # --- Cálculo de hora de salida ---
    df["fechaHoraEntrada"] = [
        datetime.combine(fecha, hora) for fecha, hora in zip(df["fechaCaptura"], df["hora"])
    ]

    def calcular_salida(row):
        horno = int(row["horno"]) if not pd.isna(row["horno"]) else None
        tiempo_horno = horno_tiempos.get(horno, 0)
        return row["fechaHoraEntrada"] + timedelta(hours=tiempo_horno)

    with st.spinner("⏳ Calculando predicciones..."):
        df["fechaHoraSalida"] = df.apply(calcular_salida, axis=1)

        # --- Determinar rango horario ---
        def rango(fecha):
            inicio = datetime.combine(fecha, datetime.strptime(hora_inicio, "%H:%M").time())
            fin = datetime.combine(fecha, datetime.strptime(hora_fin, "%H:%M").time())
            # Si el rango pasa a la madrugada (p.ej. 22:00 – 06:00)
            if fin < inicio:
                fin += timedelta(days=1)
            return inicio, fin

        df["en_rango"] = df.apply(
            lambda x: rango(x["fechaCaptura"])[0] <= x["fechaHoraSalida"] <= rango(x["fechaCaptura"])[1],
            axis=1
        )

        df_salida = df[df["en_rango"]].copy()

    # --- Resultados ---
    if df_salida.empty:
        st.warning("⚠️ Ninguna producción tiene hora de salida dentro del turno seleccionado.")
    else:
        resumen = df_salida.groupby("material", as_index=False)["cantidad"].sum()
        resumen = resumen.rename(columns={"cantidad": f"Cantidad estimada ({hora_inicio}–{hora_fin})"})

        total_piezas = resumen.iloc[:, 1].sum()

        st.success("✅ Resultados de predicción")
        st.metric("Piezas estimadas", f"{total_piezas:,.0f}")
        st.dataframe(resumen, use_container_width=True)

        st.markdown("#### Detalle de lotes con hora de salida estimada:")
        st.dataframe(df_salida[["material", "horno", "cantidad", "fechaHoraSalida"]], use_container_width=True)

        # --- Botón de descarga ---
        st.download_button(
            "⬇️ Descargar resultados en CSV",
            resumen.to_csv(index=False).encode("utf-8"),
            file_name="prediccion_salida_hornos.csv",
            mime="text/csv"
        )
else:
    st.info("📂 Sube un archivo CSV o Excel para comenzar.")

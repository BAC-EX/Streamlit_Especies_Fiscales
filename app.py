# app.py — Streamlit app para el Validador de Documentos Fiscales SAR (HN)
# Deploy: streamlit run app.py  |  Streamlit Cloud: apunta a este archivo

import streamlit as st
import pandas as pd
import os
import time
import zipfile
import tempfile
from io import BytesIO
from core_processor import BacExValidator, BacExClient, BacExError, normalizar_dataframe

# ─────────────────────────────────────────────────────────────────────────────
# Config de página
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Validador SAR · Honduras",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Fondo general */
.stApp {
    background: #0F1117;
    color: #E8EAF0;
}

/* Header hero */
.hero {
    background: linear-gradient(135deg, #1a1f2e 0%, #0d1520 100%);
    border: 1px solid #1e3a5f;
    border-radius: 16px;
    padding: 40px 48px;
    margin-bottom: 32px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(0, 122, 255, 0.15) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-badge {
    display: inline-block;
    background: rgba(0, 122, 255, 0.15);
    color: #4DA3FF;
    border: 1px solid rgba(0, 122, 255, 0.3);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 16px;
}
.hero h1 {
    font-size: 36px;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0 0 10px 0;
    line-height: 1.2;
}
.hero p {
    font-size: 15px;
    color: #8B95A8;
    margin: 0;
    max-width: 520px;
    line-height: 1.6;
}

/* Cards de secciones */
.card {
    background: #161B27;
    border: 1px solid #1E2535;
    border-radius: 12px;
    padding: 28px;
    margin-bottom: 20px;
}
.card-title {
    font-size: 13px;
    font-weight: 600;
    color: #4DA3FF;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Métricas */
.metrics-row {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
}
.metric-card {
    flex: 1;
    background: #161B27;
    border: 1px solid #1E2535;
    border-radius: 12px;
    padding: 20px 24px;
    text-align: center;
}
.metric-value {
    font-size: 32px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1;
    margin-bottom: 6px;
}
.metric-label {
    font-size: 12px;
    color: #8B95A8;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.metric-total   .metric-value { color: #E8EAF0; }
.metric-ok      .metric-value { color: #30D158; }
.metric-fail    .metric-value { color: #FF453A; }
.metric-pending .metric-value { color: #FFD60A; }

/* Log de progreso */
.log-box {
    background: #0D1117;
    border: 1px solid #1E2535;
    border-radius: 8px;
    padding: 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #8B95A8;
    max-height: 220px;
    overflow-y: auto;
    line-height: 1.7;
}
.log-ok     { color: #30D158; }
.log-error  { color: #FF453A; }
.log-info   { color: #4DA3FF; }
.log-warn   { color: #FFD60A; }

/* Botón primario */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #007AFF, #0051D5);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 28px;
    width: 100%;
    transition: opacity 0.2s;
}
div[data-testid="stButton"] > button:hover {
    opacity: 0.85;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #161B27;
    border: 1px dashed #2A3650;
    border-radius: 12px;
    padding: 8px;
}

/* Radio buttons */
.stRadio > div { gap: 12px; }
.stRadio label {
    background: #161B27;
    border: 1px solid #1E2535;
    border-radius: 8px;
    padding: 10px 16px;
    cursor: pointer;
    font-size: 14px;
}

/* Progress bar */
.stProgress > div > div {
    background: linear-gradient(90deg, #007AFF, #30D158);
    border-radius: 4px;
}

/* Tabla de resultados */
[data-testid="stDataFrame"] {
    border: 1px solid #1E2535;
    border-radius: 10px;
    overflow: hidden;
}

/* Ocultar menú y footer de Streamlit */
#MainMenu, footer, header { visibility: hidden; }

/* Divider */
.divider {
    height: 1px;
    background: #1E2535;
    margin: 24px 0;
}

/* Status pill */
.pill {
    display: inline-block;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    font-weight: 600;
}
.pill-ok    { background: rgba(48,209,88,0.15);  color: #30D158; }
.pill-error { background: rgba(255,69,58,0.15);  color: #FF453A; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Estado de sesión
# ─────────────────────────────────────────────────────────────────────────────
if "logs"         not in st.session_state: st.session_state.logs        = []
if "completados"  not in st.session_state: st.session_state.completados = 0
if "fallidos"     not in st.session_state: st.session_state.fallidos    = 0
if "total"        not in st.session_state: st.session_state.total       = 0
if "procesando"   not in st.session_state: st.session_state.procesando  = False
if "excel_bytes"  not in st.session_state: st.session_state.excel_bytes = None
if "zip_bytes"    not in st.session_state: st.session_state.zip_bytes   = None
if "df_resultado" not in st.session_state: st.session_state.df_resultado = None


# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-badge">🇭🇳 SAR · Honduras</div>
    <h1>Validador de Documentos Fiscales</h1>
    <p>Cargá tu Excel con RTN, número de documento y fecha — el sistema valida cada uno contra el SAR y te devuelve los datos completos en segundos.</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT: dos columnas
# ─────────────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1.6], gap="large")

# ══════════════════════════════════════════════════════════════════════════════
# COLUMNA IZQUIERDA — Configuración
# ══════════════════════════════════════════════════════════════════════════════
with col_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📂 Archivo de entrada</div>', unsafe_allow_html=True)

    archivo = st.file_uploader(
        "Arrastrá o seleccioná tu Excel",
        type=["xlsx", "xls"],
        label_visibility="collapsed",
    )

    if archivo:
        try:
            df_preview = pd.read_excel(archivo)
            archivo.seek(0)
            st.success(f"✅ {len(df_preview)} filas cargadas")

            # Renombrar para preview si tiene el nombre viejo
            df_show = df_preview.rename(columns={"Clave referencia 3": "Nº documento"})
            cols_mostrar = [c for c in ["RTN", "Nº documento", "Fecha doc."] if c in df_show.columns]
            if cols_mostrar:
                st.dataframe(
                    df_show[cols_mostrar].head(5),
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Modo de salida ────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ Modo de salida</div>', unsafe_allow_html=True)

    modo = st.radio(
        "Elegí qué querés generar",
        options=["Solo Excel", "Excel + PDFs"],
        captions=[
            "Datos completos de cada documento en una planilla.",
            "Todo lo anterior + un PDF por documento (descargás un ZIP).",
        ],
        label_visibility="collapsed",
    )
    output_mode = "DATA" if modo == "Solo Excel" else "PDF"

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Botón ejecutar ────────────────────────────────────────────────────────
    ejecutar = st.button(
        "🚀  Validar documentos",
        disabled=archivo is None or st.session_state.procesando,
        use_container_width=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# COLUMNA DERECHA — Progreso y resultados
# ══════════════════════════════════════════════════════════════════════════════
with col_right:

    # Métricas
    st.markdown(f"""
    <div class="metrics-row">
        <div class="metric-card metric-total">
            <div class="metric-value">{st.session_state.total}</div>
            <div class="metric-label">Total</div>
        </div>
        <div class="metric-card metric-ok">
            <div class="metric-value">{st.session_state.completados}</div>
            <div class="metric-label">Completados</div>
        </div>
        <div class="metric-card metric-fail">
            <div class="metric-value">{st.session_state.fallidos}</div>
            <div class="metric-label">Fallidos</div>
        </div>
        <div class="metric-card metric-pending">
            <div class="metric-value">{max(st.session_state.total - st.session_state.completados - st.session_state.fallidos, 0)}</div>
            <div class="metric-label">Pendientes</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Barra de progreso
    progress_placeholder = st.empty()
    if st.session_state.total > 0:
        pct = (st.session_state.completados + st.session_state.fallidos) / st.session_state.total
        progress_placeholder.progress(pct)
    else:
        progress_placeholder.progress(0.0)

    # Log
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📋 Log de actividad</div>', unsafe_allow_html=True)
    log_placeholder = st.empty()

    def _render_log():
        if not st.session_state.logs:
            log_placeholder.markdown(
                '<div class="log-box" style="color:#3A4558;">Esperando inicio del proceso...</div>',
                unsafe_allow_html=True,
            )
        else:
            lines = "".join(st.session_state.logs[-30:])   # últimas 30 líneas
            log_placeholder.markdown(
                f'<div class="log-box">{lines}</div>',
                unsafe_allow_html=True,
            )

    _render_log()
    st.markdown('</div>', unsafe_allow_html=True)

    # Descargas
    if st.session_state.excel_bytes:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title" style="font-size:13px;color:#30D158;">⬇️ Descargas listas</div>', unsafe_allow_html=True)

        dcol1, dcol2 = st.columns(2)
        with dcol1:
            st.download_button(
                label="📊 Descargar Excel",
                data=st.session_state.excel_bytes,
                file_name=f"SAR_Resultados_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with dcol2:
            if st.session_state.zip_bytes:
                st.download_button(
                    label="📦 Descargar PDFs (ZIP)",
                    data=st.session_state.zip_bytes,
                    file_name=f"SAR_PDFs_{time.strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

    # Tabla de resultados
    if st.session_state.df_resultado is not None:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title" style="font-size:13px;">📄 Vista previa de resultados</div>', unsafe_allow_html=True)
        st.dataframe(
            st.session_state.df_resultado,
            use_container_width=True,
            hide_index=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str, tipo: str = "info"):
    iconos = {"ok": "✅", "error": "❌", "info": "·", "warn": "⚠️"}
    clases = {"ok": "log-ok", "error": "log-error", "info": "log-info", "warn": "log-warn"}
    icono  = iconos.get(tipo, "·")
    clase  = clases.get(tipo, "log-info")
    ts     = time.strftime("%H:%M:%S")
    st.session_state.logs.append(
        f'<span class="{clase}">[{ts}] {icono} {msg}</span><br>'
    )


if ejecutar and archivo is not None:
    # Reset
    st.session_state.logs        = []
    st.session_state.completados = 0
    st.session_state.fallidos    = 0
    st.session_state.excel_bytes = None
    st.session_state.zip_bytes   = None
    st.session_state.df_resultado = None
    st.session_state.procesando  = True

    try:
        df_input = pd.read_excel(archivo)
        st.session_state.total = len(df_input)
        _log(f"Archivo cargado: {len(df_input)} documentos a procesar", "info")
        _render_log()

        # Directorio temporal para PDFs
        with tempfile.TemporaryDirectory() as tmp_dir:
            client    = BacExClient()
            validator = BacExValidator(
                output_folder=tmp_dir,
                output_mode=output_mode,
                client=client,
            )

            # Barra y métricas en tiempo real
            prog_bar  = progress_placeholder
            metricas  = col_right

            def on_progress(index, total, mensaje, estado):
                st.session_state.total = total
                if estado == "Éxito":
                    st.session_state.completados += 1
                    _log(f"Fila {index+1}/{total} — {mensaje}", "ok")
                elif estado in ("Fallido", "Error"):
                    st.session_state.fallidos += 1
                    _log(f"Fila {index+1}/{total} — {mensaje}", "error")
                else:
                    _log(f"Fila {index+1}/{total} — {mensaje}", "info")
                _render_log()
                pct = (st.session_state.completados + st.session_state.fallidos) / max(total, 1)
                progress_placeholder.progress(min(pct, 1.0))

            ruta_excel = validator.procesar_dataframe(df_input, on_progress)

            # Leer el Excel generado
            with open(ruta_excel, "rb") as f:
                st.session_state.excel_bytes = f.read()

            st.session_state.df_resultado = pd.read_excel(ruta_excel)

            # Si hay PDFs, empaquetar en ZIP
            if output_mode == "PDF":
                pdfs = [f for f in os.listdir(tmp_dir) if f.endswith(".pdf")]
                if pdfs:
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for pdf in pdfs:
                            zf.write(os.path.join(tmp_dir, pdf), pdf)
                    st.session_state.zip_bytes = zip_buffer.getvalue()
                    _log(f"{len(pdfs)} PDFs empaquetados en ZIP", "ok")
                else:
                    _log("No se generaron PDFs (¿ningún documento válido?)", "warn")

        completados = st.session_state.completados
        fallidos    = st.session_state.fallidos
        _log(f"Proceso finalizado — {completados} OK · {fallidos} fallidos", "ok")

    except BacExError as e:
        _log(f"Error del API: {e}", "error")
        st.error(str(e))
    except Exception as e:
        _log(f"Error inesperado: {e}", "error")
        st.error(str(e))
    finally:
        st.session_state.procesando = False
        _render_log()
        progress_placeholder.progress(1.0)
        st.rerun()
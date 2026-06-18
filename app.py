# app.py — Validador SAR Honduras · Streamlit con Login + Diseño Premium
import streamlit as st
import pandas as pd
import os, time, zipfile, tempfile, hashlib
from io import BytesIO
from core_processor import BacExValidator, BacExClient, BacExError

# ─── Página ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ValidaSAR · Honduras",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Usuarios (cambiar por DB o secrets en producción) ───────────────────────
def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

USERS = {
    "admin":   {"password": _hash("admin123"),  "nombre": "Administrador", "rol": "admin"},
    "usuario": {"password": _hash("valida123"), "nombre": "Analista",      "rol": "user"},
}

# ─── CSS + Animaciones ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #080C14; color: #C9D1E0; }
#MainMenu, footer, header { visibility: hidden; }
section[data-testid="stSidebar"] { display: none; }

/* ── Partículas de fondo ── */
.particles {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(ellipse 80% 60% at 20% 10%, rgba(0,100,255,.08) 0%, transparent 60%),
        radial-gradient(ellipse 60% 80% at 80% 80%, rgba(0,210,120,.06) 0%, transparent 60%),
        radial-gradient(ellipse 40% 40% at 50% 50%, rgba(120,0,255,.04) 0%, transparent 60%);
    animation: drift 12s ease-in-out infinite alternate;
}
@keyframes drift {
    0%   { transform: scale(1)    translateY(0px); }
    100% { transform: scale(1.04) translateY(-18px); }
}

/* ── LOGIN ── */
.login-wrap {
    min-height: 100vh; display: flex; align-items: center;
    justify-content: center; position: relative; z-index: 1;
    animation: fadeIn .5s ease;
}
@keyframes fadeIn { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:none; } }
@keyframes slideUp { from { opacity:0; transform:translateY(24px); } to { opacity:1; transform:none; } }
@keyframes pulse-ring {
    0%   { box-shadow: 0 0 0 0   rgba(0,122,255,.4); }
    70%  { box-shadow: 0 0 0 14px rgba(0,122,255,0);  }
    100% { box-shadow: 0 0 0 0   rgba(0,122,255,0);   }
}

.login-card {
    background: rgba(16,22,36,.92);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 24px;
    padding: 52px 48px 44px;
    width: 420px;
    backdrop-filter: blur(20px);
    box-shadow: 0 32px 80px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.04);
}
.login-logo {
    width: 64px; height: 64px;
    background: linear-gradient(135deg,#007AFF,#00C6FF);
    border-radius: 20px;
    display: flex; align-items: center; justify-content: center;
    font-size: 30px; margin: 0 auto 24px;
    animation: pulse-ring 2.5s infinite;
    box-shadow: 0 8px 32px rgba(0,122,255,.35);
}
.login-title { font-size: 26px; font-weight: 700; color: #fff; text-align: center; margin-bottom: 6px; }
.login-sub   { font-size: 14px; color: #5A6880; text-align: center; margin-bottom: 36px; }
.login-error {
    background: rgba(255,59,48,.12); border: 1px solid rgba(255,59,48,.3);
    border-radius: 10px; padding: 12px 16px; font-size: 13px; color: #FF6B6B;
    margin-top: 14px; text-align: center; animation: slideUp .3s ease;
}

/* ── Inputs Streamlit override ── */
.stTextInput input {
    background: rgba(255,255,255,.05) !important;
    border: 1px solid rgba(255,255,255,.1) !important;
    border-radius: 10px !important; color: #E0E7F0 !important;
    padding: 14px 16px !important; font-size: 14px !important;
    transition: border-color .2s, box-shadow .2s !important;
}
.stTextInput input:focus {
    border-color: #007AFF !important;
    box-shadow: 0 0 0 3px rgba(0,122,255,.18) !important;
    outline: none !important;
}
.stTextInput label { color: #8B95A8 !important; font-size: 12px !important; font-weight: 600 !important; letter-spacing: .06em !important; text-transform: uppercase !important; }

div[data-testid="stButton"] > button {
    background: linear-gradient(135deg,#007AFF 0%,#0051D5 100%) !important;
    color: #fff !important; border: none !important;
    border-radius: 12px !important; font-weight: 700 !important;
    font-size: 15px !important; padding: 14px !important;
    width: 100% !important; margin-top: 8px !important;
    box-shadow: 0 4px 20px rgba(0,122,255,.4) !important;
    transition: transform .15s, box-shadow .15s, opacity .15s !important;
}
div[data-testid="stButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 28px rgba(0,122,255,.55) !important;
}
div[data-testid="stButton"] > button:active { transform: translateY(0) !important; }

/* ── TOPBAR ── */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 32px; margin-bottom: 32px;
    background: rgba(12,18,30,.8); border-bottom: 1px solid rgba(255,255,255,.06);
    backdrop-filter: blur(12px); position: sticky; top: 0; z-index: 100;
    animation: fadeIn .4s ease;
}
.topbar-brand { display: flex; align-items: center; gap: 12px; }
.topbar-icon  {
    width: 38px; height: 38px; background: linear-gradient(135deg,#007AFF,#00C6FF);
    border-radius: 10px; display: flex; align-items: center; justify-content: center;
    font-size: 18px; box-shadow: 0 4px 14px rgba(0,122,255,.4);
}
.topbar-name  { font-size: 17px; font-weight: 700; color: #fff; }
.topbar-sub   { font-size: 12px; color: #5A6880; }
.topbar-user  {
    display: flex; align-items: center; gap: 10px;
    background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08);
    border-radius: 40px; padding: 7px 16px;
}
.topbar-avatar {
    width: 30px; height: 30px; background: linear-gradient(135deg,#30D158,#00C6FF);
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700; color: #fff;
}
.topbar-uname { font-size: 13px; font-weight: 600; color: #C9D1E0; }

/* ── MAIN CONTENT ── */
.main-content { padding: 0 32px 48px; animation: slideUp .4s ease; position: relative; z-index: 1; }

/* ── STEP GUIDE ── */
.steps-row { display: flex; gap: 12px; margin-bottom: 32px; }
.step-card {
    flex: 1; background: rgba(16,22,36,.7);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 14px; padding: 20px;
    transition: border-color .25s, transform .25s;
    cursor: default;
}
.step-card:hover { border-color: rgba(0,122,255,.4); transform: translateY(-3px); }
.step-num  { font-size: 11px; font-weight: 700; color: #007AFF; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.step-icon { font-size: 26px; margin-bottom: 10px; }
.step-title{ font-size: 14px; font-weight: 600; color: #E0E7F0; margin-bottom: 4px; }
.step-desc { font-size: 12px; color: #5A6880; line-height: 1.5; }

/* ── CARDS ── */
.card {
    background: rgba(16,22,36,.7);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 16px; padding: 28px; margin-bottom: 20px;
    transition: border-color .2s;
}
.card:hover { border-color: rgba(255,255,255,.1); }
.card-title {
    font-size: 11px; font-weight: 700; color: #007AFF;
    text-transform: uppercase; letter-spacing: .1em;
    margin-bottom: 18px; display: flex; align-items: center; gap: 8px;
}

/* ── MÉTRICAS ── */
.metrics-row { display: flex; gap: 14px; margin-bottom: 24px; }
.metric-card {
    flex: 1; border-radius: 14px; padding: 20px;
    background: rgba(16,22,36,.7); border: 1px solid rgba(255,255,255,.06);
    text-align: center; transition: transform .2s;
}
.metric-card:hover { transform: scale(1.03); }
.metric-value {
    font-size: 34px; font-weight: 800; font-family: 'JetBrains Mono', monospace;
    line-height: 1; margin-bottom: 6px;
    background: var(--c); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.metric-label { font-size: 11px; color: #5A6880; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; }
.m-total   { --c: linear-gradient(135deg,#C9D1E0,#8B95A8); }
.m-ok      { --c: linear-gradient(135deg,#30D158,#00C6FF); }
.m-fail    { --c: linear-gradient(135deg,#FF453A,#FF9F0A); }
.m-pending { --c: linear-gradient(135deg,#FFD60A,#FF9F0A); }

/* ── LOG ── */
.log-box {
    background: #060A10; border: 1px solid rgba(255,255,255,.05);
    border-radius: 10px; padding: 16px 18px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
    max-height: 240px; overflow-y: auto; line-height: 1.8;
}
.log-box::-webkit-scrollbar { width: 4px; }
.log-box::-webkit-scrollbar-thumb { background: #1E2535; border-radius: 4px; }
.l-ok   { color: #30D158; } .l-err  { color: #FF453A; }
.l-info { color: #4DA3FF; } .l-warn { color: #FFD60A; }
.l-dim  { color: #3A4558; }

/* ── PROGRESS ── */
.stProgress > div > div {
    background: linear-gradient(90deg, #007AFF, #30D158, #00C6FF) !important;
    border-radius: 4px !important;
    background-size: 200% 100% !important;
    animation: shimmer 2s linear infinite !important;
}
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

/* ── DOWNLOAD BUTTONS ── */
.dl-section {
    background: linear-gradient(135deg, rgba(0,122,255,.08), rgba(48,209,88,.06));
    border: 1px solid rgba(0,122,255,.2);
    border-radius: 14px; padding: 24px; margin-top: 16px;
    animation: slideUp .4s ease;
}
.dl-title { font-size: 13px; font-weight: 700; color: #30D158; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }

div[data-testid="stDownloadButton"] > button {
    background: rgba(255,255,255,.05) !important;
    border: 1px solid rgba(255,255,255,.12) !important;
    border-radius: 10px !important; color: #C9D1E0 !important;
    font-weight: 600 !important; font-size: 13px !important;
    padding: 12px !important; width: 100% !important;
    transition: background .2s, border-color .2s, transform .15s !important;
}
div[data-testid="stDownloadButton"] > button:hover {
    background: rgba(0,122,255,.15) !important;
    border-color: rgba(0,122,255,.4) !important;
    transform: translateY(-2px) !important;
}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {
    background: rgba(16,22,36,.5) !important;
    border: 2px dashed rgba(0,122,255,.25) !important;
    border-radius: 14px !important;
    transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: rgba(0,122,255,.5) !important; }

/* ── RADIO ── */
.stRadio > div { gap: 10px; }
.stRadio [data-testid="stMarkdownContainer"] p { color: #8B95A8 !important; font-size: 12px !important; }

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] { border: 1px solid rgba(255,255,255,.06) !important; border-radius: 12px !important; overflow: hidden !important; }

/* ── SUCCESS BANNER ── */
.success-banner {
    background: linear-gradient(135deg, rgba(48,209,88,.12), rgba(0,198,255,.08));
    border: 1px solid rgba(48,209,88,.25); border-radius: 14px;
    padding: 20px 24px; margin-bottom: 20px; animation: slideUp .4s ease;
    display: flex; align-items: center; gap: 16px;
}
.success-icon { font-size: 32px; }
.success-text h3 { font-size: 16px; font-weight: 700; color: #30D158; margin-bottom: 4px; }
.success-text p  { font-size: 13px; color: #5A6880; }

/* ── DIVIDER ── */
.div { height: 1px; background: rgba(255,255,255,.06); margin: 24px 0; }

/* ── LOGOUT BUTTON ── */
.logout-btn > div[data-testid="stButton"] > button {
    background: rgba(255,59,48,.1) !important;
    border: 1px solid rgba(255,59,48,.2) !important;
    color: #FF453A !important; box-shadow: none !important;
    padding: 8px 18px !important; font-size: 13px !important;
    margin-top: 0 !important; width: auto !important;
}
</style>

<div class="particles"></div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
defaults = {
    "logged_in": False, "username": "", "nombre": "",
    "logs": [], "completados": 0, "fallidos": 0, "total": 0,
    "procesando": False, "excel_bytes": None, "zip_bytes": None,
    "df_resultado": None, "proceso_ok": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────
def show_login():
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown("""
    <div class="login-card">
        <div class="login-logo">🧾</div>
        <div class="login-title">ValidaSAR</div>
        <div class="login-sub">Validador de Documentos Fiscales · Honduras</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        usuario  = st.text_input("Usuario", placeholder="tu_usuario")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        submit   = st.form_submit_button("Iniciar sesión →", use_container_width=True)

        if submit:
            user_data = USERS.get(usuario)
            if user_data and user_data["password"] == _hash(password):
                st.session_state.logged_in = True
                st.session_state.username  = usuario
                st.session_state.nombre    = user_data["nombre"]
                st.rerun()
            else:
                st.markdown(
                    '<div class="login-error">⚠️ Usuario o contraseña incorrectos</div>',
                    unsafe_allow_html=True,
                )
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
def show_app():
    nombre  = st.session_state.nombre
    inicial = nombre[0].upper()

    # ── TOPBAR ───────────────────────────────────────────────────────────────
    tc1, tc2 = st.columns([1, 1])
    with tc1:
        st.markdown(f"""
        <div class="topbar-brand" style="padding:14px 0 14px 8px">
            <div class="topbar-icon">🧾</div>
            <div>
                <div class="topbar-name">ValidaSAR</div>
                <div class="topbar-sub">Servicio de Administración de Rentas · HN</div>
            </div>
        </div>""", unsafe_allow_html=True)
    with tc2:
        ucol1, ucol2 = st.columns([3, 1])
        with ucol1:
            st.markdown(f"""
            <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;padding-top:12px">
                <div class="topbar-avatar">{inicial}</div>
                <div class="topbar-uname">{nombre}</div>
            </div>""", unsafe_allow_html=True)
        with ucol2:
            st.markdown('<div class="logout-btn">', unsafe_allow_html=True)
            if st.button("Salir"):
                for k in defaults:
                    st.session_state[k] = defaults[k]
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="main-content">', unsafe_allow_html=True)

    # ── GUÍA DE PASOS ────────────────────────────────────────────────────────
    st.markdown("""
    <div class="steps-row">
        <div class="step-card">
            <div class="step-num">Paso 01</div>
            <div class="step-icon">📂</div>
            <div class="step-title">Cargá tu Excel</div>
            <div class="step-desc">El archivo debe tener RTN, número de documento y fecha de emisión.</div>
        </div>
        <div class="step-card">
            <div class="step-num">Paso 02</div>
            <div class="step-icon">⚙️</div>
            <div class="step-title">Elegí el modo</div>
            <div class="step-desc">Solo datos en Excel, o Excel más los PDFs de cada documento.</div>
        </div>
        <div class="step-card">
            <div class="step-num">Paso 03</div>
            <div class="step-icon">🚀</div>
            <div class="step-title">Ejecutá</div>
            <div class="step-desc">El sistema consulta el SAR documento por documento en tiempo real.</div>
        </div>
        <div class="step-card">
            <div class="step-num">Paso 04</div>
            <div class="step-icon">⬇️</div>
            <div class="step-title">Descargá</div>
            <div class="step-desc">Obtenés el Excel con todos los datos validados y los PDFs en un ZIP.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── DOS COLUMNAS ─────────────────────────────────────────────────────────
    col_l, col_r = st.columns([1, 1.55], gap="large")

    # ══ IZQUIERDA ════════════════════════════════════════════════════════════
    with col_l:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📂 Archivo de entrada</div>', unsafe_allow_html=True)

        archivo = st.file_uploader(
            "Arrastrá o seleccioná tu Excel (.xlsx)",
            type=["xlsx", "xls"],
            label_visibility="collapsed",
        )

        if archivo:
            try:
                df_prev = pd.read_excel(archivo)
                archivo.seek(0)
                df_show = df_prev.rename(columns={"Clave referencia 3": "Nº documento"})
                cols_ok = [c for c in ["RTN","Nº documento","Fecha doc."] if c in df_show.columns]

                st.markdown(f"""
                <div style="background:rgba(48,209,88,.08);border:1px solid rgba(48,209,88,.2);
                     border-radius:10px;padding:12px 16px;margin:12px 0;font-size:13px;color:#30D158">
                    ✅ &nbsp;{len(df_prev)} documentos listos para validar
                </div>""", unsafe_allow_html=True)

                if cols_ok:
                    st.dataframe(df_show[cols_ok].head(5), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")

        st.markdown('</div>', unsafe_allow_html=True)

        # Modo
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚙️ Modo de salida</div>', unsafe_allow_html=True)
        modo = st.radio(
            "modo",
            ["Solo Excel  🗂️", "Excel + PDFs  📦"],
            captions=[
                "Todos los datos validados en una planilla.",
                "Planilla + un PDF por documento en un ZIP.",
            ],
            label_visibility="collapsed",
        )
        output_mode = "DATA" if "Solo" in modo else "PDF"
        st.markdown('</div>', unsafe_allow_html=True)

        # Botón
        can_run = archivo is not None and not st.session_state.procesando
        ejecutar = st.button(
            "🚀  Iniciar validación" if not st.session_state.procesando else "⏳  Procesando...",
            disabled=not can_run,
            use_container_width=True,
        )

    # ══ DERECHA ══════════════════════════════════════════════════════════════
    with col_r:

        # Métricas
        total  = st.session_state.total
        comp   = st.session_state.completados
        fail   = st.session_state.fallidos
        pend   = max(total - comp - fail, 0)

        st.markdown(f"""
        <div class="metrics-row">
            <div class="metric-card m-total">
                <div class="metric-value">{total}</div>
                <div class="metric-label">Total</div>
            </div>
            <div class="metric-card m-ok">
                <div class="metric-value">{comp}</div>
                <div class="metric-label">Completados</div>
            </div>
            <div class="metric-card m-fail">
                <div class="metric-value">{fail}</div>
                <div class="metric-label">Fallidos</div>
            </div>
            <div class="metric-card m-pending">
                <div class="metric-value">{pend}</div>
                <div class="metric-label">Pendientes</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        prog_ph = st.empty()
        pct = (comp + fail) / max(total, 1) if total else 0
        prog_ph.progress(pct)

        # Log
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📋 Actividad en tiempo real</div>', unsafe_allow_html=True)
        log_ph = st.empty()

        def render_log():
            if not st.session_state.logs:
                log_ph.markdown(
                    '<div class="log-box"><span class="l-dim">Esperando inicio del proceso...</span></div>',
                    unsafe_allow_html=True)
            else:
                lines = "".join(st.session_state.logs[-40:])
                log_ph.markdown(f'<div class="log-box">{lines}</div>', unsafe_allow_html=True)

        render_log()
        st.markdown('</div>', unsafe_allow_html=True)

        # Éxito + Descargas
        if st.session_state.proceso_ok and st.session_state.excel_bytes:
            st.markdown(f"""
            <div class="success-banner">
                <div class="success-icon">🎉</div>
                <div class="success-text">
                    <h3>¡Validación completada!</h3>
                    <p>{comp} documentos procesados · {fail} fallidos</p>
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown('<div class="dl-section">', unsafe_allow_html=True)
            st.markdown('<div class="dl-title">⬇️ Tus archivos están listos</div>', unsafe_allow_html=True)
            dc1, dc2 = st.columns(2)
            with dc1:
                st.download_button(
                    "📊 Descargar Excel",
                    data=st.session_state.excel_bytes,
                    file_name=f"SAR_Resultados_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with dc2:
                if st.session_state.zip_bytes:
                    st.download_button(
                        "📦 Descargar PDFs (ZIP)",
                        data=st.session_state.zip_bytes,
                        file_name=f"SAR_PDFs_{time.strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )
                else:
                    st.markdown(
                        '<p style="font-size:12px;color:#3A4558;text-align:center;padding-top:12px">PDFs no solicitados</p>',
                        unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # Tabla de resultados
        if st.session_state.df_resultado is not None:
            st.markdown('<div class="div"></div>', unsafe_allow_html=True)
            st.markdown('<div class="card-title" style="font-size:11px;">📄 Resultados</div>', unsafe_allow_html=True)
            st.dataframe(st.session_state.df_resultado, use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)  # main-content

    # ── PROCESAMIENTO ─────────────────────────────────────────────────────────
    def log(msg, tipo="info"):
        ts = time.strftime("%H:%M:%S")
        cls = {"ok":"l-ok","error":"l-err","info":"l-info","warn":"l-warn"}.get(tipo,"l-dim")
        ico = {"ok":"✅","error":"❌","info":"›","warn":"⚠️"}.get(tipo,"·")
        st.session_state.logs.append(f'<span class="{cls}">[{ts}] {ico} {msg}</span><br>')

    if ejecutar and archivo is not None:
        st.session_state.logs        = []
        st.session_state.completados = 0
        st.session_state.fallidos    = 0
        st.session_state.excel_bytes = None
        st.session_state.zip_bytes   = None
        st.session_state.df_resultado = None
        st.session_state.proceso_ok  = False
        st.session_state.procesando  = True

        try:
            df_input = pd.read_excel(archivo)
            st.session_state.total = len(df_input)
            log(f"Cargados {len(df_input)} documentos — modo {output_mode}", "info")
            render_log()

            with tempfile.TemporaryDirectory() as tmp:
                validator = BacExValidator(
                    output_folder=tmp,
                    output_mode=output_mode,
                    client=BacExClient(),
                )

                def on_progress(index, total, mensaje, estado):
                    st.session_state.total = total
                    tipo = "ok" if estado == "Éxito" else ("error" if estado in ("Fallido","Error") else "info")
                    if estado == "Éxito":   st.session_state.completados += 1
                    elif estado in ("Fallido","Error"): st.session_state.fallidos += 1
                    log(f"[{index+1}/{total}] {mensaje}", tipo)
                    render_log()
                    pct = (st.session_state.completados + st.session_state.fallidos) / max(total,1)
                    prog_ph.progress(min(pct, 1.0))

                ruta_excel = validator.procesar_dataframe(df_input, on_progress)

                with open(ruta_excel, "rb") as f:
                    st.session_state.excel_bytes = f.read()
                st.session_state.df_resultado = pd.read_excel(ruta_excel)

                if output_mode == "PDF":
                    pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
                    if pdfs:
                        buf = BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                            for p in pdfs:
                                zf.write(os.path.join(tmp, p), p)
                        st.session_state.zip_bytes = buf.getvalue()
                        log(f"{len(pdfs)} PDFs empaquetados", "ok")
                    else:
                        log("No se generaron PDFs", "warn")

            st.session_state.proceso_ok = True
            log("¡Proceso completado exitosamente!", "ok")

        except BacExError as e:
            log(f"Error del API: {e}", "error")
            st.error(str(e))
        except Exception as e:
            log(f"Error inesperado: {e}", "error")
            st.error(str(e))
        finally:
            st.session_state.procesando = False
            render_log()
            prog_ph.progress(1.0)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login()
else:
    show_app()
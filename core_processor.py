# bacex_client.py
# ─────────────────────────────────────────────────────────────────────────────
# POST /api/SAR/validar      → datos del documento (pdfUrl viene vacío aquí)
# POST /api/SAR/validar-pdf  → genera y devuelve el PDF (o su URL)
# ─────────────────────────────────────────────────────────────────────────────

import os
import time
import json
import requests
import pandas as pd

BASE_URL = "https://bac-exrrhhapi.vesta-accelerate.com"

COLUMNAS_SALIDA = [
    "RTN",
    "No Documento Búsqueda",
    "Fecha Documento",
    "Nombre / Razón Social",
    "Nombre Comercial",
    "Teléfono",
    "Email",
    "Dirección Casa Matriz",
    "Dirección Establecimiento",
    "Nº Documento",
    "Estado Documento",
    "CAI",
    "Tipo Documento",
    "Modalidad",
    "Fecha Límite Emisión",
    "Rango Autorizado",
    "Documento Existe",
    "Documento Válido",
    "Fecha Sistema",
    "Estado_Proceso",
    "Detalle_Validacion",
]


class BacExError(Exception):
    pass


def _fecha_a_iso(valor) -> str:
    ts = pd.to_datetime(valor, errors="coerce", dayfirst=True)
    if pd.isna(ts):
        raise BacExError(f"Fecha inválida: {valor!r}")
    return ts.strftime("%Y-%m-%dT06:00:00.000Z")


def _fmt_fecha(valor) -> str:
    if not valor or str(valor) in ("N/A", "nan", "None", ""):
        return "N/A"
    ts = pd.to_datetime(valor, errors="coerce")
    return ts.strftime("%d/%m/%Y") if not pd.isna(ts) else str(valor)


def normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    renombres = {"Clave referencia 3": "Nº documento"}
    df = df.rename(columns={k: v for k, v in renombres.items() if k in df.columns})
    requeridas = ["RTN", "Nº documento", "Fecha doc."]
    faltan = [c for c in requeridas if c not in df.columns]
    if faltan:
        raise BacExError(
            f"Al DataFrame le faltan columnas: {faltan}.\n"
            f"Columnas presentes: {list(df.columns)}"
        )
    df["RTN"] = df["RTN"].astype(str).str.strip().str.zfill(14)
    df["Nº documento"] = df["Nº documento"].astype(str).str.strip()
    return df


def _normalizar(respuesta: dict) -> tuple:
    r = respuesta
    fila = {
        "RTN":                          r.get("rtn", "N/A"),
        "No Documento Búsqueda":        r.get("noDocumentoBusqueda", "N/A"),
        "Fecha Documento":              _fmt_fecha(r.get("fechaDocumento")),
        "Nombre / Razón Social":        r.get("nombreRazonSocial", "N/A"),
        "Nombre Comercial":             r.get("nombreComercial", "N/A"),
        "Teléfono":                     r.get("telefono", "N/A"),
        "Email":                        r.get("email", "N/A"),
        "Dirección Casa Matriz":        r.get("direccionCasaMatriz", "N/A"),
        "Dirección Establecimiento":    r.get("direccionEstablecimiento", "N/A"),
        "Nº Documento":                 r.get("numeroDocumento", "N/A"),
        "Estado Documento":             r.get("estadoDocumento", "N/A"),
        "CAI":                          r.get("cai", "N/A"),
        "Tipo Documento":               r.get("tipoDocumento", "N/A"),
        "Modalidad":                    r.get("modalidad", "N/A"),
        "Fecha Límite Emisión":         _fmt_fecha(r.get("fechaLimiteEmision")),
        "Rango Autorizado":             r.get("rangoAutorizado", "N/A"),
        "Documento Existe":             "Sí" if r.get("documentoExiste") else "No",
        "Documento Válido":             "Sí" if r.get("documentoValido") else "No",
        "Fecha Sistema":                r.get("fechaSistema", "N/A"),
        "Estado_Proceso":               r.get("estadoProceso", "N/A"),
        "Detalle_Validacion":           r.get("detalleValidacion", "N/A"),
    }
    es_valido = bool(r.get("documentoValido", False))
    return fila, es_valido


class BacExClient:
    def __init__(self, base_url=BASE_URL, timeout=90, max_retries=3):
        self.base_url    = base_url.rstrip("/")
        self.timeout     = timeout
        self.max_retries = max_retries
        self.session     = requests.Session()
        self.session.headers.update({
            "Accept":       "application/json",
            "Content-Type": "application/json",
        })
        self._cred = {}

    def set_bearer_token(self, token: str):
        self.session.headers["Authorization"] = f"Bearer {token}"

    def set_api_key(self, key: str, header: str = "X-Api-Key"):
        self.session.headers[header] = key

    def login(self, usuario: str, password: str, path="/api/Auth/login"):
        r = self.session.post(
            f"{self.base_url}/{path.lstrip('/')}",
            json={"usuario": usuario, "clave": password},
            timeout=self.timeout,
        )
        r.raise_for_status()
        token = r.json().get("token") or r.json().get("accessToken")
        if not token:
            raise BacExError(f"Login OK pero sin token: {r.json()}")
        self.set_bearer_token(token)
        self._cred = {"usuario": usuario, "password": password, "path": path}
        print("✅ Login en Bac-Ex OK")

    def _post(self, path: str, body: dict) -> requests.Response:
        url    = f"{self.base_url}/{path.lstrip('/')}"
        ultimo = None
        for intento in range(1, self.max_retries + 1):
            try:
                resp = self.session.post(url, json=body, timeout=self.timeout)
                if resp.status_code == 401 and self._cred:
                    print("  ↻ Token vencido, re-login...")
                    self.login(**self._cred)
                    resp = self.session.post(url, json=body, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                ultimo = e
                if intento < self.max_retries:
                    espera = 3 * intento
                    print(f"  ⚠️ Intento {intento} fallido, reintentando en {espera}s...")
                    time.sleep(espera)
        raise BacExError(f"Fallo POST {path} tras {self.max_retries} intentos: {ultimo}")

    def validar(self, rtn: str, no_documento: str, fecha_iso: str) -> dict:
        body = {
            "rtn":                 rtn,
            "noDocumentoBusqueda": no_documento,
            "fechaDocumento":      fecha_iso,
        }
        resp = self._post("/api/SAR/validar", body)
        try:
            return resp.json()
        except ValueError:
            return {"estadoProceso": "Error", "detalleValidacion": resp.text[:200]}

    def obtener_pdf(self, rtn: str, no_documento: str, fecha_iso: str,
                    ruta_salida: str) -> str:
        """
        POST /api/SAR/validar-pdf con el mismo body que /validar.
        Maneja 3 casos posibles de respuesta:
          A) PDF binario directo (Content-Type: application/pdf)
          B) JSON con pdfUrl → descarga desde esa URL
          C) JSON con base64
        """
        body = {
            "rtn":                 rtn,
            "noDocumentoBusqueda": no_documento,
            "fechaDocumento":      fecha_iso,
        }
        resp = self._post("/api/SAR/validar-pdf", body)
        ctype = resp.headers.get("Content-Type", "")

        print(f"  🔍 validar-pdf → Content-Type: {ctype} | Tamaño: {len(resp.content)} bytes")

        # Caso A: PDF binario directo
        if "application/pdf" in ctype or resp.content[:4] == b"%PDF":
            with open(ruta_salida, "wb") as f:
                f.write(resp.content)
            print(f"  ✅ PDF binario guardado directamente.")
            return ruta_salida

        # Casos B y C: respuesta JSON
        try:
            data = resp.json()
            print(f"  📋 JSON de validar-pdf: {json.dumps(data, ensure_ascii=False)[:400]}")
        except ValueError:
            raise BacExError(
                f"validar-pdf devolvió respuesta inesperada. "
                f"Content-Type: {ctype} | Inicio: {resp.content[:100]}"
            )

        # Caso B: tiene pdfUrl
        pdf_url = (data.get("pdfUrl") or data.get("PdfUrl") or
                   data.get("url") or data.get("urlPdf") or "")
        if pdf_url:
            print(f"  🔗 pdfUrl en validar-pdf: {pdf_url[:80]}")
            r2 = requests.get(pdf_url, timeout=self.timeout)
            if r2.status_code == 403:
                raise BacExError("URL del PDF expirada (403).")
            r2.raise_for_status()
            with open(ruta_salida, "wb") as f:
                f.write(r2.content)
            return ruta_salida

        # Caso C: base64
        import base64
        b64 = (data.get("pdfBase64") or data.get("base64") or
               data.get("archivo") or "")
        if b64:
            with open(ruta_salida, "wb") as f:
                f.write(base64.b64decode(b64))
            return ruta_salida

        raise BacExError(
            f"validar-pdf no devolvió PDF, URL ni base64. "
            f"Campos recibidos: {list(data.keys())}"
        )


class BacExValidator:
    """
    output_mode:
      "DATA" → solo Excel
      "PDF"  → Excel + llama a /api/SAR/validar-pdf por cada documento válido
    """

    def __init__(self, output_folder: str, output_mode: str = "DATA",
                 client: BacExClient = None):
        self.output_folder = output_folder
        self.output_mode   = output_mode
        self.client        = client or BacExClient()
        os.makedirs(self.output_folder, exist_ok=True)

    def procesar_dataframe(self, df: pd.DataFrame, on_progress_update):
        df    = normalizar_dataframe(df.copy())
        total = len(df)
        filas = []
        completados = fallidos = 0

        for index, row in df.iterrows():
            rtn    = str(row["RTN"])
            no_doc = str(row["Nº documento"])
            fecha  = row["Fecha doc."]

            on_progress_update(index, total, f"Procesando: RTN={rtn}  Doc={no_doc}", "Iniciando")
            print(f"\n─── Fila {index + 1}/{total}: RTN={rtn}  Doc={no_doc} ───")

            try:
                fecha_iso = _fecha_a_iso(fecha)

                # 1. Validar → datos del documento
                respuesta = self.client.validar(rtn, no_doc, fecha_iso)
                fila, es_valido = _normalizar(respuesta)

                # 2. PDF → llama a /validar-pdf solo si es modo PDF y doc es válido
                if self.output_mode == "PDF":
                    if es_valido:
                        fecha_str  = _fmt_fecha(fecha).replace("/", "-")
                        nombre_pdf = f"SAR_{no_doc}_{fecha_str}_{rtn}.pdf"
                        ruta_pdf   = os.path.join(self.output_folder, nombre_pdf)
                        try:
                            self.client.obtener_pdf(rtn, no_doc, fecha_iso, ruta_pdf)
                            fila["Estado_Proceso"]
                            print(f"  📄 PDF guardado: {nombre_pdf}")
                        except BacExError as e_pdf:
                            fila["Estado_Proceso"]
                            fila["Detalle_Validacion"] += f" | PDF: {e_pdf}"
                            print(f"  ⚠️  PDF falló: {e_pdf}")
                    else:
                        print("  ⚠️  Documento no válido, se omite la descarga del PDF.")

                filas.append(fila)
                completados += 1
                estado_ui = "Éxito" if es_valido else "Fallido"
                on_progress_update(index, total, fila["Estado_Proceso"], estado_ui)
                print(f"  ✅ {fila['Estado_Proceso']}")

            except Exception as e:
                fallidos += 1
                fila = {c: "N/A" for c in COLUMNAS_SALIDA}
                fila.update({
                    "RTN":                   rtn,
                    "No Documento Búsqueda": no_doc,
                    "Fecha Documento":       _fmt_fecha(fecha),
                    "Estado_Proceso":        "Error",
                    "Detalle_Validacion":    f"{e.__class__.__name__}: {str(e)[:150]}",
                })
                filas.append(fila)
                on_progress_update(index, total, f"Error: {e.__class__.__name__}", "Error")
                print(f"  ❌ Error: {e}")

        print(f"\n{'='*52}")
        print(f"✅ Completados: {completados}  |  ❌ Fallidos: {fallidos}  |  Total: {total}")
        return self._guardar_excel(filas)

    def _guardar_excel(self, filas: list) -> str:
        df = pd.DataFrame(filas)
        for c in COLUMNAS_SALIDA:
            if c not in df.columns:
                df[c] = "N/A"
        df = df[COLUMNAS_SALIDA].fillna("N/A")

        nombre = "SAR_Datos_Extraidos_" + time.strftime("%Y%m%d_%H%M%S") + ".xlsx"
        ruta   = os.path.join(self.output_folder, nombre)
        df.to_excel(ruta, index=False)
        print(f"\n📊 Excel generado: {ruta}")
        return ruta
# Validador de Documentos Fiscales SAR · Honduras

App Streamlit que valida documentos fiscales contra el SAR de Honduras vía API de Bac-Ex.

## Deploy en Streamlit Cloud (gratis)

1. Subí estos 3 archivos a un repo de GitHub:
   - `app.py`
   - `core_processor.py`
   - `requirements.txt`

2. Entrá a [share.streamlit.io](https://share.streamlit.io)

3. Conectá tu repo → Main file: `app.py` → Deploy

¡Listo! Streamlit Cloud te da un link público.

## Columnas requeridas en el Excel de entrada

| Columna | Descripción |
|---|---|
| `RTN` | RTN del emisor (14 dígitos) |
| `Nº documento` (o `Clave referencia 3`) | Número del documento fiscal |
| `Fecha doc.` | Fecha de emisión (DD/MM/AAAA) |

## Modos de salida

- **Solo Excel** → planilla con todos los datos validados
- **Excel + PDFs** → lo mismo + un PDF por documento en un ZIP descargable
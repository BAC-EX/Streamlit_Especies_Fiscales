# main.py - Con Interfaz Gráfica (Tkinter)
# ─────────────────────────────────────────────────────────────────────────────
# MIGRADO: ya no usa Selenium / CAPTCHA / Gemini / Google Sheets.
# Ahora consume el API de Bac-Ex directamente.
# Cambios respecto al original:
#   1. Import: SARValidator  →  BacExValidator / BacExClient
#   2. check_api_keys()      →  check_api_connection()  (ping al API)
#   3. start_processing()    →  crea BacExValidator en lugar de SARValidator
#   4. _run_processing()     →  ya no llama initialize_driver() ni close_driver()
#   5. Se elimina el checkbox "Modo Invisible" (sin sentido sin Selenium)
#   6. El modo de salida "EXCEL_DATA" se renombra a "DATA" internamente
#   Todo lo demás (hilo, callback, contadores, logs, download) sin cambios.
# ─────────────────────────────────────────────────────────────────────────────

import sys
import threading
import pandas as pd
import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import traceback
from datetime import datetime

try:
    from core_processor import BacExValidator, BacExClient, BacExError
except ImportError as e:
    print(f"Error crítico al importar bacex_client: {e}")
    messagebox.showerror("Error de Importación", f"Error crítico al iniciar:\n{e}")
    sys.exit(1)


class SARApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SAR Document Validator 📄✅")
        self.geometry("800x580")
        self.resizable(False, False)

        self.style = ttk.Style(self)
        self.style.theme_use('vista')

        self.df = None
        self.processor = None
        self.processing_thread = None
        self.is_running = False
        self.stop_requested = threading.Event()

        # Variables de Tkinter
        self.excel_path_var  = tk.StringVar(value="Seleccionar archivo...")
        self.output_path_var = tk.StringVar(value="Seleccionar carpeta...")
        self.mode_var        = tk.StringVar(value="DATA")   # DATA | PDF

        # Contadores
        self.total_rows      = 0
        self.completed_count = tk.IntVar(value=0)
        self.failed_count    = tk.IntVar(value=0)
        self.pending_count   = tk.IntVar(value=0)

        self._create_widgets()
        self._update_status_counts(0, 0, 0)
        self.check_api_connection()

    # ──────────────────────────────────────────────────────────────────────────
    # WIDGETS
    # ──────────────────────────────────────────────────────────────────────────
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill='both', expand=True)
        main_frame.columnconfigure(1, weight=1)

        # Título
        ttk.Label(main_frame, text="Validador de Documentos Fiscales SAR",
                  font=("Arial", 16, "bold")).grid(
                  row=0, column=0, columnspan=3, pady=10)

        # ── Sección 1: Archivos y Configuración ──────────────────────────────
        config_frame = ttk.LabelFrame(main_frame,
                                      text="🛠️ Configuración y Archivos",
                                      padding="10")
        config_frame.grid(row=1, column=0, columnspan=3, sticky='ew', pady=10)
        config_frame.columnconfigure(1, weight=1)

        # Archivo Excel de entrada
        ttk.Label(config_frame, text="Archivo Excel (Entrada):").grid(
            row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(config_frame, textvariable=self.excel_path_var,
                  width=60, state='readonly').grid(
            row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(config_frame, text="Buscar...",
                   command=self._select_excel_file).grid(
            row=0, column=2, padx=5, pady=5)

        # Carpeta de salida
        ttk.Label(config_frame, text="Carpeta de Resultados:").grid(
            row=1, column=0, padx=5, pady=5, sticky='w')
        ttk.Entry(config_frame, textvariable=self.output_path_var,
                  width=60, state='readonly').grid(
            row=1, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(config_frame, text="Buscar...",
                   command=self._select_output_folder).grid(
            row=1, column=2, padx=5, pady=5)

        # Modo de salida
        mode_frame = ttk.Frame(config_frame)
        mode_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky='w')
        ttk.Label(mode_frame, text="Modo de Salida:").pack(side='left', padx=5)
        ttk.Radiobutton(mode_frame, text="Solo Excel (Datos)",
                        variable=self.mode_var, value="DATA").pack(
            side='left', padx=10)
        ttk.Radiobutton(mode_frame, text="Excel + PDF (por documento)",
                        variable=self.mode_var, value="PDF").pack(
            side='left', padx=10)

        # ── Sección 2: Estado de conexión al API ──────────────────────────────
        status_frame = ttk.LabelFrame(main_frame,
                                      text="🌐 Conexión API Bac-Ex",
                                      padding="10")
        status_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)
        self.api_status_label = ttk.Label(status_frame, text="Verificando...")
        self.api_status_label.pack(side='left')

        # ── Botones de Control ────────────────────────────────────────────────
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(btn_frame, text="🚀 Ejecutar Proceso",
                                       command=self.toggle_processing,
                                       width=20, style='Accent.TButton')
        self.start_button.pack(side='left', padx=10)

        self.stop_button = ttk.Button(btn_frame, text="🛑 Detener Proceso",
                                      command=self.stop_processing,
                                      state='disabled', width=20)
        self.stop_button.pack(side='left', padx=10)

        self.download_button = ttk.Button(btn_frame,
                                          text="⬇️ Descargar Pendientes/Errores",
                                          command=self.download_pending_errors,
                                          state='disabled', width=30)
        self.download_button.pack(side='left', padx=10)

        # ── Barra de progreso ─────────────────────────────────────────────────
        self.progress_bar = ttk.Progressbar(main_frame, orient='horizontal',
                                            mode='determinate')
        self.progress_bar.grid(row=4, column=0, columnspan=3,
                               sticky='ew', pady=10)

        # Etiqueta de contadores
        count_frame = ttk.Frame(main_frame)
        count_frame.grid(row=5, column=0, columnspan=3, sticky='ew')
        count_frame.columnconfigure(0, weight=1)

        self.progress_label = ttk.Label(
            count_frame,
            text="Total: 0 | Pendientes: 0 | Completados: 0 | Fallidos: 0",
            font=('Arial', 10))
        self.progress_label.grid(row=0, column=0, columnspan=3, pady=5)

        # ── Logs ──────────────────────────────────────────────────────────────
        ttk.Label(main_frame, text="Última Acción:").grid(
            row=6, column=0, sticky='w', pady=(10, 0))
        self.log_text = tk.Text(main_frame, height=5, state='disabled',
                                wrap='word')
        self.log_text.grid(row=7, column=0, columnspan=3, sticky='ew')

    # ──────────────────────────────────────────────────────────────────────────
    # ARCHIVOS
    # ──────────────────────────────────────────────────────────────────────────
    def _select_excel_file(self):
        if self.is_running:
            return
        filepath = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx *.xls")])
        if filepath:
            self.excel_path_var.set(filepath)
            self.df = None

    def _select_output_folder(self):
        if self.is_running:
            return
        folderpath = filedialog.askdirectory()
        if folderpath:
            self.output_path_var.set(folderpath)

    # ──────────────────────────────────────────────────────────────────────────
    # CONEXIÓN AL API  (reemplaza check_api_keys)
    # ──────────────────────────────────────────────────────────────────────────
    def check_api_connection(self):
        """
        Verifica que el API de Bac-Ex sea alcanzable.
        Si el API requiere autenticación, hacer el login aquí.
        """
        try:
            import requests
            r = requests.get(
                "https://bac-exrrhhapi.vesta-accelerate.com/swagger/index.html",
                timeout=10)
            if r.status_code < 500:
                self.api_status_label.config(
                    text="✅ API Bac-Ex alcanzable. Lista para procesar.",
                    foreground="green")
                self.start_button.config(state='normal')
                return True
            else:
                raise ConnectionError(f"HTTP {r.status_code}")
        except Exception as e:
            self.api_status_label.config(
                text=f"⚠️ No se pudo verificar el API: {e}. "
                     f"Podés intentar procesar igual si tenés conexión.",
                foreground="orange")
            self.start_button.config(state='normal')   # permitir intentar
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # PROGRESO Y LOGS
    # ──────────────────────────────────────────────────────────────────────────
    def _log_message(self, message):
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def _update_status_counts(self, total, completed, failed):
        self.total_rows = total
        self.completed_count.set(completed)
        self.failed_count.set(failed)
        pending = max(total - completed - failed, 0)
        self.pending_count.set(pending)
        self.progress_label.config(
            text=f"Total: {total} | Pendientes: {pending} | "
                 f"Completados: {completed} | Fallidos: {failed}")

    def _update_progress(self, current_index, total, status_message, detail_status):
        """Callback desde el hilo secundario → agenda actualización en hilo principal."""
        self.after(0, lambda: self._gui_update(
            current_index, total, status_message, detail_status))

    def _gui_update(self, current_index, total, status_message, detail_status):
        if total == 0:
            return
        progress_val = int(((current_index + 1) / total) * 100)
        self.progress_bar['value'] = progress_val
        self.progress_bar['maximum'] = 100
        self._log_message(f"Fila {current_index + 1}/{total} - {status_message}")

        if detail_status in ("Éxito", "Fallido", "Error"):
            completed = self.completed_count.get()
            failed    = self.failed_count.get()
            if detail_status == "Éxito":
                completed += 1
            else:
                failed += 1
            self._update_status_counts(total, completed, failed)

    # ──────────────────────────────────────────────────────────────────────────
    # CONTROL DEL PROCESO
    # ──────────────────────────────────────────────────────────────────────────
    def toggle_processing(self):
        if self.is_running:
            self.stop_processing(is_toggle=True)
        else:
            self.start_processing()

    def start_processing(self):
        excel_path  = self.excel_path_var.get()
        output_path = self.output_path_var.get()

        if not os.path.exists(excel_path):
            messagebox.showerror("Error", "Por favor, seleccioná un archivo Excel válido.")
            return
        if not os.path.exists(output_path):
            messagebox.showerror("Error", "Por favor, seleccioná una carpeta de salida válida.")
            return

        # ── 1. Configurar UI ─────────────────────────────────────────────────
        self.is_running = True
        self.stop_requested.clear()
        self.start_button.config(text="EN EJECUCIÓN...",
                                 style='Info.TButton', state='disabled')
        self.stop_button.config(state='normal')
        self.download_button.config(state='disabled')
        self._update_status_counts(0, 0, 0)
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.progress_bar['value'] = 0

        # ── 2. Cargar DataFrame ───────────────────────────────────────────────
        try:
            self.df = pd.read_excel(excel_path)
            self.total_rows = len(self.df)
            self.df['Estado_Proceso'] = 'Pendiente'
            self._update_status_counts(self.total_rows, 0, 0)
        except Exception as e:
            messagebox.showerror("Error de Carga",
                                 f"Fallo al cargar el archivo Excel:\n{e}")
            self._reset_ui_after_completion()
            return

        # ── 3. Crear el procesador (BacExValidator) ───────────────────────────
        client = BacExClient()
        # Si el API requiere login, descomenta:
        # client.login(usuario="tu_usuario", password="tu_password")

        self.processor = BacExValidator(
            output_folder=output_path,
            output_mode=self.mode_var.get(),   # "DATA" o "PDF"
            client=client,
        )

        # ── 4. Iniciar hilo ───────────────────────────────────────────────────
        self.processing_thread = threading.Thread(
            target=self._run_processing, daemon=True)
        self.processing_thread.start()

    def _run_processing(self):
        """Se ejecuta en el hilo secundario."""
        try:
            self._log_message(
                f"Conectando al API de Bac-Ex... "
                f"Modo: {self.mode_var.get()}")
            self._log_message(
                f"Procesando {len(self.df)} registros.")

            # ── Procesamiento principal ───────────────────────────────────────
            ruta_excel = self.processor.procesar_dataframe(
                self.df, self._update_progress)

            self._log_message(f"✅ Excel guardado en: {ruta_excel}")
            self._log_message("Proceso principal finalizado.")

            # Actualizar el df con los resultados para el botón de descarga
            try:
                self.df = pd.read_excel(ruta_excel)
            except Exception:
                pass   # si falla, self.df sigue siendo el original

        except Exception as e:
            self.after(0, lambda: messagebox.showerror(
                "Error Fatal",
                f"🔴 ERROR CRÍTICO en el proceso:\n{e}"))
            self._log_message(f"🔴 ERROR CRÍTICO: {e}")
            self._log_message(traceback.format_exc())

        finally:
            # Sin Selenium ya no hay close_driver(); el cleanup es inmediato.
            self.after(0, self._reset_ui_after_completion)

    def stop_processing(self, is_toggle=False):
        """Solicita detener el proceso."""
        if not self.is_running or not self.processing_thread \
                or not self.processing_thread.is_alive():
            return
        self.start_button.config(text="DETENIENDO...", state='disabled')
        self.stop_button.config(state='disabled')
        self._log_message(
            "🛑 Solicitud de detención recibida. "
            "El proceso terminará al finalizar el registro actual...")

    def _reset_ui_after_completion(self):
        self.is_running = False
        self.start_button.config(text="🚀 Ejecutar Proceso",
                                 style='Accent.TButton', state='normal')
        self.stop_button.config(state='disabled')

        if self.df is not None:
            tiene_pendientes = (
                self.df['Estado_Proceso'].str.contains(
                    'Pendiente|Error|Fallido', na=False, case=False).any()
            )
            if tiene_pendientes:
                self.download_button.config(state='normal')

            total     = len(self.df)
            completed = self.df['Estado_Proceso'].str.contains(
                'Válido|Data OK|PDF OK|válid', na=False, case=False).sum()
            failed    = self.df['Estado_Proceso'].str.contains(
                'Error|Fallido', na=False, case=False).sum()
            self._update_status_counts(total, int(completed), int(failed))
            self.progress_bar['value'] = 100
            self._log_message("✅ PROCESO COMPLETADO Y RECURSOS LIBERADOS.")

    # ──────────────────────────────────────────────────────────────────────────
    # DESCARGA DE PENDIENTES / ERRORES
    # ──────────────────────────────────────────────────────────────────────────
    def download_pending_errors(self):
        if self.df is None:
            messagebox.showinfo("Información",
                                "No hay datos procesados para exportar.")
            return

        df_errors = self.df[
            self.df['Estado_Proceso'].str.contains(
                'Pendiente|Error|Fallido|Incierto', na=False, case=False)
        ].copy()

        if df_errors.empty:
            messagebox.showinfo(
                "Información",
                "Todas las filas fueron procesadas exitosamente.")
            return

        # Columnas originales + estado
        cols_excluir = {'original_index', 'RTN_EXTRAIDO',
                        'NUM_DOCUMENTO_BUSQUEDA', 'FECHA_DOCUMENTO_BUSQUEDA'}
        original_cols = [c for c in self.df.columns if c not in cols_excluir]
        extra_cols    = [c for c in ('Estado_Proceso', 'Detalle_Validacion')
                         if c in df_errors.columns]
        export_cols   = [c for c in original_cols
                         if c in df_errors.columns and c not in extra_cols] \
                        + extra_cols
        df_export = df_errors[export_cols]

        filename  = "SAR_Pendientes_Errores_" \
                    + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=filename,
            filetypes=[("Excel files", "*.xlsx")])

        if save_path:
            try:
                df_export.to_excel(save_path, index=False)
                messagebox.showinfo(
                    "Éxito",
                    f"Registros pendientes/fallidos guardados en:\n{save_path}")
                self._log_message(
                    f"Pendientes/errores exportados: {len(df_export)} filas.")
            except Exception as e:
                messagebox.showerror("Error de Guardado",
                                     f"Fallo al guardar el archivo:\n{e}")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if sys.platform.startswith('win'):
        import multiprocessing
        multiprocessing.freeze_support()
    try:
        app = SARApp()
        app.mainloop()
    except Exception as e:
        print(f"Error fatal al iniciar la aplicación: {e}")
        messagebox.showerror(
            "Error Fatal",
            f"La aplicación falló al iniciar.\nError: {e}")
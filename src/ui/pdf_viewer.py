"""
Visor Rápido de Documentos PDF integrado para Facturas, Honorarios y DTEs.
Renderizado de alta resolución con pypdfium2 / PIL, zoom interactivo,
navegación de páginas, rotación y opciones de guardado/impresión.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

try:
    import pypdfium2 as pdfium
    PDFIUM_DISPONIBLE = True
except ImportError:
    PDFIUM_DISPONIBLE = False

from .theme import (
    C_CANVAS,
    C_SIDEBAR,
    C_SURFACE,
    C_SURFACE_ALT,
    C_INPUT,
    C_BORDER,
    C_BORDER_FOCUS,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_DIM,
    C_PRIMARY,
    C_PRIMARY_HOV,
    C_SUCCESS,
    C_INFO,
    C_PURPLE,
)
from ..utils import abrir_archivo_o_carpeta


class VentanaVisorPDF(tk.Toplevel):
    """Ventana modal moderna para visualizar documentos PDF con zoom y herramientas."""

    def __init__(self, parent, ruta_pdf, doc_info=None):
        super().__init__(parent)
        self.ruta_pdf = ruta_pdf
        self.doc_info = doc_info or {}
        
        folio = self.doc_info.get("folio", "")
        proveedor = self.doc_info.get("razon_social") or self.doc_info.get("emisor") or self.doc_info.get("proveedor", "")
        tit_doc = f"Folio {folio} • {proveedor}" if folio else os.path.basename(ruta_pdf)
        
        self.title(f"Visor de Documento • {tit_doc}")
        self.geometry("980x820")
        self.minsize(680, 540)
        self.configure(bg=C_CANVAS)
        self.transient(parent)

        # Centrar relativo al padre
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 490
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 410
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

        # Variables de control
        self.pdf_doc = None
        self.total_paginas = 0
        self.pagina_actual = 0
        self.zoom_escala = 1.35
        self.rotacion = 0
        self._img_tk = None

        self.crear_interfaz()
        self.cargar_documento()

    def crear_interfaz(self):
        # 1. Barra Superior de Herramientas (Toolbar)
        tb = tk.Frame(self, bg=C_SIDEBAR, padx=12, pady=8, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        tb.pack(fill="x", side="top")

        # Info básica a la izquierda
        lbl_tit = tk.Label(
            tb,
            text=f"📄 {os.path.basename(self.ruta_pdf)}",
            font=("Segoe UI", 9, "bold"),
            bg=C_SIDEBAR,
            fg=C_TEXT_MAIN
        )
        lbl_tit.pack(side="left", padx=(0, 14))

        # Controles de Zoom
        tk.Button(
            tb,
            text="➖",
            font=("Segoe UI", 9),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.zoom_out
        ).pack(side="left", padx=(0, 2))

        self.lbl_zoom = tk.Label(
            tb,
            text=f"{int(self.zoom_escala * 100)}%",
            font=("Segoe UI", 8, "bold"),
            bg=C_SIDEBAR,
            fg=C_TEXT_MUTED,
            width=6
        )
        self.lbl_zoom.pack(side="left")

        tk.Button(
            tb,
            text="➕",
            font=("Segoe UI", 9),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.zoom_in
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            tb,
            text="Ajustar",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MUTED,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.zoom_ajustar
        ).pack(side="left", padx=(0, 10))

        # Paginación
        self.btn_prev_pag = tk.Button(
            tb,
            text="◀",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.pagina_anterior
        )
        self.btn_prev_pag.pack(side="left", padx=(0, 2))

        self.lbl_pag = tk.Label(
            tb,
            text="1 / 1",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR,
            fg=C_TEXT_MUTED
        )
        self.lbl_pag.pack(side="left", padx=4)

        self.btn_next_pag = tk.Button(
            tb,
            text="▶",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.pagina_siguiente
        )
        self.btn_next_pag.pack(side="left", padx=(0, 10))

        # Botones de Acción a la derecha
        tk.Button(
            tb,
            text="📂 Abrir Externo",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_INFO,
            relief="flat",
            highlightbackground=C_BORDER,
            highlightthickness=1,
            padx=8,
            pady=2,
            cursor="hand2",
            command=lambda: abrir_archivo_o_carpeta(self.ruta_pdf)
        ).pack(side="right", padx=(4, 0))

        tk.Button(
            tb,
            text="📁 Ver en Carpeta",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MUTED,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=lambda: abrir_archivo_o_carpeta(os.path.dirname(self.ruta_pdf))
        ).pack(side="right", padx=(4, 0))

        # 2. Barra de Información Contextual (si hay datos del documento)
        if self.doc_info:
            info_bar = tk.Frame(self, bg=C_SURFACE, padx=12, pady=6, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
            info_bar.pack(fill="x", side="top")

            folio = self.doc_info.get("folio", "-")
            tipo = self.doc_info.get("tipo_doc_nombre") or self.doc_info.get("tipo_doc", "-")
            fecha = self.doc_info.get("fecha_docto") or self.doc_info.get("fecha", "-")
            monto_tot = self.doc_info.get("monto_total") or self.doc_info.get("monto_liquido", 0)
            monto_str = f"${monto_tot:,}".replace(",", ".") if isinstance(monto_tot, (int, float)) else str(monto_tot)
            rz = self.doc_info.get("razon_social") or self.doc_info.get("emisor") or self.doc_info.get("proveedor", "-")
            rut = self.doc_info.get("rut_emisor") or self.doc_info.get("rut", "")

            txt_info = f"Tipo: {tipo}   |   Folio: {folio}   |   Fecha: {fecha}   |   Total: {monto_str}   |   {rz} ({rut})"
            tk.Label(info_bar, text=txt_info, font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(side="left")

        # 3. Área de Scroll y Visualización del Canvas
        main_container = tk.Frame(self, bg=C_CANVAS)
        main_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(main_container, bg="#080c16", highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        self.scroll_x = ttk.Scrollbar(main_container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.scroll_x.set, yscrollcommand=self.scroll_y.set)

        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Eventos de scroll del ratón
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def cargar_documento(self):
        if not os.path.exists(self.ruta_pdf):
            self.mostrar_error(f"El archivo PDF no existe en la ruta:\n{self.ruta_pdf}")
            return

        if not PDFIUM_DISPONIBLE:
            self.mostrar_error("Librería pypdfium2 no disponible. Puedes abrir el archivo externamente.")
            return

        try:
            self.pdf_doc = pdfium.PdfDocument(self.ruta_pdf)
            self.total_paginas = len(self.pdf_doc)
            self.pagina_actual = 0
            self.renderizar_pagina()
        except Exception as e:
            self.mostrar_error(f"Error al procesar el archivo PDF:\n{e}")

    def renderizar_pagina(self):
        if not self.pdf_doc or self.total_paginas == 0:
            return

        try:
            self.lbl_pag.config(text=f"{self.pagina_actual + 1} / {self.total_paginas}")
            self.lbl_zoom.config(text=f"{int(self.zoom_escala * 100)}%")

            pagina = self.pdf_doc[self.pagina_actual]
            # Renderizado nítido con pypdfium2
            bitmap = pagina.render(scale=self.zoom_escala, rotation=self.rotacion)
            pil_img = bitmap.to_pil()

            self._img_tk = ImageTk.PhotoImage(pil_img)

            self.canvas.delete("all")
            # Centrar la imagen en el canvas
            c_w = self.canvas.winfo_width() or 800
            img_w, img_h = pil_img.size
            pos_x = max(img_w // 2 + 20, c_w // 2)
            pos_y = img_h // 2 + 20

            self.canvas.create_image(pos_x, pos_y, image=self._img_tk)
            self.canvas.config(scrollregion=(0, 0, max(c_w, img_w + 40), img_h + 40))

        except Exception as e:
            self.mostrar_error(f"No se pudo renderizar la página:\n{e}")

    def zoom_in(self):
        if self.zoom_escala < 3.0:
            self.zoom_escala = round(self.zoom_escala + 0.2, 2)
            self.renderizar_pagina()

    def zoom_out(self):
        if self.zoom_escala > 0.5:
            self.zoom_escala = round(self.zoom_escala - 0.2, 2)
            self.renderizar_pagina()

    def zoom_ajustar(self):
        self.zoom_escala = 1.25
        self.renderizar_pagina()

    def pagina_anterior(self):
        if self.pagina_actual > 0:
            self.pagina_actual -= 1
            self.renderizar_pagina()

    def pagina_siguiente(self):
        if self.pagina_actual < self.total_paginas - 1:
            self.pagina_actual += 1
            self.renderizar_pagina()

    def _on_mousewheel(self, event):
        if event.state & 0x0004:  # Ctrl presionado -> Zoom
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:  # Scroll vertical normal
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def mostrar_error(self, mensaje):
        self.canvas.delete("all")
        self.canvas.create_text(
            400, 200,
            text=f"⚠️ {mensaje}",
            fill="#f43f5e",
            font=("Segoe UI", 11, "bold"),
            justify="center"
        )

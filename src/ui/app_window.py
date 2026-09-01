"""
Gestor Tributario Unificado:
1. Facturas y Registro de Compras (RCV) - SII
2. Boletas de Honorarios Electrónicas (BHE) - SII
3. Panel DTE y Facturas - Facturacion.cl (Desis)

Interfaz Moderna, Minimalista y Profesional con Barra Lateral (Sidebar).
"""

import os
import sys
import threading
import glob
import re
import csv
import json
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter.scrolledtext import ScrolledText

from ..utils import (
    obtener_ruta_base,
    obtener_ruta_appdata,
    cargar_variables_entorno,
    CONFIG_FILE,
    EMPRESAS_FILE,
    LISTA_EMPRESAS_DEFECTO,
    cargar_configuracion as utils_cargar_configuracion,
    guardar_configuracion as utils_guardar_configuracion,
    cargar_empresas as utils_cargar_empresas,
    guardar_empresas as utils_guardar_empresas,
    leer_credenciales_env,
    guardar_credenciales_env,
    VERSION_LOCAL,
)

DIRECTORIO_ACTUAL = obtener_ruta_base()
cargar_variables_entorno()

if DIRECTORIO_ACTUAL not in sys.path:
    sys.path.insert(0, DIRECTORIO_ACTUAL)

from src.core import rcv_engine as script
from src.core import bhe_engine as script_honorarios
from src.core import desis_engine as script_facturacion_cl
from src.ai import glosa_extractor as ai_context
from src.utils import verificar_actualizaciones_inicio, verificar_actualizaciones_manual
from .pdf_viewer import VentanaVisorPDF

# Activar escalado DPI nítido y AppUserModelID para Windows
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    import ctypes
    app_id = "sii.gestor.facturas.v2"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
except Exception:
    pass

# ==========================================================
# PALETA DE COLORES MODERNA (Obsidian / Deep Slate / Sidebar)
# ==========================================================
C_CANVAS       = "#080c16"  # Fondo base principal
C_SIDEBAR      = "#0d1424"  # Fondo de la barra lateral
C_SIDEBAR_CARD = "#121b30"  # Fondo de bloques en sidebar
C_SURFACE      = "#131c31"  # Fondo de tarjetas y paneles
C_SURFACE_ALT  = "#1a2540"  # Fondo secundario para cabeceras y cajas
C_INPUT        = "#0a0f1d"  # Fondo de campos de texto y combos
C_BORDER       = "#1e2a44"  # Bordes sutiles y limpios
C_BORDER_FOCUS = "#6366f1"  # Borde al enfocar

C_TEXT_MAIN    = "#f8fafc"  # Texto principal blanco nítido
C_TEXT_MUTED   = "#94a3b8"  # Texto secundario / etiquetas
C_TEXT_DIM     = "#64748b"  # Texto atenuado / hints

C_PRIMARY      = "#6366f1"  # Indigo primario
C_PRIMARY_HOV  = "#818cf8"  # Indigo hover
C_SUCCESS      = "#10b981"  # Verde esmeralda (Consultar / Éxito)
C_SUCCESS_HOV  = "#34d399"  # Verde hover
C_WARNING      = "#f59e0b"  # Ámbar (Pendientes / Retenciones)
C_DANGER       = "#f43f5e"  # Coral / Rojo (Desconexión / Errores)
C_INFO         = "#0ea5e9"  # Azul cielo (Facturas / Documentos)
C_PURPLE       = "#a855f7"  # Púrpura (IA / Monto Total)
C_TEAL         = "#14b8a6"  # Verde azulado (PDFs / Archivos)

LISTA_EMPRESAS_DEFECTO = [
    {"nombre": "BEALICE SPA", "rut": "76505297-1"},
    {"nombre": "PEDRO ANTONIO CONTRERAS CALDERON", "rut": "9696421-8"},
    {"nombre": "AUDIFONOS CHILE SPA", "rut": "77099672-4"},
    {"nombre": "COMUNICACIONES DIRECTAS CHILE SPA", "rut": "76299996-K"},
    {"nombre": "OKSALUD SPA", "rut": "76458359-0"},
    {"nombre": "V-ACTION SPA", "rut": "76360435-7"},
    {"nombre": "PUBLICIDAD CARLOS CORNEJO MORENO E.I.R.L.", "rut": "76696247-5"},
    {"nombre": "ASTRA COMS SPA", "rut": "77956457-6"},
    {"nombre": "WE-PROSPECT SPA", "rut": "77313675-0"},
    {"nombre": "DI PAOLA & ASOCIADOS CHILE S A", "rut": "96994760-9"},
    {"nombre": "PRODUCTORA DE EVENTOS YULIA SAVCHENKO EIRL", "rut": "76212375-4"},
    {"nombre": "COMUNICATIO SPA", "rut": "76941483-5"},
    {"nombre": "FRANCISCO DI PAOLA PUBLICIDAD E.I.R.L", "rut": "76493217-K"},
    {"nombre": "MEET SUPER CHILE SPA", "rut": "76410455-2"},
    {"nombre": "CARLOS ENRIQUE KULM CABELLO", "rut": "9323099-K"},
    {"nombre": "EIGHT MARKETING LAB SPA", "rut": "76231321-9"},
    {"nombre": "RODRIGO ALEJANDRO RETAMALES VIVANCO SERVICIOS TECNOLOGIA Y COMERCIO E.", "rut": "76234411-4"},
    {"nombre": "SYNAPTICA COACHING SPA", "rut": "78052127-9"},
    {"nombre": "SOCIEDAD DISTRIBUIDORA Y COMERCIALIZADORA LTI LIMITADA", "rut": "76510430-0"},
    {"nombre": "SERVICIOS DE COMUNICACIONES LATINOAMERICA SPA", "rut": "78019373-5"},
    {"nombre": "PORTONES AUTOMÁTICOS SPA", "rut": "78023923-9"},
    {"nombre": "COMERCIALIZADORA MORALES, MONTANER Y PÉREZ LIMITADA", "rut": "77872358-1"}
]


def abrir_archivo_o_carpeta(ruta):
    """Abre un archivo o directorio de forma segura en Windows, Linux o macOS."""
    if not ruta or not os.path.exists(ruta):
        return
    try:
        if sys.platform == "win32":
            os.startfile(ruta)
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", ruta])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", ruta])
    except Exception:
        pass


def parse_fecha_dt(fecha_str):
    """Convierte un string de fecha (DD/MM/AAAA o DD-MM-AAAA) a objeto datetime para ordenamiento."""
    if not fecha_str:
        return datetime.min
    try:
        solo_fecha = str(fecha_str).strip().split(" ")[0]
        sep = "/" if "/" in solo_fecha else "-"
        partes = solo_fecha.split(sep)
        if len(partes) == 3:
            return datetime(int(partes[2]), int(partes[1]), int(partes[0]))
    except Exception:
        pass
    return datetime.min


class AppSII(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"Gestor Tributario • SII & Facturación v{VERSION_LOCAL}")
        self.configure(bg=C_CANVAS)
        self.minsize(1180, 720)

        # Configurar icono de ventana y barra de tareas
        base_res = getattr(sys, '_MEIPASS', DIRECTORIO_ACTUAL)
        ico_path = os.path.join(base_res, "app_icon.ico")
        png_path = os.path.join(base_res, "app_icon.png")

        if not os.path.exists(ico_path):
            ico_path = os.path.join(DIRECTORIO_ACTUAL, "app_icon.ico")
        if not os.path.exists(png_path):
            png_path = os.path.join(DIRECTORIO_ACTUAL, "app_icon.png")

        if os.path.exists(ico_path):
            try:
                self.iconbitmap(default=os.path.abspath(ico_path))
            except Exception:
                try:
                    self.iconbitmap(os.path.abspath(ico_path))
                except Exception:
                    pass

        if os.path.exists(png_path):
            try:
                from PIL import Image, ImageTk
                self._app_icon_img = ImageTk.PhotoImage(Image.open(png_path))
                self.iconphoto(True, self._app_icon_img)
            except Exception:
                try:
                    self._app_icon_img = tk.PhotoImage(file=png_path)
                    self.iconphoto(True, self._app_icon_img)
                except Exception:
                    pass

        # Cargar lista de empresas
        self.empresas = self.cargar_empresas()

        # Cargar configuración guardada
        config = self.cargar_configuracion()
        self.correlativo_val = tk.IntVar(value=config.get("correlativo", 2000))
        self.contexto_val = tk.StringVar(value=config.get("contexto", ""))
        self.chk_usar_ia = tk.BooleanVar(value=config.get("usar_ia", True))
        self.gemini_api_key = config.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
        self.openai_api_key = config.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))

        # Empresa inicial
        rut_guardado = config.get("empresa_rut", script.RUT_EMPRESA or "")
        emp_inicial = None
        for emp in self.empresas:
            if rut_guardado and emp.get("rut", "").replace("-", "").replace(".", "").upper() == rut_guardado.replace("-", "").replace(".", "").upper():
                emp_inicial = emp
                break
        if not emp_inicial and self.empresas:
            emp_inicial = self.empresas[0]

        valor_inicial = f"{emp_inicial['nombre']}  •  {emp_inicial['rut']}" if emp_inicial else ""
        self.sel_empresa_str = tk.StringVar(value=valor_inicial)
        if emp_inicial:
            script.set_rut_empresa(emp_inicial["rut"])

        # Estado de ejecución y cancelación
        self.en_ejecucion = False
        self.cancelar_solicitado = False
        self.cancelar_hn_solicitado = False
        self.cancelar_fcl_solicitado = False
        self.modulo_activo = "facturas"  # "facturas", "honorarios", "facturacion_cl"
        self.opciones_avanzadas_visibles = False

        # Datos y carpeta de descargas de FACTURAS SII
        self.documentos = []
        self.documentos_visibles = []
        self.orden_columnas_asc = {}
        raw_download_dir = config.get("download_dir", script.DOWNLOAD_DIR)
        script.set_download_dir(raw_download_dir)
        self.download_dir = script.DOWNLOAD_DIR
        self.download_dir_var = tk.StringVar(value=self.download_dir)

        # Variables de BOLETAS DE HONORARIOS
        _env_rut_hn = os.getenv("RUT_EMPRESA_HN") or os.getenv("rut_empresa_hn") or (emp_inicial["rut"] if emp_inicial else "")
        _env_clave_hn = os.getenv("SII_CLAVE_HN") or os.getenv("sii_clave_hn") or (emp_inicial.get("clave_sii", "") if emp_inicial else "")
        self.hn_rut_empresa_var = tk.StringVar(value=config.get("rut_empresa_hn", _env_rut_hn))
        self.hn_clave_empresa_var = tk.StringVar(value=config.get("sii_clave_hn", _env_clave_hn))
        self.hn_ver_clave = tk.BooleanVar(value=False)

        _hoy = datetime.now()
        self.hn_sel_mes = tk.StringVar(value=script.NOMBRES_MESES[_hoy.month])
        self.hn_sel_anio = tk.StringVar(value=str(_hoy.year))
        self.hn_tipo_consulta = tk.StringVar(value="recibidas")
        self.hn_modo_headless = tk.BooleanVar(value=True)

        raw_hn_dir = config.get("download_dir_hn", self.download_dir)
        script_honorarios.gestor_honorarios.set_download_dir(raw_hn_dir)
        self.hn_download_dir = script_honorarios.gestor_honorarios.download_dir
        self.hn_download_dir_var = tk.StringVar(value=self.hn_download_dir)

        self.boletas_honorarios = []
        self.boletas_honorarios_visibles = []
        self.hn_orden_columnas_asc = {}
        self.hn_busqueda_texto = tk.StringVar()
        self.hn_criterio_orden = tk.StringVar(value="fecha_desc")
        self.hn_chk_usar_ia = tk.BooleanVar(value=config.get("hn_usar_ia", True))
        self.hn_contexto_val = tk.StringVar(value=config.get("hn_contexto", ""))

        # Variables de FACTURACION.CL
        _env_fcl_emp = os.getenv("FACTURACION_EMPRESA", "")
        _env_fcl_usr = os.getenv("FACTURACION_USUARIO", "")
        _env_fcl_pwd = os.getenv("FACTURACION_PASSWORD", "")
        self.fcl_empresa_var = tk.StringVar(value=config.get("facturacion_empresa", _env_fcl_emp))
        self.fcl_usuario_var = tk.StringVar(value=config.get("facturacion_usuario", _env_fcl_usr))
        self.fcl_password_var = tk.StringVar(value=config.get("facturacion_password", _env_fcl_pwd))
        self.fcl_ver_clave = tk.BooleanVar(value=False)

        self.fcl_sel_mes = tk.StringVar(value=script.NOMBRES_MESES[_hoy.month])
        self.fcl_sel_anio = tk.StringVar(value=str(_hoy.year))
        self.fcl_modo_headless = tk.BooleanVar(value=True)

        raw_fcl_dir = config.get("download_dir_fcl", self.download_dir)
        script_facturacion_cl.gestor_facturacion_cl.set_download_dir(raw_fcl_dir)
        self.fcl_download_dir = script_facturacion_cl.gestor_facturacion_cl.download_dir
        self.fcl_download_dir_var = tk.StringVar(value=self.fcl_download_dir)

        # Variables de IA y Glosa para Facturacion.cl
        self.fcl_chk_usar_ia = tk.BooleanVar(value=config.get("fcl_usar_ia", True))
        self.fcl_contexto_val = tk.StringVar(value=config.get("fcl_contexto", ""))
        self.fcl_system_prompt = config.get("fcl_system_prompt", "")

        self.fcl_documentos = []
        self.fcl_documentos_visibles = []
        self.fcl_orden_columnas_asc = {}
        self.fcl_busqueda_texto = tk.StringVar()
        self.fcl_criterio_orden = tk.StringVar(value="fecha_desc")
        self.fcl_tipo_doc_filtro = tk.StringVar(value="Todos")

        # Variables de estado generales
        self.sel_mes = tk.StringVar(value=script.NOMBRES_MESES[_hoy.month])
        self.sel_anio = tk.StringVar(value=str(_hoy.year))
        self.chk_registro = tk.BooleanVar(value=True)
        self.chk_pendientes = tk.BooleanVar(value=True)
        self.chk_reclamados = tk.BooleanVar(value=False)
        self.modo_headless = tk.BooleanVar(value=True)
        self.busqueda_texto = tk.StringVar()
        self.criterio_orden = tk.StringVar(value="fecha_desc")
        self.filtro_estado = tk.StringVar(value="Todos")

        # Centrar ventana
        self.centrar_ventana(ancho_deseado=1520, alto_deseado=880)
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_app)

        self.crear_estilos()
        self.crear_interfaz()
        self.actualizar_conteo_archivos()
        self.actualizar_conteo_archivos_hn()
        self.actualizar_conteo_archivos_fcl()

        # Comprobar si hay una nueva versión disponible en GitHub en segundo plano
        self.after(1200, lambda: verificar_actualizaciones_inicio(self, log_cb=self.log))

    def cargar_configuracion(self):
        return utils_cargar_configuracion()

    def guardar_configuracion(self):
        try:
            cfg = {
                "correlativo": self.correlativo_val.get(),
                "contexto": self.contexto_val.get(),
                "usar_ia": self.chk_usar_ia.get(),
                "gemini_api_key": self.gemini_api_key,
                "openai_api_key": self.openai_api_key,
                "download_dir": self.download_dir,
                "empresa_rut": script.RUT_EMPRESA,
                "rut_empresa_hn": self.hn_rut_empresa_var.get(),
                "sii_clave_hn": self.hn_clave_empresa_var.get(),
                "download_dir_hn": self.hn_download_dir,
                "hn_usar_ia": self.hn_chk_usar_ia.get(),
                "hn_contexto": self.hn_contexto_val.get(),
                "facturacion_empresa": self.fcl_empresa_var.get(),
                "facturacion_usuario": self.fcl_usuario_var.get(),
                "facturacion_password": self.fcl_password_var.get(),
                "download_dir_fcl": self.fcl_download_dir,
                "fcl_usar_ia": self.fcl_chk_usar_ia.get(),
                "fcl_contexto": self.fcl_contexto_val.get(),
                "fcl_system_prompt": self.fcl_system_prompt
            }
            utils_guardar_configuracion(cfg)
        except Exception:
            pass

    def cargar_empresas(self):
        return utils_cargar_empresas()

    def guardar_empresas(self, lista_empresas):
        return utils_guardar_empresas(lista_empresas)

    def obtener_empresa_obj(self):
        val = self.sel_empresa_str.get()
        if "•" in val:
            rut = val.split("•")[1].strip()
        else:
            rut = val.strip()
        rut_clean = rut.replace("-", "").replace(".", "").upper()
        for emp in self.empresas:
            if emp.get("rut", "").replace("-", "").replace(".", "").upper() == rut_clean:
                return emp
        return {"nombre": val, "rut": rut, "clave_sii": ""}

    def obtener_empresa_actual(self):
        return self.obtener_empresa_obj()

    def al_cambiar_empresa(self, event=None):
        emp = self.obtener_empresa_actual()
        rut = emp.get("rut", "")
        if rut:
            script.set_rut_empresa(rut)
            self.guardar_configuracion()
            self.sincronizar_empresa_a_honorarios()
            self.log(f"Empresa activa: {emp.get('nombre', 'Empresa')} (RUT: {rut})")
            self.actualizar_subtitulo_vistas()

    def sincronizar_empresa_a_honorarios(self):
        emp = self.obtener_empresa_actual()
        if emp:
            rut = emp.get("rut", "")
            clave = emp.get("clave_sii", "")
            if rut:
                self.hn_rut_empresa_var.set(rut)
            if clave:
                self.hn_clave_empresa_var.set(clave)
            else:
                sii_rut_env = (os.getenv("SII_RUT") or "").replace(".", "").replace("-", "").strip().upper()
                rut_limpio = rut.replace(".", "").replace("-", "").strip().upper()
                if sii_rut_env and rut_limpio == sii_rut_env and os.getenv("SII_CLAVE"):
                    self.hn_clave_empresa_var.set(os.getenv("SII_CLAVE"))
                elif os.getenv("SII_CLAVE_HN"):
                    self.hn_clave_empresa_var.set(os.getenv("SII_CLAVE_HN"))
                else:
                    self.hn_clave_empresa_var.set("")

    def actualizar_combobox_empresas(self):
        valores = [f"{e['nombre']}  •  {e['rut']}" for e in self.empresas]
        self.cb_empresa.configure(values=valores)

    def abrir_gestion_empresas(self):
        ventana = tk.Toplevel(self)
        ventana.title("Catálogo de Empresas")
        ventana.geometry("740x480")
        ventana.configure(bg=C_CANVAS)
        ventana.transient(self)
        ventana.grab_set()

        pnl = tk.Frame(ventana, bg=C_SURFACE, padx=16, pady=16)
        pnl.pack(fill="both", expand=True, padx=12, pady=12)

        lbl_t = tk.Label(pnl, text="Catálogo de Empresas Registradas", font=("Segoe UI", 12, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN)
        lbl_t.pack(anchor="w", pady=(0, 10))

        tree_frame = tk.Frame(pnl, bg=C_SURFACE)
        tree_frame.pack(fill="both", expand=True, pady=(0, 12))

        cols = ("idx", "nombre", "rut", "clave")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        tree.heading("idx", text="#")
        tree.heading("nombre", text="Razón Social / Nombre")
        tree.heading("rut", text="RUT")
        tree.heading("clave", text="Clave SII (BHE)")

        tree.column("idx", width=40, anchor="center")
        tree.column("nombre", width=360, anchor="w")
        tree.column("rut", width=130, anchor="center")
        tree.column("clave", width=130, anchor="center")

        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        def refrescar_tree():
            for it in tree.get_children():
                tree.delete(it)
            for i, emp in enumerate(self.empresas, 1):
                clave_mask = "••••••••" if emp.get("clave_sii") else ("(Sin clave)" if emp.get("rut") != "76410455-2" else "•••••••• (Meet)")
                tree.insert("", "end", iid=str(i-1), values=(i, emp["nombre"], emp["rut"], clave_mask))

        refrescar_tree()

        btn_bar = tk.Frame(pnl, bg=C_SURFACE)
        btn_bar.pack(fill="x")

        def agregar_empresa():
            nom = simpledialog.askstring("Nueva Empresa", "Razón Social / Nombre:", parent=ventana)
            if not nom or not nom.strip():
                return
            rut = simpledialog.askstring("Nueva Empresa", "RUT de la Empresa (ej: 76123456-7):", parent=ventana)
            if not rut or not rut.strip():
                return
            clave = simpledialog.askstring("Clave SII (Opcional)", "Clave SII para Honorarios (opcional):", parent=ventana) or ""
            nueva = {"nombre": nom.strip().upper(), "rut": rut.strip().upper(), "clave_sii": clave.strip()}
            self.empresas.append(nueva)
            self.guardar_empresas(self.empresas)
            self.actualizar_combobox_empresas()
            refrescar_tree()
            self.log(f"Nueva empresa agregada: {nueva['nombre']} ({nueva['rut']})")

        def editar_empresa():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Editar", "Selecciona una empresa en la lista.", parent=ventana)
                return
            idx = int(sel[0])
            emp = self.empresas[idx]
            nom = simpledialog.askstring("Editar Empresa", "Razón Social / Nombre:", initialvalue=emp["nombre"], parent=ventana)
            if not nom or not nom.strip():
                return
            rut = simpledialog.askstring("Editar Empresa", "RUT de la Empresa:", initialvalue=emp["rut"], parent=ventana)
            if not rut or not rut.strip():
                return
            clave = simpledialog.askstring("Editar Clave SII", "Clave SII para Boletas de Honorarios:", initialvalue=emp.get("clave_sii", ""), parent=ventana)
            if clave is None:
                clave = emp.get("clave_sii", "")

            self.empresas[idx] = {"nombre": nom.strip().upper(), "rut": rut.strip().upper(), "clave_sii": clave.strip()}
            self.guardar_empresas(self.empresas)
            self.actualizar_combobox_empresas()
            refrescar_tree()
            self.log(f"Empresa editada: {nom.strip().upper()} ({rut.strip().upper()})")

        def eliminar_empresa():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Eliminar", "Selecciona una empresa en la lista.", parent=ventana)
                return
            idx = int(sel[0])
            emp = self.empresas[idx]
            if messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que deseas eliminar a {emp['nombre']} ({emp['rut']})?", parent=ventana):
                self.empresas.pop(idx)
                self.guardar_empresas(self.empresas)
                self.actualizar_combobox_empresas()
                refrescar_tree()
                self.log(f"Empresa eliminada: {emp['nombre']}")

        def restaurar_defecto():
            if messagebox.askyesno("Restaurar Lista", "¿Deseas restaurar las 22 empresas predeterminadas?", parent=ventana):
                self.empresas = [dict(e) for e in LISTA_EMPRESAS_DEFECTO]
                self.guardar_empresas(self.empresas)
                self.actualizar_combobox_empresas()
                refrescar_tree()
                self.log("Lista de empresas restaurada.")

        def seleccionar_y_cerrar():
            sel = tree.selection()
            if sel:
                idx = int(sel[0])
                emp = self.empresas[idx]
                val_str = f"{emp['nombre']}  •  {emp['rut']}"
                self.sel_empresa_str.set(val_str)
                self.al_cambiar_empresa()
            ventana.destroy()

        tk.Button(btn_bar, text="➕ Agregar", font=("Segoe UI", 9, "bold"), bg=C_SUCCESS, fg="#022c22", activebackground=C_SUCCESS_HOV, relief="flat", padx=10, pady=4, cursor="hand2", command=agregar_empresa).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="✏️ Editar", font=("Segoe UI", 9, "bold"), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=10, pady=4, cursor="hand2", command=editar_empresa).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="🗑️ Eliminar", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_DANGER, activebackground="#374151", relief="flat", padx=8, pady=4, cursor="hand2", command=eliminar_empresa).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="🔄 Restaurar 22", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, activebackground="#374151", relief="flat", padx=8, pady=4, cursor="hand2", command=restaurar_defecto).pack(side="left", padx=(0, 6))
        tk.Button(btn_bar, text="✔️ Seleccionar y Cerrar", font=("Segoe UI", 9, "bold"), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=12, pady=4, cursor="hand2", command=seleccionar_y_cerrar).pack(side="right")

    def centrar_ventana(self, ancho_deseado=1520, alto_deseado=880):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ancho = min(ancho_deseado, sw)
        alto = min(alto_deseado, sh)
        x = max(0, (sw - ancho) // 2)
        y = max(0, (sh - alto) // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

    def crear_estilos(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        self.option_add("*selectBackground", C_PRIMARY)
        self.option_add("*selectForeground", "#ffffff")
        self.option_add("*insertBackground", C_TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.background", C_SURFACE)
        self.option_add("*TCombobox*Listbox.foreground", C_TEXT_MAIN)
        self.option_add("*TCombobox*Listbox.selectBackground", C_PRIMARY)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

        self.bind_class("TCombobox", "<FocusIn>", lambda e: e.widget.selection_clear())

        style.configure(".", background=C_CANVAS, foreground=C_TEXT_MAIN, font=("Segoe UI", 10))

        style.configure(
            "TCombobox",
            fieldbackground=C_INPUT,
            background=C_SURFACE_ALT,
            foreground=C_TEXT_MAIN,
            darkcolor=C_BORDER,
            lightcolor=C_BORDER,
            arrowcolor=C_PRIMARY_HOV,
            bordercolor=C_BORDER,
            padding=4
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", C_INPUT), ("focus", C_INPUT), ("active", C_INPUT)],
            foreground=[("readonly", C_TEXT_MAIN), ("focus", C_TEXT_MAIN), ("active", C_TEXT_MAIN)],
            selectbackground=[("readonly", C_INPUT), ("focus", C_INPUT)],
            selectforeground=[("readonly", C_TEXT_MAIN), ("focus", C_TEXT_MAIN)],
            bordercolor=[("focus", C_PRIMARY_HOV), ("active", C_PRIMARY_HOV)]
        )

        style.configure("Custom.TCheckbutton", background=C_SIDEBAR_CARD, foreground=C_TEXT_MAIN, font=("Segoe UI", 9))
        style.map(
            "Custom.TCheckbutton",
            indicatorcolor=[("selected", C_PRIMARY), ("active", C_PRIMARY_HOV), ("!selected", C_INPUT)],
            indicatorbackground=[("selected", C_PRIMARY), ("!selected", C_INPUT)],
            foreground=[("selected", "#ffffff"), ("active", C_PRIMARY_HOV), ("!selected", C_TEXT_MUTED)]
        )

        style.configure(
            "Treeview",
            background=C_INPUT,
            foreground=C_TEXT_MAIN,
            fieldbackground=C_INPUT,
            rowheight=28,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background=C_SURFACE_ALT,
            foreground=C_TEXT_MAIN,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padding=[4, 6]
        )
        style.map(
            "Treeview",
            background=[("selected", C_PRIMARY)],
            foreground=[("selected", "#ffffff")]
        )
        style.map("Treeview.Heading", background=[("active", "#2a3754")])
        style.configure("Custom.Horizontal.TProgressbar", troughcolor=C_INPUT, background=C_PRIMARY, bordercolor=C_BORDER)

    # ==========================================================
    # CONSTRUCCIÓN DE LA INTERFAZ CON BARRA LATERAL (SIDEBAR)
    # ==========================================================
    def crear_interfaz(self):
        self.root_container = tk.Frame(self, bg=C_CANVAS)
        self.root_container.pack(fill="both", expand=True)

        self.crear_sidebar(self.root_container)
        self.crear_area_principal(self.root_container)

    def crear_sidebar(self, parent):
        self.sidebar_frame = tk.Frame(
            parent,
            bg=C_SIDEBAR,
            width=300,
            padx=14,
            pady=14,
            relief="flat",
            highlightbackground=C_BORDER,
            highlightthickness=1
        )
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # 1. Logo y Título
        brand_frame = tk.Frame(self.sidebar_frame, bg=C_SIDEBAR)
        brand_frame.pack(fill="x", pady=(0, 14))

        base_res = getattr(sys, '_MEIPASS', DIRECTORIO_ACTUAL)
        png_path = os.path.join(base_res, "app_icon.png")
        if not os.path.exists(png_path):
            png_path = os.path.join(DIRECTORIO_ACTUAL, "app_icon.png")

        self._logo_img = None
        if os.path.exists(png_path):
            try:
                from PIL import Image, ImageTk
                img_pil = Image.open(png_path).resize((26, 26), Image.Resampling.LANCZOS)
                self._logo_img = ImageTk.PhotoImage(img_pil)
            except Exception:
                pass

        brand_row = tk.Frame(brand_frame, bg=C_SIDEBAR)
        brand_row.pack(fill="x", anchor="w")

        if self._logo_img:
            lbl_title = tk.Label(brand_row, text=" GESTOR SII", image=self._logo_img, compound="left", font=("Segoe UI", 12, "bold"), bg=C_SIDEBAR, fg=C_TEXT_MAIN)
        else:
            lbl_title = tk.Label(brand_row, text="⚡ GESTOR SII", font=("Segoe UI", 12, "bold"), bg=C_SIDEBAR, fg=C_TEXT_MAIN)
        lbl_title.pack(side="left")

        lbl_ver_badge = tk.Label(
            brand_row,
            text=f"v{VERSION_LOCAL}",
            font=("Segoe UI", 7, "bold"),
            bg="#1e2442",
            fg="#818cf8",
            padx=6,
            pady=1,
            relief="flat",
            cursor="hand2"
        )
        lbl_ver_badge.pack(side="left", padx=(6, 0))
        lbl_ver_badge.bind("<Button-1>", lambda e: self.buscar_actualizaciones_click())

        lbl_sub = tk.Label(brand_frame, text="Facturas, Honorarios & DTEs", font=("Segoe UI", 8), bg=C_SIDEBAR, fg=C_TEXT_MUTED)
        lbl_sub.pack(anchor="w", padx=(28 if self._logo_img else 2, 0))

        # 2. Navegación de Módulos (Nav Items)
        nav_frame = tk.Frame(self.sidebar_frame, bg=C_SIDEBAR)
        nav_frame.pack(fill="x", pady=(0, 14))

        tk.Label(nav_frame, text="MÓDULOS", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_DIM).pack(anchor="w", pady=(0, 6))

        self.btn_nav_facturas = tk.Button(
            nav_frame,
            text="📑  Facturas y RCV (SII)",
            font=("Segoe UI", 9, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_PRIMARY_HOV,
            activebackground=C_SURFACE_ALT,
            activeforeground="#ffffff",
            relief="flat",
            anchor="w",
            padx=12,
            pady=7,
            cursor="hand2",
            command=lambda: self.cambiar_modulo("facturas")
        )
        self.btn_nav_facturas.pack(fill="x", pady=(0, 4))

        self.btn_nav_honorarios = tk.Button(
            nav_frame,
            text="📜  Boletas Honorarios (BHE)",
            font=("Segoe UI", 9),
            bg=C_SIDEBAR,
            fg=C_TEXT_MUTED,
            activebackground=C_SURFACE_ALT,
            activeforeground="#ffffff",
            relief="flat",
            anchor="w",
            padx=12,
            pady=7,
            cursor="hand2",
            command=lambda: self.cambiar_modulo("honorarios")
        )
        self.btn_nav_honorarios.pack(fill="x", pady=(0, 4))

        self.btn_nav_facturacion_cl = tk.Button(
            nav_frame,
            text="🌐  Facturación.cl (Desis)",
            font=("Segoe UI", 9),
            bg=C_SIDEBAR,
            fg=C_TEXT_MUTED,
            activebackground=C_SURFACE_ALT,
            activeforeground="#ffffff",
            relief="flat",
            anchor="w",
            padx=12,
            pady=7,
            cursor="hand2",
            command=lambda: self.cambiar_modulo("facturacion_cl")
        )
        self.btn_nav_facturacion_cl.pack(fill="x")

        # Separador
        tk.Frame(self.sidebar_frame, bg=C_BORDER, height=1).pack(fill="x", pady=10)

        # 3. Parámetros de Consulta
        self.params_frame = tk.Frame(self.sidebar_frame, bg=C_SIDEBAR)
        self.params_frame.pack(fill="x", pady=(0, 10))

        tk.Label(self.params_frame, text="PARÁMETROS DE CONSULTA", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_DIM).pack(anchor="w", pady=(0, 6))

        # Empresa
        emp_header = tk.Frame(self.params_frame, bg=C_SIDEBAR)
        emp_header.pack(fill="x", pady=(0, 3))
        tk.Label(emp_header, text="Empresa Activa:", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_MUTED).pack(side="left")
        
        self.btn_cat = tk.Button(
            emp_header,
            text="🏢 Catálogo",
            font=("Segoe UI", 7, "bold"),
            bg="#1e1b4b",
            fg="#a5b4fc",
            activebackground="#2e2a72",
            activeforeground="#ffffff",
            relief="flat",
            highlightbackground="#312e81",
            highlightthickness=1,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self.abrir_gestion_empresas
        )
        self.btn_cat.pack(side="right", padx=(4, 0))

        self.btn_sii_creds = tk.Button(
            emp_header,
            text="🔑 Clave SII",
            font=("Segoe UI", 7, "bold"),
            bg="#0f291e",
            fg="#6ee7b7",
            activebackground="#134e3a",
            activeforeground="#ffffff",
            relief="flat",
            highlightbackground="#065f46",
            highlightthickness=1,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self.dialogo_configurar_sii_credenciales
        )
        self.btn_sii_creds.pack(side="right")

        valores_empresas = [f"{e['nombre']}  •  {e['rut']}" for e in self.empresas]
        self.cb_empresa = ttk.Combobox(
            self.params_frame,
            textvariable=self.sel_empresa_str,
            values=valores_empresas,
            state="readonly",
            font=("Segoe UI", 8, "bold")
        )
        self.cb_empresa.pack(fill="x", pady=(0, 8))
        self.cb_empresa.bind("<<ComboboxSelected>>", self.al_cambiar_empresa)

        # Periodo (Mes, Año y Botones de Salto Rápido ◀ ▶)
        tk.Label(self.params_frame, text="Periodo:", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 3))
        row_per = tk.Frame(self.params_frame, bg=C_SIDEBAR)
        row_per.pack(fill="x", pady=(0, 8))

        self.btn_mes_prev = tk.Button(
            row_per,
            text="◀",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            activebackground="#223150",
            activeforeground="#ffffff",
            relief="flat",
            padx=5,
            pady=1,
            cursor="hand2",
            command=self.mes_anterior_sidebar
        )
        self.btn_mes_prev.pack(side="left", padx=(0, 3))

        meses_disp = [m for m in script.NOMBRES_MESES if m]
        self.cb_mes = ttk.Combobox(row_per, textvariable=self.sel_mes, values=meses_disp, width=10, state="readonly")
        self.cb_mes.pack(side="left", padx=(0, 3))
        self.cb_mes.bind("<<ComboboxSelected>>", lambda e: self.on_cambio_periodo_sidebar())

        self.btn_mes_next = tk.Button(
            row_per,
            text="▶",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            activebackground="#223150",
            activeforeground="#ffffff",
            relief="flat",
            padx=5,
            pady=1,
            cursor="hand2",
            command=self.mes_siguiente_sidebar
        )
        self.btn_mes_next.pack(side="left", padx=(0, 3))

        anios_disp = [str(a) for a in range(datetime.now().year, datetime.now().year - 4, -1)]
        self.cb_anio = ttk.Combobox(row_per, textvariable=self.sel_anio, values=anios_disp, width=6, state="readonly")
        self.cb_anio.pack(side="left")
        self.cb_anio.bind("<<ComboboxSelected>>", lambda e: self.on_cambio_periodo_sidebar())

        # BOTÓN DESPLEGABLE DE OPCIONES AVANZADAS (Registro, Pendientes, Reclamados, Silencioso)
        self.btn_toggle_opciones = tk.Button(
            self.params_frame,
            text="⚙️  Opciones y Filtros  ▼",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR_CARD,
            fg=C_TEXT_MUTED,
            activebackground=C_SURFACE_ALT,
            activeforeground=C_PRIMARY_HOV,
            relief="flat",
            pady=3,
            cursor="hand2",
            command=self.toggle_opciones_avanzadas
        )
        self.btn_toggle_opciones.pack(fill="x", pady=(0, 6))

        # Panel Plegable con los 4 controles
        self.panel_opciones = tk.Frame(
            self.params_frame,
            bg=C_SIDEBAR_CARD,
            padx=8,
            pady=6,
            highlightbackground=C_BORDER,
            highlightthickness=1
        )

        # Fila de RCV Pills
        self.row_rcv_pills = tk.Frame(self.panel_opciones, bg=C_SIDEBAR_CARD)
        self.row_rcv_pills.pack(fill="x", pady=(0, 4))
        self.chk_btn_registro = ttk.Checkbutton(self.row_rcv_pills, text="Registro", variable=self.chk_registro, style="Custom.TCheckbutton")
        self.chk_btn_registro.pack(side="left", padx=(0, 4))
        self.chk_btn_pendientes = ttk.Checkbutton(self.row_rcv_pills, text="Pendientes", variable=self.chk_pendientes, style="Custom.TCheckbutton")
        self.chk_btn_pendientes.pack(side="left", padx=(0, 4))
        self.chk_btn_reclamados = ttk.Checkbutton(self.row_rcv_pills, text="Reclamados", variable=self.chk_reclamados, style="Custom.TCheckbutton")
        self.chk_btn_reclamados.pack(side="left")

        # Modo silencioso
        self.chk_btn_headless = ttk.Checkbutton(self.panel_opciones, text="Modo silencioso (navegador oculto)", variable=self.modo_headless, style="Custom.TCheckbutton")
        self.chk_btn_headless.pack(anchor="w")

        # BOTÓN CONSULTAR DESTACADO
        self.btn_consultar_sidebar = tk.Button(
            self.params_frame,
            text="⚡  CONSULTAR FACTURAS",
            font=("Segoe UI", 10, "bold"),
            bg=C_SUCCESS,
            fg="#022c22",
            activebackground=C_SUCCESS_HOV,
            activeforeground="#022c22",
            relief="flat",
            pady=8,
            cursor="hand2",
            command=self.iniciar_consulta_actual
        )
        self.btn_consultar_sidebar.pack(fill="x", pady=(0, 4))

        self.btn_cancelar_sidebar = tk.Button(
            self.params_frame,
            text="🛑  CANCELAR CONSULTA",
            font=("Segoe UI", 9, "bold"),
            bg=C_DANGER,
            fg="#ffffff",
            activebackground="#dc2626",
            relief="flat",
            pady=6,
            cursor="hand2",
            command=self.cancelar_consulta_actual
        )

        self.pb_sidebar = ttk.Progressbar(self.params_frame, mode="indeterminate", style="Custom.Horizontal.TProgressbar")

        # Separador
        tk.Frame(self.sidebar_frame, bg=C_BORDER, height=1).pack(fill="x", pady=10)

        # 4. Configuración de Descargas & IA
        dl_card = tk.Frame(self.sidebar_frame, bg=C_SIDEBAR)
        dl_card.pack(fill="x", pady=(0, 10))

        tk.Label(dl_card, text="DESCARGAS & IA", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_DIM).pack(anchor="w", pady=(0, 6))

        # Correlativo e IA
        row_corr = tk.Frame(dl_card, bg=C_SIDEBAR)
        row_corr.pack(fill="x", pady=(0, 6))

        tk.Label(row_corr, text="Corr:", font=("Segoe UI", 8, "bold"), bg=C_SIDEBAR, fg=C_TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.spin_corr = tk.Spinbox(
            row_corr,
            from_=1,
            to=999999,
            textvariable=self.correlativo_val,
            font=("Segoe UI", 8, "bold"),
            bg=C_INPUT,
            fg=C_PRIMARY_HOV,
            insertbackground=C_TEXT_MAIN,
            buttonbackground=C_SIDEBAR_CARD,
            relief="flat",
            width=6,
            command=self.on_cambio_correlativo
        )
        self.spin_corr.pack(side="left", padx=(0, 8))
        self.spin_corr.bind("<KeyRelease>", lambda e: self.on_cambio_correlativo())

        self.chk_ia_btn = ttk.Checkbutton(row_corr, text="IA Glosa", variable=self.chk_usar_ia, style="Custom.TCheckbutton", command=self.on_cambio_correlativo)
        self.chk_ia_btn.pack(side="left", padx=(0, 4))
        
        self.btn_ia_config = tk.Button(
            row_corr,
            text="⚙️",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR_CARD,
            fg=C_PURPLE,
            relief="flat",
            padx=4,
            pady=1,
            cursor="hand2",
            command=self.dialogo_configurar_ia
        )
        self.btn_ia_config.pack(side="left")

        # Carpeta de descarga
        row_fld = tk.Frame(dl_card, bg=C_SIDEBAR)
        row_fld.pack(fill="x")

        self.btn_cambiar_dir = tk.Button(
            row_fld,
            text="📂 Cambiar",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR_CARD,
            fg=C_INFO,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.seleccionar_carpeta_guardado_actual
        )
        self.btn_cambiar_dir.pack(side="left", padx=(0, 4))

        self.btn_abrir_dir = tk.Button(
            row_fld,
            text="📁 Abrir",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR_CARD,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.abrir_carpeta_descargas_actual
        )
        self.btn_abrir_dir.pack(side="left")

        # 5. Footer Sidebar (Estado de Conexión)
        footer_sidebar = tk.Frame(self.sidebar_frame, bg=C_SIDEBAR)
        footer_sidebar.pack(side="bottom", fill="x", pady=(6, 0))

        tk.Frame(footer_sidebar, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 8))

        row_stat = tk.Frame(footer_sidebar, bg=C_SIDEBAR)
        row_stat.pack(fill="x")

        self.lbl_sesion_badge = tk.Label(
            row_stat,
            text="● SII Conectado",
            font=("Segoe UI", 8, "bold"),
            bg=C_SIDEBAR_CARD,
            fg=C_SUCCESS,
            padx=6,
            pady=2
        )
        self.lbl_sesion_badge.pack(side="left")

        self.btn_disc = tk.Button(
            row_stat,
            text="🔌 Desconectar",
            font=("Segoe UI", 8),
            bg=C_SIDEBAR_CARD,
            fg=C_DANGER,
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.desconectar_todas_sesiones
        )
        self.btn_disc.pack(side="right")

        # Botón Salir del Programa (con cierre limpio de sesión en SII)
        self.btn_salir = tk.Button(
            footer_sidebar,
            text="🚪  Salir del Programa",
            font=("Segoe UI", 9, "bold"),
            bg="#24121a",
            fg="#f87171",
            activebackground="#3b1523",
            activeforeground="#fca5a5",
            relief="flat",
            highlightbackground="#881337",
            highlightthickness=1,
            pady=6,
            cursor="hand2",
            command=self.confirmar_y_salir
        )
        self.btn_salir.pack(fill="x", pady=(6, 0))

    def toggle_opciones_avanzadas(self):
        if self.opciones_avanzadas_visibles:
            self.panel_opciones.pack_forget()
            self.btn_toggle_opciones.config(text="⚙️  Opciones y Filtros  ▼", fg=C_TEXT_MUTED)
            self.opciones_avanzadas_visibles = False
        else:
            self.panel_opciones.pack(fill="x", pady=(0, 6), before=self.btn_consultar_sidebar)
            self.btn_toggle_opciones.config(text="⚙️  Opciones y Filtros  ▲", fg=C_PRIMARY_HOV)
            self.opciones_avanzadas_visibles = True

    def mes_anterior_sidebar(self):
        mes_nom = self.sel_mes.get()
        meses = [m for m in script.NOMBRES_MESES if m]
        mes_idx = meses.index(mes_nom) if mes_nom in meses else datetime.now().month - 1
        anio_val = int(self.sel_anio.get())
        if mes_idx == 0:
            mes_idx = 11
            anio_val -= 1
        else:
            mes_idx -= 1
        self.sel_mes.set(meses[mes_idx])
        self.sel_anio.set(str(anio_val))
        self.on_cambio_periodo_sidebar()

    def mes_siguiente_sidebar(self):
        mes_nom = self.sel_mes.get()
        meses = [m for m in script.NOMBRES_MESES if m]
        mes_idx = meses.index(mes_nom) if mes_nom in meses else datetime.now().month - 1
        anio_val = int(self.sel_anio.get())
        if mes_idx == 11:
            mes_idx = 0
            anio_val += 1
        else:
            mes_idx += 1
        self.sel_mes.set(meses[mes_idx])
        self.sel_anio.set(str(anio_val))
        self.on_cambio_periodo_sidebar()

    def on_cambio_periodo_sidebar(self):
        m = self.sel_mes.get()
        a = self.sel_anio.get()
        self.hn_sel_mes.set(m)
        self.hn_sel_anio.set(a)
        self.fcl_sel_mes.set(m)
        self.fcl_sel_anio.set(a)
        self.actualizar_subtitulo_vistas()

    def cambiar_modulo(self, modulo_id):
        self.modulo_activo = modulo_id

        btn_map = {
            "facturas": (self.btn_nav_facturas, "⚡  CONSULTAR FACTURAS"),
            "honorarios": (self.btn_nav_honorarios, "⚡  CONSULTAR HONORARIOS"),
            "facturacion_cl": (self.btn_nav_facturacion_cl, "⚡  CONSULTAR FACTURACIÓN.CL")
        }

        for k, (btn, txt_btn) in btn_map.items():
            if k == modulo_id:
                btn.configure(
                    bg="#1e2442",
                    fg="#ffffff",
                    activebackground="#252c52",
                    activeforeground="#ffffff",
                    highlightbackground="#6366f1",
                    highlightcolor="#6366f1",
                    highlightthickness=1,
                    font=("Segoe UI", 9, "bold")
                )
                self.btn_consultar_sidebar.configure(text=txt_btn, bg=C_SUCCESS, fg="#ffffff")
            else:
                btn.configure(
                    bg=C_SIDEBAR,
                    fg=C_TEXT_MUTED,
                    activebackground=C_SURFACE_ALT,
                    activeforeground="#ffffff",
                    highlightthickness=0,
                    font=("Segoe UI", 9)
                )

        if modulo_id == "facturas":
            self.row_rcv_pills.pack(fill="x", pady=(0, 4))
        else:
            self.row_rcv_pills.pack_forget()

        if modulo_id == "facturas":
            self.vista_facturas.tkraise()
        elif modulo_id == "honorarios":
            self.vista_honorarios.tkraise()
        elif modulo_id == "facturacion_cl":
            self.vista_facturacion_cl.tkraise()

        self.actualizar_subtitulo_vistas()

    def crear_area_principal(self, parent):
        self.main_area = tk.Frame(parent, bg=C_CANVAS, padx=14, pady=10)
        self.main_area.pack(side="right", fill="both", expand=True)

        self.views_container = tk.Frame(self.main_area, bg=C_CANVAS)
        self.views_container.pack(fill="both", expand=True, pady=(0, 6))
        self.views_container.grid_rowconfigure(0, weight=1)
        self.views_container.grid_columnconfigure(0, weight=1)

        self.vista_facturas = tk.Frame(self.views_container, bg=C_CANVAS)
        self.vista_honorarios = tk.Frame(self.views_container, bg=C_CANVAS)
        self.vista_facturacion_cl = tk.Frame(self.views_container, bg=C_CANVAS)

        for v in (self.vista_facturas, self.vista_honorarios, self.vista_facturacion_cl):
            v.grid(row=0, column=0, sticky="nsew")

        self.crear_vista_facturas_content(self.vista_facturas)
        self.crear_vista_honorarios_content(self.vista_honorarios)
        self.crear_vista_facturacion_cl_content(self.vista_facturacion_cl)

        self.vista_facturas.tkraise()
        self.crear_terminal_inferior(self.main_area)

    # ==========================================================
    # VISTA 1: FACTURAS Y RCV
    # ==========================================================
    def crear_vista_facturas_content(self, parent):
        hdr = tk.Frame(parent, bg=C_CANVAS)
        hdr.pack(fill="x", pady=(0, 8))

        self.lbl_hdr_fac_tit = tk.Label(hdr, text="📑 Facturas y Registro de Compras (RCV) • SII", font=("Segoe UI", 13, "bold"), bg=C_CANVAS, fg=C_TEXT_MAIN)
        self.lbl_hdr_fac_tit.pack(anchor="w")

        self.lbl_hdr_fac_sub = tk.Label(hdr, text="Consultando periodo actual...", font=("Segoe UI", 9), bg=C_CANVAS, fg=C_TEXT_MUTED)
        self.lbl_hdr_fac_sub.pack(anchor="w")

        # KPI CARDS PILL BAR
        kpi_bar = tk.Frame(parent, bg=C_CANVAS)
        kpi_bar.pack(fill="x", pady=(0, 8))

        def _filtrar_kpi_fac():
            self.filtro_estado.set("Registro")
            self.filtrar_tabla()
            self.log("Filtro aplicado: Documentos en Registro.")

        def _filtrar_kpi_exe():
            self.busqueda_texto.set("34")
            self.filtrar_tabla()
            self.log("Filtro aplicado: Facturas Exentas (Tipo 34).")

        def _filtrar_kpi_pen():
            self.filtro_estado.set("Pendientes")
            self.filtrar_tabla()
            self.log("Filtro aplicado: Facturas Pendientes.")

        def _filtrar_kpi_tot():
            self.busqueda_texto.set("")
            self.filtro_estado.set("Todos")
            self.filtrar_tabla()
            self.log("Filtro restablecido: Todos los documentos.")

        self.kpi_fac = self.crear_kpi_card_compacta(kpi_bar, "DOCS (33)", "0", C_INFO, click_cb=_filtrar_kpi_fac)
        self.kpi_exe = self.crear_kpi_card_compacta(kpi_bar, "EXENTAS (34)", "0", C_SUCCESS, click_cb=_filtrar_kpi_exe)
        self.kpi_pen = self.crear_kpi_card_compacta(kpi_bar, "PENDIENTES", "0", C_WARNING, click_cb=_filtrar_kpi_pen)
        self.kpi_iva = self.crear_kpi_card_compacta(kpi_bar, "IVA RECUP.", "$0", C_DANGER)
        self.kpi_tot = self.crear_kpi_card_compacta(kpi_bar, "TOTAL SUMADO", "$0", C_PURPLE, click_cb=_filtrar_kpi_tot)
        self.kpi_pdf = self.crear_kpi_card_compacta(kpi_bar, "PDFS GUARDADOS", "0", C_TEAL, click_cb=self.abrir_carpeta_descargas)

        # TOOLBAR DE TABLA
        tb = tk.Frame(parent, bg=C_SURFACE, padx=10, pady=6, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        tb.pack(fill="x", pady=(0, 6))

        # Caja de búsqueda integrada con botón Limpiar
        box_search = tk.Frame(tb, bg=C_INPUT, highlightbackground=C_BORDER, highlightthickness=1)
        box_search.pack(side="left", padx=(0, 10))
        tk.Label(box_search, text="🔎", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MUTED).pack(side="left", padx=(5, 2))
        self.entry_busqueda = tk.Entry(
            box_search,
            textvariable=self.busqueda_texto,
            font=("Segoe UI", 9),
            bg=C_INPUT,
            fg=C_TEXT_MAIN,
            insertbackground=C_TEXT_MAIN,
            relief="flat",
            width=22
        )
        self.entry_busqueda.pack(side="left", ipady=2)
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self.filtrar_tabla())
        tk.Button(
            box_search,
            text="✖",
            font=("Segoe UI", 7, "bold"),
            bg=C_INPUT,
            fg=C_TEXT_MUTED,
            activebackground=C_INPUT,
            activeforeground=C_DANGER,
            relief="flat",
            padx=4,
            cursor="hand2",
            command=lambda: [self.busqueda_texto.set(""), self.filtrar_tabla()]
        ).pack(side="right", padx=(0, 2))

        tk.Label(tb, text="Filtro:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.cb_filtro_est = ttk.Combobox(
            tb,
            textvariable=self.filtro_estado,
            values=["Todos", "Registro", "Pendientes", "Reclamados"],
            width=11,
            state="readonly"
        )
        self.cb_filtro_est.pack(side="left", padx=(0, 10))
        self.cb_filtro_est.bind("<<ComboboxSelected>>", lambda e: self.filtrar_tabla())

        tk.Label(tb, text="Ordenar:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(side="left", padx=(0, 4))
        opciones_orden = [
            ("🔽 Fecha Docto", "fecha_desc"),
            ("🔼 Fecha Docto", "fecha_asc"),
            ("💰 Monto Total (Mayor)", "monto_desc"),
            ("💵 Monto Total (Menor)", "monto_asc"),
            ("💸 IVA (Mayor)", "iva_desc"),
        ]
        self.cb_orden = ttk.Combobox(tb, values=[t[0] for t in opciones_orden], width=18, state="readonly")
        self.cb_orden.set("🔽 Fecha Docto")
        self.cb_orden.pack(side="left", padx=(0, 10))
        self.cb_orden.bind("<<ComboboxSelected>>", self.on_cambio_orden)

        self.btn_exp_fac = tk.Button(
            tb,
            text="📊 Exportar CSV",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.exportar_rcv_csv
        )
        self.btn_exp_fac.pack(side="right")

        self.btn_copy_fac = tk.Button(
            tb,
            text="📋 Copiar a Excel",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_SUCCESS,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.copiar_rcv_excel
        )
        self.btn_copy_fac.pack(side="right", padx=(0, 6))

        # TABLA DE FACTURAS (TREEVIEW)
        tree_frame = tk.Frame(parent, bg=C_CANVAS)
        tree_frame.pack(fill="both", expand=True, pady=(0, 6))

        columnas = ("check", "folio", "tipo_doc", "razon_social", "rut_emisor", "fecha_docto", "monto_neto", "monto_iva", "monto_total", "estado_rcv", "pdf_estado")
        self.tree = ttk.Treeview(tree_frame, columns=columnas, show="headings", selectmode="extended")

        self.tree.heading("check", text="✓", anchor="center")
        self.tree.heading("folio", text="Folio", anchor="center", command=lambda: self.ordenar_por_columna("folio", es_num=True))
        self.tree.heading("tipo_doc", text="Tipo", anchor="center", command=lambda: self.ordenar_por_columna("tipo_doc_codigo"))
        self.tree.heading("razon_social", text="Emisor / Razón Social", anchor="w", command=lambda: self.ordenar_por_columna("razon_social"))
        self.tree.heading("rut_emisor", text="RUT Emisor", anchor="center", command=lambda: self.ordenar_por_columna("rut_emisor"))
        self.tree.heading("fecha_docto", text="Fecha", anchor="center", command=lambda: self.ordenar_por_columna("fecha_docto", es_fecha=True))
        self.tree.heading("monto_neto", text="Monto Neto", anchor="e", command=lambda: self.ordenar_por_columna("monto_neto", es_monto=True))
        self.tree.heading("monto_iva", text="IVA Recup.", anchor="e", command=lambda: self.ordenar_por_columna("monto_iva", es_monto=True))
        self.tree.heading("monto_total", text="Monto Total", anchor="e", command=lambda: self.ordenar_por_columna("monto_total", es_monto=True))
        self.tree.heading("estado_rcv", text="Estado", anchor="center", command=lambda: self.ordenar_por_columna("estado_rcv"))
        self.tree.heading("pdf_estado", text="PDF", anchor="center")

        self.tree.column("check", width=34, minwidth=34, anchor="center")
        self.tree.column("folio", width=75, minwidth=60, anchor="center")
        self.tree.column("tipo_doc", width=65, minwidth=50, anchor="center")
        self.tree.column("razon_social", width=330, minwidth=200, anchor="w")
        self.tree.column("rut_emisor", width=105, minwidth=90, anchor="center")
        self.tree.column("fecha_docto", width=85, minwidth=75, anchor="center")
        self.tree.column("monto_neto", width=105, minwidth=85, anchor="e")
        self.tree.column("monto_iva", width=95, minwidth=80, anchor="e")
        self.tree.column("monto_total", width=115, minwidth=95, anchor="e")
        self.tree.column("estado_rcv", width=90, minwidth=75, anchor="center")
        self.tree.column("pdf_estado", width=55, minwidth=45, anchor="center")

        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        sy.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("odd", background="#0b1120")
        self.tree.tag_configure("even", background="#0e1628")
        self.tree.tag_configure("tipo_33", foreground="#93c5fd")
        self.tree.tag_configure("tipo_34", foreground="#86efac")
        self.tree.tag_configure("tipo_61", foreground="#fda4af")
        self.tree.tag_configure("tipo_56", foreground="#fde047")
        self.tree.tag_configure("pdf_listo", foreground="#34d399")
        self.tree.tag_configure("reclamado", foreground="#f87171")
        self.tree.tag_configure("pendiente", foreground="#fbbf24")

        self.tree.bind("<Double-1>", self.on_doble_clic_fila)
        self.tree.bind("<Button-3>", self.mostrar_menu_contextual)
        self.tree.bind("<<TreeviewSelect>>", self.on_seleccion_fila)

        # Estado Vacío (Empty State Placeholder)
        self.empty_state_fac = tk.Frame(tree_frame, bg=C_INPUT)
        lbl_box_fac = tk.Label(self.empty_state_fac, text="📥", font=("Segoe UI", 34), bg=C_INPUT, fg="#334155")
        lbl_box_fac.pack(pady=(0, 4))
        lbl_t_fac = tk.Label(self.empty_state_fac, text="No hay facturas para mostrar", font=("Segoe UI", 11, "bold"), bg=C_INPUT, fg=C_TEXT_MAIN)
        lbl_t_fac.pack()
        lbl_s_fac = tk.Label(self.empty_state_fac, text="Ajusta los filtros o consulta el Registro de Compras (RCV)", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_DIM)
        lbl_s_fac.pack(pady=(2, 0))
        self.empty_state_fac.place(relx=0.5, rely=0.5, anchor="center")

        # BARRA DE ACCIONES INFERIOR (BOTTOM ACTION BAR)
        act_bar = tk.Frame(parent, bg=C_SURFACE, padx=12, pady=8, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        act_bar.pack(fill="x")

        left_act = tk.Frame(act_bar, bg=C_SURFACE)
        left_act.pack(side="left")

        self.lbl_seleccion_resumen = tk.Label(left_act, text="0 facturas seleccionadas", font=("Segoe UI", 9, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN)
        self.lbl_seleccion_resumen.pack(side="left", padx=(0, 10))

        self.btn_sel_todo_fac = tk.Button(left_act, text="Seleccionar Todo", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.seleccionar_todo_rcv)
        self.btn_sel_todo_fac.pack(side="left", padx=(0, 4))
        self.btn_limpiar_sel_fac = tk.Button(left_act, text="Limpiar", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.limpiar_seleccion_rcv)
        self.btn_limpiar_sel_fac.pack(side="left")

        right_act = tk.Frame(act_bar, bg=C_SURFACE)
        right_act.pack(side="right")

        self.btn_descargar_seleccionada = tk.Button(
            right_act,
            text="📥  DESCARGAR SELECCIÓN",
            font=("Segoe UI", 9, "bold"),
            bg=C_PRIMARY,
            fg="#ffffff",
            activebackground=C_PRIMARY_HOV,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.descargar_facturas_seleccionadas_lote
        )
        self.btn_descargar_seleccionada.pack(side="left", padx=(0, 6))

        self.btn_descargar_todo_mes = tk.Button(
            right_act,
            text="⚡  DESCARGAR TODO EL MES",
            font=("Segoe UI", 9, "bold"),
            bg=C_SUCCESS,
            fg="#022c22",
            activebackground=C_SUCCESS_HOV,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.iniciar_descarga_todas_pdf
        )
        self.btn_descargar_todo_mes.pack(side="left")

    # ==========================================================
    # VISTA 2: BOLETAS DE HONORARIOS BHE
    # ==========================================================
    def crear_vista_honorarios_content(self, parent):
        hdr = tk.Frame(parent, bg=C_CANVAS)
        hdr.pack(fill="x", pady=(0, 8))

        hdr_top = tk.Frame(hdr, bg=C_CANVAS)
        hdr_top.pack(fill="x")

        self.lbl_hdr_hn_tit = tk.Label(hdr_top, text="📜 Boletas de Honorarios Electrónicas (BHE) • SII", font=("Segoe UI", 13, "bold"), bg=C_CANVAS, fg=C_TEXT_MAIN)
        self.lbl_hdr_hn_tit.pack(side="left")

        hdr_right = tk.Frame(hdr_top, bg=C_CANVAS)
        hdr_right.pack(side="right")

        self.rb_hn_rec = tk.Radiobutton(hdr_right, text="Recibidas", variable=self.hn_tipo_consulta, value="recibidas", font=("Segoe UI", 9, "bold"), bg=C_CANVAS, fg=C_INFO, selectcolor=C_INPUT, activebackground=C_CANVAS)
        self.rb_hn_rec.pack(side="left", padx=(0, 6))
        self.rb_hn_emi = tk.Radiobutton(hdr_right, text="Emitidas", variable=self.hn_tipo_consulta, value="emitidas", font=("Segoe UI", 9, "bold"), bg=C_CANVAS, fg=C_WARNING, selectcolor=C_INPUT, activebackground=C_CANVAS)
        self.rb_hn_emi.pack(side="left", padx=(0, 10))

        self.btn_clave_hn = tk.Button(
            hdr_right,
            text="🔑 Clave SII Empresa",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE,
            fg=C_PRIMARY_HOV,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.abrir_dialogo_credenciales_hn
        )
        self.btn_clave_hn.pack(side="left")

        self.lbl_hdr_hn_sub = tk.Label(hdr, text="Consultando periodo actual...", font=("Segoe UI", 9), bg=C_CANVAS, fg=C_TEXT_MUTED)
        self.lbl_hdr_hn_sub.pack(anchor="w")

        # KPI CARDS PILL BAR
        kpi_bar = tk.Frame(parent, bg=C_CANVAS)
        kpi_bar.pack(fill="x", pady=(0, 8))

        self.kpi_hn_tot = self.crear_kpi_card_compacta(kpi_bar, "TOTAL BOLETAS", "0", C_INFO)
        self.kpi_hn_bruto = self.crear_kpi_card_compacta(kpi_bar, "TOTAL BRUTO", "$0", C_SUCCESS)
        self.kpi_hn_ret = self.crear_kpi_card_compacta(kpi_bar, "RETENCIÓN (13.75%)", "$0", C_WARNING)
        self.kpi_hn_liq = self.crear_kpi_card_compacta(kpi_bar, "MONTO LÍQUIDO", "$0", C_PURPLE)
        self.kpi_hn_pdf = self.crear_kpi_card_compacta(kpi_bar, "PDFS GUARDADOS", "0", C_TEAL, click_cb=self.abrir_carpeta_descargas_hn)

        # TOOLBAR
        tb = tk.Frame(parent, bg=C_SURFACE, padx=10, pady=6, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        tb.pack(fill="x", pady=(0, 6))

        # Caja de búsqueda integrada con botón Limpiar
        box_search_hn = tk.Frame(tb, bg=C_INPUT, highlightbackground=C_BORDER, highlightthickness=1)
        box_search_hn.pack(side="left", padx=(0, 10))
        tk.Label(box_search_hn, text="🔎", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MUTED).pack(side="left", padx=(5, 2))
        self.entry_busqueda_hn = tk.Entry(
            box_search_hn,
            textvariable=self.hn_busqueda_texto,
            font=("Segoe UI", 9),
            bg=C_INPUT,
            fg=C_TEXT_MAIN,
            insertbackground=C_TEXT_MAIN,
            relief="flat",
            width=24
        )
        self.entry_busqueda_hn.pack(side="left", ipady=2)
        self.entry_busqueda_hn.bind("<KeyRelease>", lambda e: self.filtrar_tabla_honorarios())
        tk.Button(
            box_search_hn,
            text="✖",
            font=("Segoe UI", 7, "bold"),
            bg=C_INPUT,
            fg=C_TEXT_MUTED,
            activebackground=C_INPUT,
            activeforeground=C_DANGER,
            relief="flat",
            padx=4,
            cursor="hand2",
            command=lambda: [self.hn_busqueda_texto.set(""), self.filtrar_tabla_honorarios()]
        ).pack(side="right", padx=(0, 2))

        self.btn_exp_hn = tk.Button(
            tb,
            text="📊 Exportar CSV",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.exportar_honorarios_csv
        )
        self.btn_exp_hn.pack(side="right")

        self.btn_copy_hn = tk.Button(
            tb,
            text="📋 Copiar a Excel",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_SUCCESS,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.copiar_honorarios_excel
        )
        self.btn_copy_hn.pack(side="right", padx=(0, 6))

        # TABLA DE HONORARIOS
        tree_frame = tk.Frame(parent, bg=C_CANVAS)
        tree_frame.pack(fill="both", expand=True, pady=(0, 6))

        cols_hn = ("check", "folio", "fecha", "emisor", "rut", "bruto", "retencion", "liquido", "glosa", "pdf_estado")
        self.tree_hn = ttk.Treeview(tree_frame, columns=cols_hn, show="headings", selectmode="extended")

        self.tree_hn.heading("check", text="✓", anchor="center")
        self.tree_hn.heading("folio", text="Folio", anchor="center", command=lambda: self.ordenar_por_columna_honorarios("folio", es_num=True))
        self.tree_hn.heading("fecha", text="Fecha", anchor="center", command=lambda: self.ordenar_por_columna_honorarios("fecha", es_fecha=True))
        self.tree_hn.heading("emisor", text="Emisor / Profesional", anchor="w", command=lambda: self.ordenar_por_columna_honorarios("emisor"))
        self.tree_hn.heading("rut", text="RUT Emisor", anchor="center", command=lambda: self.ordenar_por_columna_honorarios("rut"))
        self.tree_hn.heading("bruto", text="Monto Bruto", anchor="e", command=lambda: self.ordenar_por_columna_honorarios("monto_bruto", es_monto=True))
        self.tree_hn.heading("retencion", text="Retención (Impuesto)", anchor="e", command=lambda: self.ordenar_por_columna_honorarios("retencion", es_monto=True))
        self.tree_hn.heading("liquido", text="Monto Líquido", anchor="e", command=lambda: self.ordenar_por_columna_honorarios("monto_liquido", es_monto=True))
        self.tree_hn.heading("glosa", text="Glosa / Detalle Servicios", anchor="w")
        self.tree_hn.heading("pdf_estado", text="PDF", anchor="center")

        self.tree_hn.column("check", width=34, minwidth=34, anchor="center")
        self.tree_hn.column("folio", width=75, minwidth=60, anchor="center")
        self.tree_hn.column("fecha", width=85, minwidth=75, anchor="center")
        self.tree_hn.column("emisor", width=280, minwidth=180, anchor="w")
        self.tree_hn.column("rut", width=105, minwidth=90, anchor="center")
        self.tree_hn.column("bruto", width=110, minwidth=90, anchor="e")
        self.tree_hn.column("retencion", width=110, minwidth=90, anchor="e")
        self.tree_hn.column("liquido", width=110, minwidth=90, anchor="e")
        self.tree_hn.column("glosa", width=240, minwidth=150, anchor="w")
        self.tree_hn.column("pdf_estado", width=55, minwidth=45, anchor="center")

        sy_hn = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_hn.yview)
        self.tree_hn.configure(yscrollcommand=sy_hn.set)
        sy_hn.pack(side="right", fill="y")
        self.tree_hn.pack(fill="both", expand=True)

        self.tree_hn.tag_configure("odd", background="#0b1120")
        self.tree_hn.tag_configure("even", background="#0e1628")
        self.tree_hn.tag_configure("bhe_activa", foreground="#86efac")
        self.tree_hn.tag_configure("bhe_anulada", foreground="#fda4af")
        self.tree_hn.tag_configure("pdf_listo", foreground="#34d399")

        self.tree_hn.bind("<Double-1>", self.on_doble_clic_fila_hn)
        self.tree_hn.bind("<Button-3>", self.mostrar_menu_contextual_hn)

        # Estado Vacío (Empty State Placeholder)
        self.empty_state_hn = tk.Frame(tree_frame, bg=C_INPUT)
        lbl_box_hn = tk.Label(self.empty_state_hn, text="📜", font=("Segoe UI", 34), bg=C_INPUT, fg="#334155")
        lbl_box_hn.pack(pady=(0, 4))
        lbl_t_hn = tk.Label(self.empty_state_hn, text="No hay boletas de honorarios para mostrar", font=("Segoe UI", 11, "bold"), bg=C_INPUT, fg=C_TEXT_MAIN)
        lbl_t_hn.pack()
        lbl_s_hn = tk.Label(self.empty_state_hn, text="Ajusta los filtros o consulta Boletas de Honorarios en el SII", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_DIM)
        lbl_s_hn.pack(pady=(2, 0))
        self.empty_state_hn.place(relx=0.5, rely=0.5, anchor="center")

        # BARRA DE ACCIONES INFERIOR
        act_bar_hn = tk.Frame(parent, bg=C_SURFACE, padx=12, pady=8, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        act_bar_hn.pack(fill="x")

        left_act_hn = tk.Frame(act_bar_hn, bg=C_SURFACE)
        left_act_hn.pack(side="left")

        self.lbl_seleccion_hn = tk.Label(left_act_hn, text="0 boletas seleccionadas", font=("Segoe UI", 9, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN)
        self.lbl_seleccion_hn.pack(side="left", padx=(0, 10))

        self.btn_sel_todo_hn = tk.Button(left_act_hn, text="Seleccionar Todo", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.seleccionar_todo_hn)
        self.btn_sel_todo_hn.pack(side="left", padx=(0, 4))
        self.btn_limpiar_sel_hn = tk.Button(left_act_hn, text="Limpiar", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.limpiar_seleccion_hn)
        self.btn_limpiar_sel_hn.pack(side="left")

        right_act_hn = tk.Frame(act_bar_hn, bg=C_SURFACE)
        right_act_hn.pack(side="right")

        self.btn_descargar_hn_selec = tk.Button(
            right_act_hn,
            text="📥  DESCARGAR SELECCIÓN",
            font=("Segoe UI", 9, "bold"),
            bg=C_PRIMARY,
            fg="#ffffff",
            activebackground=C_PRIMARY_HOV,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.descargar_boletas_seleccionadas_lote
        )
        self.btn_descargar_hn_selec.pack(side="left", padx=(0, 6))

        self.btn_descargar_hn_todo = tk.Button(
            right_act_hn,
            text="⚡  DESCARGAR TODAS LAS BOLETAS",
            font=("Segoe UI", 9, "bold"),
            bg=C_SUCCESS,
            fg="#ffffff",
            activebackground=C_SUCCESS_HOV,
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self.iniciar_descarga_todas_honorarios_pdf
        )
        self.btn_descargar_hn_todo.pack(side="left")

    # ==========================================================
    # VISTA 3: FACTURACIÓN.CL (DESIS)
    # ==========================================================
    def crear_vista_facturacion_cl_content(self, parent):
        hdr = tk.Frame(parent, bg=C_CANVAS)
        hdr.pack(fill="x", pady=(0, 8))

        hdr_top = tk.Frame(hdr, bg=C_CANVAS)
        hdr_top.pack(fill="x")

        self.lbl_hdr_fcl_tit = tk.Label(hdr_top, text="🌐 Facturación.cl • Panel DTE Recibidos (Compras)", font=("Segoe UI", 13, "bold"), bg=C_CANVAS, fg=C_TEXT_MAIN)
        self.lbl_hdr_fcl_tit.pack(side="left")

        self.btn_cred_fcl = tk.Button(
            hdr_top,
            text="🔑 Credenciales Facturación.cl",
            font=("Segoe UI", 8, "bold"),
            bg="#181a30",
            fg="#a5b4fc",
            activebackground="#252a4e",
            activeforeground="#ffffff",
            relief="flat",
            highlightbackground="#312e81",
            highlightthickness=1,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.abrir_dialogo_credenciales_fcl
        )
        self.btn_cred_fcl.pack(side="right")

        self.lbl_hdr_fcl_sub = tk.Label(hdr, text="Consultando periodo actual...", font=("Segoe UI", 9), bg=C_CANVAS, fg=C_TEXT_MUTED)
        self.lbl_hdr_fcl_sub.pack(anchor="w")

        # KPI CARDS PILL BAR
        kpi_bar = tk.Frame(parent, bg=C_CANVAS)
        kpi_bar.pack(fill="x", pady=(0, 8))

        self.kpi_fcl_tot = self.crear_kpi_card_compacta(kpi_bar, "TOTAL DTES", "0", C_INFO)
        self.kpi_fcl_neto = self.crear_kpi_card_compacta(kpi_bar, "MONTO NETO", "$0", C_SUCCESS)
        self.kpi_fcl_iva = self.crear_kpi_card_compacta(kpi_bar, "MONTO IVA", "$0", C_DANGER)
        self.kpi_fcl_total = self.crear_kpi_card_compacta(kpi_bar, "MONTO TOTAL", "$0", C_PURPLE)
        self.kpi_fcl_pdf = self.crear_kpi_card_compacta(kpi_bar, "PDFS GUARDADOS", "0", C_TEAL, click_cb=self.abrir_carpeta_descargas_fcl)

        # TOOLBAR
        tb = tk.Frame(parent, bg=C_SURFACE, padx=10, pady=6, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        tb.pack(fill="x", pady=(0, 6))

        # Caja de búsqueda integrada con botón Limpiar
        box_search_fcl = tk.Frame(tb, bg=C_INPUT, highlightbackground=C_BORDER, highlightthickness=1)
        box_search_fcl.pack(side="left", padx=(0, 10))
        tk.Label(box_search_fcl, text="🔎", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MUTED).pack(side="left", padx=(5, 2))
        self.entry_busqueda_fcl = tk.Entry(
            box_search_fcl,
            textvariable=self.fcl_busqueda_texto,
            font=("Segoe UI", 9),
            bg=C_INPUT,
            fg=C_TEXT_MAIN,
            insertbackground=C_TEXT_MAIN,
            relief="flat",
            width=24
        )
        self.entry_busqueda_fcl.pack(side="left", ipady=2)
        self.entry_busqueda_fcl.bind("<KeyRelease>", lambda e: self.filtrar_tabla_fcl())
        tk.Button(
            box_search_fcl,
            text="✖",
            font=("Segoe UI", 7, "bold"),
            bg=C_INPUT,
            fg=C_TEXT_MUTED,
            activebackground=C_INPUT,
            activeforeground=C_DANGER,
            relief="flat",
            padx=4,
            cursor="hand2",
            command=lambda: [self.fcl_busqueda_texto.set(""), self.filtrar_tabla_fcl()]
        ).pack(side="right", padx=(0, 2))

        tk.Label(tb, text="Tipo Doc:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(side="left", padx=(0, 4))
        self.cb_filtro_fcl = ttk.Combobox(
            tb,
            textvariable=self.fcl_tipo_doc_filtro,
            values=["Todos", "Factura", "Exenta", "Nota Crédito", "Nota Débito", "Guía"],
            width=13,
            state="readonly"
        )
        self.cb_filtro_fcl.pack(side="left", padx=(0, 10))
        self.cb_filtro_fcl.bind("<<ComboboxSelected>>", lambda e: self.filtrar_tabla_fcl())

        self.btn_exp_fcl = tk.Button(
            tb,
            text="📊 Exportar CSV",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=lambda: self.exportar_fcl_seccion_csv("todos")
        )
        self.btn_exp_fcl.pack(side="right")

        self.btn_copy_fcl = tk.Button(
            tb,
            text="📋 Copiar a Excel",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE_ALT,
            fg=C_SUCCESS,
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.copiar_fcl_excel
        )
        self.btn_copy_fcl.pack(side="right", padx=(0, 6))

        # TABLA DE FACTURACIÓN.CL
        tree_frame = tk.Frame(parent, bg=C_CANVAS)
        tree_frame.pack(fill="both", expand=True, pady=(0, 6))

        cols_fcl = ("check", "folio", "tipo_doc", "proveedor", "rut", "fecha_docto", "monto_neto", "monto_iva", "monto_total", "estado_acuse", "pdf_estado")
        self.tree_fcl = ttk.Treeview(tree_frame, columns=cols_fcl, show="headings", selectmode="extended")

        self.tree_fcl.heading("check", text="✓", anchor="center")
        self.tree_fcl.heading("folio", text="Folio", anchor="center", command=lambda: self.ordenar_por_columna_fcl("folio", es_num=True))
        self.tree_fcl.heading("tipo_doc", text="Tipo", anchor="center", command=lambda: self.ordenar_por_columna_fcl("tipo_doc_nombre"))
        self.tree_fcl.heading("proveedor", text="Razón Social / Proveedor", anchor="w", command=lambda: self.ordenar_por_columna_fcl("razon_social"))
        self.tree_fcl.heading("rut", text="RUT Proveedor", anchor="center", command=lambda: self.ordenar_por_columna_fcl("rut_emisor"))
        self.tree_fcl.heading("fecha_docto", text="Fecha", anchor="center", command=lambda: self.ordenar_por_columna_fcl("fecha_docto", es_fecha=True))
        self.tree_fcl.heading("monto_neto", text="Monto Neto", anchor="e", command=lambda: self.ordenar_por_columna_fcl("monto_neto", es_monto=True))
        self.tree_fcl.heading("monto_iva", text="Monto IVA", anchor="e", command=lambda: self.ordenar_por_columna_fcl("monto_iva", es_monto=True))
        self.tree_fcl.heading("monto_total", text="Monto Total", anchor="e", command=lambda: self.ordenar_por_columna_fcl("monto_total", es_monto=True))
        self.tree_fcl.heading("estado_acuse", text="Estado Acuse", anchor="center")
        self.tree_fcl.heading("pdf_estado", text="PDF", anchor="center")

        self.tree_fcl.column("check", width=34, minwidth=34, anchor="center")
        self.tree_fcl.column("folio", width=75, minwidth=60, anchor="center")
        self.tree_fcl.column("tipo_doc", width=95, minwidth=70, anchor="center")
        self.tree_fcl.column("proveedor", width=300, minwidth=180, anchor="w")
        self.tree_fcl.column("rut", width=105, minwidth=90, anchor="center")
        self.tree_fcl.column("fecha_docto", width=85, minwidth=75, anchor="center")
        self.tree_fcl.column("monto_neto", width=105, minwidth=85, anchor="e")
        self.tree_fcl.column("monto_iva", width=95, minwidth=80, anchor="e")
        self.tree_fcl.column("monto_total", width=115, minwidth=95, anchor="e")
        self.tree_fcl.column("estado_acuse", width=95, minwidth=75, anchor="center")
        self.tree_fcl.column("pdf_estado", width=55, minwidth=45, anchor="center")

        sy_fcl = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_fcl.yview)
        self.tree_fcl.configure(yscrollcommand=sy_fcl.set)
        sy_fcl.pack(side="right", fill="y")
        self.tree_fcl.pack(fill="both", expand=True)

        self.tree_fcl.tag_configure("odd", background="#0b1120")
        self.tree_fcl.tag_configure("even", background="#0e1628")
        self.tree_fcl.tag_configure("tipo_33", foreground="#93c5fd")
        self.tree_fcl.tag_configure("tipo_34", foreground="#86efac")
        self.tree_fcl.tag_configure("tipo_61", foreground="#fda4af")
        self.tree_fcl.tag_configure("tipo_56", foreground="#fde047")
        self.tree_fcl.tag_configure("pdf_listo", foreground="#34d399")

        self.tree_fcl.bind("<Double-1>", self.on_doble_clic_fila_fcl)
        self.tree_fcl.bind("<Button-3>", self.mostrar_menu_contextual_fcl)

        # Estado Vacío (Empty State Placeholder)
        self.empty_state_fcl = tk.Frame(tree_frame, bg=C_INPUT)
        lbl_box_fcl = tk.Label(self.empty_state_fcl, text="📄", font=("Segoe UI", 34), bg=C_INPUT, fg="#334155")
        lbl_box_fcl.pack(pady=(0, 4))
        lbl_t_fcl = tk.Label(self.empty_state_fcl, text="No hay DTEs para mostrar", font=("Segoe UI", 11, "bold"), bg=C_INPUT, fg=C_TEXT_MAIN)
        lbl_t_fcl.pack()
        lbl_s_fcl = tk.Label(self.empty_state_fcl, text="Ajusta los filtros o consulta en Facturación.cl", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_DIM)
        lbl_s_fcl.pack(pady=(2, 0))
        self.empty_state_fcl.place(relx=0.5, rely=0.5, anchor="center")

        # BARRA DE ACCIONES INFERIOR
        act_bar_fcl = tk.Frame(parent, bg=C_SURFACE, padx=12, pady=8, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        act_bar_fcl.pack(fill="x")

        left_act_fcl = tk.Frame(act_bar_fcl, bg=C_SURFACE)
        left_act_fcl.pack(side="left")

        self.lbl_seleccion_fcl = tk.Label(left_act_fcl, text="0 DTEs seleccionados", font=("Segoe UI", 9, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN)
        self.lbl_seleccion_fcl.pack(side="left", padx=(0, 10))

        self.btn_sel_todo_fcl = tk.Button(left_act_fcl, text="Seleccionar Todo", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.seleccionar_todo_fcl)
        self.btn_sel_todo_fcl.pack(side="left", padx=(0, 4))
        self.btn_limpiar_sel_fcl = tk.Button(left_act_fcl, text="Limpiar", font=("Segoe UI", 8), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=6, pady=2, cursor="hand2", command=self.limpiar_seleccion_fcl)
        self.btn_limpiar_sel_fcl.pack(side="left")

        right_act_fcl = tk.Frame(act_bar_fcl, bg=C_SURFACE)
        right_act_fcl.pack(side="right")

        self.btn_descargar_fcl_selec = tk.Button(
            right_act_fcl,
            text="📥  DESCARGAR SELECCIÓN",
            font=("Segoe UI", 9, "bold"),
            bg=C_PRIMARY,
            fg="#ffffff",
            activebackground=C_PRIMARY_HOV,
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self.descargar_fcl_seleccionados_lote
        )
        self.btn_descargar_fcl_selec.pack(side="left", padx=(0, 6))

        self.btn_descargar_fcl_todo = tk.Button(
            right_act_fcl,
            text="⚡  DESCARGAR TODOS LOS DTES",
            font=("Segoe UI", 9, "bold"),
            bg=C_SUCCESS,
            fg="#ffffff",
            activebackground=C_SUCCESS_HOV,
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
            command=self.iniciar_descarga_todas_facturacion_cl_pdf
        )
        self.btn_descargar_fcl_todo.pack(side="left")

    # ==========================================================
    # WIDGETS AUXILIARES & TERMINAL
    # ==========================================================
    def crear_kpi_card_compacta(self, parent, titulo, valor_inicial, color_acento, click_cb=None):
        card = tk.Frame(parent, bg=C_SURFACE, padx=14, pady=10, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=4)

        # Determinar icono y fondo del badge según el título
        tit_upper = titulo.upper()
        if "DTE" in tit_upper or "DOC" in tit_upper or "FACTURA" in tit_upper or "BOLETA" in tit_upper:
            ico_txt, bg_badge, fg_ico = "📄", "#0c2844", "#38bdf8"
        elif "NETO" in tit_upper or "BRUTO" in tit_upper or "EXENTA" in tit_upper:
            ico_txt, bg_badge, fg_ico = "🪙", "#093325", "#34d399"
        elif "IVA" in tit_upper or "RETENCI" in tit_upper:
            ico_txt, bg_badge, fg_ico = "%", "#3b121f", "#f43f5e"
        elif "TOTAL" in tit_upper or "LÍQUIDO" in tit_upper or "SUMADO" in tit_upper:
            ico_txt, bg_badge, fg_ico = "💳", "#2a154a", "#a855f7"
        elif "PDF" in tit_upper or "GUARDADO" in tit_upper or "DESCARGA" in tit_upper:
            ico_txt, bg_badge, fg_ico = "📑", "#093230", "#2dd4bf"
        else:
            ico_txt, bg_badge, fg_ico = "⚡", "#1e293b", color_acento

        if click_cb:
            card.configure(cursor="hand2")
            card.bind("<Button-1>", lambda e: click_cb())

        # Contenedor interior horizontal
        inner = tk.Frame(card, bg=C_SURFACE)
        inner.pack(fill="both", expand=True)

        # Badge / Insignia izquierda
        badge = tk.Frame(inner, bg=bg_badge, width=38, height=38, relief="flat")
        badge.pack(side="left", padx=(0, 10))
        badge.pack_propagate(False)

        lbl_ico = tk.Label(badge, text=ico_txt, font=("Segoe UI", 11, "bold"), bg=bg_badge, fg=fg_ico)
        lbl_ico.place(relx=0.5, rely=0.5, anchor="center")

        # Contenedor de texto a la derecha
        txt_col = tk.Frame(inner, bg=C_SURFACE)
        txt_col.pack(side="left", fill="both", expand=True)

        lbl_tit = tk.Label(txt_col, text=titulo, font=("Segoe UI", 7, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED)
        lbl_tit.pack(anchor="w")

        lbl_val = tk.Label(txt_col, text=valor_inicial, font=("Segoe UI", 14, "bold"), bg=C_SURFACE, fg=color_acento)
        lbl_val.pack(anchor="w")

        if click_cb:
            for w in (inner, badge, lbl_ico, txt_col, lbl_tit, lbl_val):
                w.bind("<Button-1>", lambda e: click_cb())

        return lbl_val

    def crear_terminal_inferior(self, parent):
        self.terminal_frame = tk.Frame(parent, bg=C_SURFACE, padx=12, pady=6, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        self.terminal_frame.pack(fill="x", side="bottom")

        bar = tk.Frame(self.terminal_frame, bg=C_SURFACE)
        bar.pack(fill="x")

        self.lbl_status_global = tk.Label(bar, text="●  Listo • Gestor Unificado iniciado.", font=("Segoe UI", 9), bg=C_SURFACE, fg=C_SUCCESS)
        self.lbl_status_global.pack(side="left")

        lbl_ver_status = tk.Label(
            bar,
            text=f"v{VERSION_LOCAL}",
            font=("Segoe UI", 8, "bold"),
            bg=C_SURFACE,
            fg=C_TEXT_DIM,
            padx=8
        )
        lbl_ver_status.pack(side="right")

        self.btn_buscar_updates = tk.Button(
            bar,
            text="🔄 Buscar Actualizaciones",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            activebackground="#223150",
            activeforeground="#ffffff",
            relief="flat",
            highlightbackground=C_BORDER,
            highlightthickness=1,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.buscar_actualizaciones_click
        )
        self.btn_buscar_updates.pack(side="right", padx=(0, 6))

        self.btn_toggle_log = tk.Button(
            bar,
            text="📄 Terminal ▲",
            font=("Segoe UI", 8),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_MAIN,
            activebackground="#223150",
            activeforeground="#ffffff",
            relief="flat",
            highlightbackground=C_BORDER,
            highlightthickness=1,
            padx=10,
            pady=2,
            cursor="hand2",
            command=self.toggle_terminal
        )
        self.btn_toggle_log.pack(side="right")

        self.btn_limpiar_log = tk.Button(
            bar,
            text="Limpiar",
            font=("Segoe UI", 7),
            bg=C_SURFACE_ALT,
            fg=C_TEXT_DIM,
            relief="flat",
            padx=6,
            pady=1,
            cursor="hand2",
            command=self.limpiar_consola
        )

        self.logs_body = tk.Frame(self.terminal_frame, bg=C_SURFACE)
        self.txt_logs = ScrolledText(
            self.logs_body,
            bg=C_INPUT,
            fg=C_TEXT_MAIN,
            insertbackground=C_TEXT_MAIN,
            font=("Consolas", 8),
            height=5,
            relief="flat",
            padx=6,
            pady=4,
            wrap="word"
        )
        self.txt_logs.pack(fill="x", pady=(4, 0))

        self.txt_logs.tag_config("ok", foreground=C_SUCCESS, font=("Consolas", 8, "bold"))
        self.txt_logs.tag_config("error", foreground=C_DANGER, font=("Consolas", 8, "bold"))
        self.txt_logs.tag_config("aviso", foreground=C_WARNING, font=("Consolas", 8, "bold"))
        self.txt_logs.tag_config("info", foreground=C_PRIMARY_HOV, font=("Consolas", 8, "bold"))

        self.terminal_visible = False

    def toggle_terminal(self):
        if self.terminal_visible:
            self.logs_body.pack_forget()
            self.btn_limpiar_log.pack_forget()
            self.btn_toggle_log.config(text="📋 Terminal ▲")
            self.terminal_visible = False
        else:
            self.logs_body.pack(fill="x")
            self.btn_limpiar_log.pack(side="right", padx=(0, 6))
            self.btn_toggle_log.config(text="📋 Terminal ▼")
            self.terminal_visible = True

    def limpiar_consola(self):
        self.txt_logs.delete("1.0", tk.END)

    def log(self, mensaje):
        def _append():
            txt = str(mensaje).strip()
            if not txt:
                return
            tag = None
            if txt.startswith("✓") or "[OK]" in txt or "exitosamente" in txt.lower() or "guardado" in txt.lower():
                tag = "ok"
            elif txt.startswith("⚠️") or "[AVISO]" in txt or "aviso" in txt.lower():
                tag = "aviso"
            elif "error" in txt.lower() or "falló" in txt.lower() or "incorrecto" in txt.lower():
                tag = "error"
            elif txt.startswith("ℹ️") or "[INFO]" in txt:
                tag = "info"

            timestamp = datetime.now().strftime("%H:%M:%S")
            self.txt_logs.insert(tk.END, f"[{timestamp}] {txt}\n", tag)
            self.txt_logs.see(tk.END)
            self.lbl_status_global.config(text=f"🟢 {txt[:90]}...")
        self.after(0, _append)

    def buscar_actualizaciones_click(self):
        try:
            self.btn_buscar_updates.config(state="disabled", text="⏳ Buscando...")
        except Exception:
            pass

        def _restaurar():
            try:
                self.btn_buscar_updates.config(state="normal", text="🔄 Buscar Actualizaciones")
            except Exception:
                pass

        verificar_actualizaciones_manual(
            ventana_padre=self,
            version_actual=VERSION_LOCAL,
            log_cb=self.log,
            status_cb=lambda s: self.lbl_status_global.config(text=s),
            final_cb=_restaurar
        )

    def actualizar_subtitulo_vistas(self):
        emp = self.obtener_empresa_actual()
        nom = emp.get("nombre", "Empresa")
        rut = emp.get("rut", "")
        m = self.sel_mes.get()
        a = self.sel_anio.get()

        sub_txt = f"{nom} (RUT: {rut}) • {m} {a}"
        self.lbl_hdr_fac_sub.config(text=f"{sub_txt} • {len(self.documentos)} facturas cargadas")
        self.lbl_hdr_hn_sub.config(text=f"{sub_txt} • {len(self.boletas_honorarios)} boletas ({self.hn_tipo_consulta.get().capitalize()})")
        self.lbl_hdr_fcl_sub.config(text=f"{nom} • {m} {a} • {len(self.fcl_documentos)} DTEs disponibles")

    def set_estado_interfaz_ocupada(self, ocupada=True, permitir_cancelar=True):
        """
        Bloquea/apaga todos los controles interactivos que no deben usarse
        mientras se ejecuta una consulta o descarga masiva.
        """
        self.en_ejecucion = ocupada
        estado = "disabled" if ocupada else "normal"
        estado_combo = "disabled" if ocupada else "readonly"

        # 1. Navegación de módulos en Sidebar
        for btn in (getattr(self, "btn_nav_facturas", None), getattr(self, "btn_nav_honorarios", None), getattr(self, "btn_nav_facturacion_cl", None)):
            if btn:
                try:
                    btn.config(state=estado)
                except Exception:
                    pass

        # 2. Selector de Empresa y Claves
        if hasattr(self, "cb_empresa"):
            try:
                self.cb_empresa.config(state=estado_combo)
            except Exception:
                pass
        if hasattr(self, "btn_cat"):
            try:
                self.btn_cat.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "btn_sii_creds"):
            try:
                self.btn_sii_creds.config(state=estado)
            except Exception:
                pass

        # 3. Periodo (Mes, Año, Salto ◀ ▶)
        for w in (getattr(self, "btn_mes_prev", None), getattr(self, "btn_mes_next", None)):
            if w:
                try:
                    w.config(state=estado)
                except Exception:
                    pass
        for cb in (getattr(self, "cb_mes", None), getattr(self, "cb_anio", None)):
            if cb:
                try:
                    cb.config(state=estado_combo)
                except Exception:
                    pass

        # 4. Opciones Avanzadas y Checkbuttons
        if hasattr(self, "btn_toggle_opciones"):
            try:
                self.btn_toggle_opciones.config(state=estado)
            except Exception:
                pass
        for chk in (
            getattr(self, "chk_btn_registro", None),
            getattr(self, "chk_btn_pendientes", None),
            getattr(self, "chk_btn_reclamados", None),
            getattr(self, "chk_btn_headless", None)
        ):
            if chk:
                try:
                    chk.config(state=estado)
                except Exception:
                    pass

        # 5. Descargas & IA
        if hasattr(self, "spin_corr"):
            try:
                self.spin_corr.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "chk_ia_btn"):
            try:
                self.chk_ia_btn.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "btn_ia_config"):
            try:
                self.btn_ia_config.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "btn_cambiar_dir"):
            try:
                self.btn_cambiar_dir.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "btn_abrir_dir"):
            try:
                self.btn_abrir_dir.config(state=estado)
            except Exception:
                pass

        # 6. Footer de Sidebar (Desconectar y Salir)
        if hasattr(self, "btn_disc"):
            try:
                self.btn_disc.config(state=estado)
            except Exception:
                pass
        if hasattr(self, "btn_salir"):
            try:
                self.btn_salir.config(state=estado)
            except Exception:
                pass

        # 7. Botones de Acción Vista 1 (Facturas RCV)
        for w in (
            getattr(self, "btn_exp_fac", None),
            getattr(self, "btn_copy_fac", None),
            getattr(self, "btn_sel_todo_fac", None),
            getattr(self, "btn_limpiar_sel_fac", None),
            getattr(self, "btn_descargar_seleccionada", None),
            getattr(self, "btn_descargar_todo_mes", None),
        ):
            if w:
                try:
                    w.config(state=estado)
                except Exception:
                    pass

        # 8. Botones de Acción Vista 2 (Honorarios BHE)
        for w in (
            getattr(self, "rb_hn_rec", None),
            getattr(self, "rb_hn_emi", None),
            getattr(self, "btn_clave_hn", None),
            getattr(self, "btn_exp_hn", None),
            getattr(self, "btn_copy_hn", None),
            getattr(self, "btn_sel_todo_hn", None),
            getattr(self, "btn_limpiar_sel_hn", None),
            getattr(self, "btn_descargar_hn_selec", None),
            getattr(self, "btn_descargar_hn_todo", None),
        ):
            if w:
                try:
                    w.config(state=estado)
                except Exception:
                    pass

        # 9. Botones de Acción Vista 3 (Facturación.cl)
        for w in (
            getattr(self, "btn_cred_fcl", None),
            getattr(self, "cb_filtro_fcl", None),
            getattr(self, "btn_exp_fcl", None),
            getattr(self, "btn_copy_fcl", None),
            getattr(self, "btn_sel_todo_fcl", None),
            getattr(self, "btn_limpiar_sel_fcl", None),
            getattr(self, "btn_descargar_fcl_selec", None),
            getattr(self, "btn_descargar_fcl_todo", None),
        ):
            if w:
                try:
                    if isinstance(w, ttk.Combobox):
                        w.config(state=estado_combo)
                    else:
                        w.config(state=estado)
                except Exception:
                    pass

        # Barra de progreso y botón de consulta/cancelar
        if ocupada:
            self.btn_consultar_sidebar.pack_forget()
            if permitir_cancelar:
                self.btn_cancelar_sidebar.pack(fill="x", pady=(0, 4))
            else:
                self.btn_cancelar_sidebar.pack_forget()
            self.pb_sidebar.pack(fill="x", pady=(0, 6))
            self.pb_sidebar.start(10)
        else:
            self.pb_sidebar.stop()
            self.pb_sidebar.pack_forget()
            self.btn_cancelar_sidebar.pack_forget()
            self.btn_consultar_sidebar.pack(fill="x", pady=(0, 4))
            try:
                self.on_seleccion_fila()
            except Exception:
                pass
            try:
                self.on_seleccion_fila_hn()
            except Exception:
                pass
            try:
                self.on_seleccion_fila_fcl()
            except Exception:
                pass

    # ==========================================================
    # DISPATCHER DE CONSULTA Y DESCARGA SEGÚN MÓDULO ACTIVO
    # ==========================================================
    def iniciar_consulta_actual(self):
        if self.modulo_activo == "facturas":
            self.iniciar_consulta_mes()
        elif self.modulo_activo == "honorarios":
            self.iniciar_consulta_honorarios()
        elif self.modulo_activo == "facturacion_cl":
            self.iniciar_consulta_facturacion_cl()

    def cancelar_consulta_actual(self):
        if self.modulo_activo == "facturas":
            self.cancelar_consulta_rcv()
        elif self.modulo_activo == "honorarios":
            self.cancelar_consulta_hn()
        elif self.modulo_activo == "facturacion_cl":
            self.cancelar_consulta_fcl()

    def seleccionar_carpeta_guardado_actual(self):
        if self.modulo_activo == "facturas":
            self.seleccionar_carpeta_guardado()
        elif self.modulo_activo == "honorarios":
            self.seleccionar_carpeta_guardado_hn()
        elif self.modulo_activo == "facturacion_cl":
            self.seleccionar_carpeta_guardado_fcl()

    def abrir_carpeta_descargas_actual(self):
        if self.modulo_activo == "facturas":
            self.abrir_carpeta_descargas()
        elif self.modulo_activo == "honorarios":
            self.abrir_carpeta_descargas_hn()
        elif self.modulo_activo == "facturacion_cl":
            self.abrir_carpeta_descargas_fcl()

    # ==========================================================
    # MÓDULO 1 (FACTURAS Y RCV) - FUNCIONES OPERATIVAS
    # ==========================================================
    def seleccionar_carpeta_guardado(self):
        d = filedialog.askdirectory(title="Seleccionar Carpeta de Descargas RCV", initialdir=self.download_dir)
        if d:
            script.set_download_dir(d)
            self.download_dir = script.DOWNLOAD_DIR
            self.download_dir_var.set(self.download_dir)
            self.guardar_configuracion()
            self.actualizar_conteo_archivos()
            self.log(f"Carpeta RCV: {self.download_dir}")

    def abrir_carpeta_descargas(self):
        abrir_archivo_o_carpeta(self.download_dir)

    def actualizar_conteo_archivos(self):
        if os.path.exists(self.download_dir):
            c = len(glob.glob(os.path.join(self.download_dir, "*.pdf")))
            self.kpi_pdf.config(text=str(c))

    def on_cambio_correlativo(self):
        self.guardar_configuracion()

    def cancelar_consulta_rcv(self):
        self.cancelar_solicitado = True
        self.log("Cancelación solicitada para consulta RCV...")

    def iniciar_consulta_mes(self):
        if self.en_ejecucion:
            return

        sii_rut, sii_clave = script.recargar_credenciales()
        if not sii_rut or not sii_clave:
            self.dialogo_configurar_sii_credenciales()
            return

        self.cancelar_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        mes_nombre = self.sel_mes.get()
        mes_idx = script.NOMBRES_MESES.index(mes_nombre) if mes_nombre in script.NOMBRES_MESES else datetime.now().month
        anio_val = int(self.sel_anio.get())

        pills = []
        if self.chk_registro.get():
            pills.append("Registro")
        if self.chk_pendientes.get():
            pills.append("Pendientes")
        if self.chk_reclamados.get():
            pills.append("Reclamados")
        if not pills:
            pills = ["Registro", "Pendientes"]

        self.log(f"Consultando RCV para {mes_nombre} {anio_val}...")
        threading.Thread(target=self._hilo_consulta_mes, args=(mes_idx, anio_val, pills), daemon=True).start()

    def _hilo_consulta_mes(self, mes_idx, anio_val, pestanas):
        exito = False
        docs = []
        err_msg = ""
        try:
            docs = script.consultar_resumen_rcv_mes(
                mes_num=mes_idx,
                anio_num=anio_val,
                pestanas=pestanas,
                rut_empresa=script.RUT_EMPRESA,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_consulta_terminada(exito, docs, err_msg))

    def _on_consulta_terminada(self, exito, docs, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito:
            self.documentos = docs
            self.actualizar_estados_pdf_en_datos()
            self.filtrar_tabla()
            self.actualizar_kpis_rcv()
            self.actualizar_subtitulo_vistas()
            self.actualizar_conteo_archivos()
            self.actualizar_badge_sesion(True)
            self.log(f"✓ Consulta completada: {len(docs)} facturas encontradas.")
        else:
            self.actualizar_badge_sesion(False)
            messagebox.showerror("Error al Consultar RCV", f"No se pudo completar la consulta:\n{err_msg}", parent=self)
            self.log(f"Error en consulta: {err_msg}")

    def actualizar_kpis_rcv(self):
        c33 = sum(1 for d in self.documentos if str(d.get("tipo_doc_codigo")) == "33" or str(d.get("tipo_doc")) == "33")
        c34 = sum(1 for d in self.documentos if str(d.get("tipo_doc_codigo")) == "34" or str(d.get("tipo_doc")) == "34")
        cpen = sum(1 for d in self.documentos if d.get("estado_rcv") == "Pendientes")
        s_iva = sum(d.get("monto_iva", 0) for d in self.documentos)
        s_tot = sum(d.get("monto_total", 0) for d in self.documentos)

        self.kpi_fac.config(text=str(c33))
        self.kpi_exe.config(text=str(c34))
        self.kpi_pen.config(text=str(cpen))
        self.kpi_iva.config(text=f"${s_iva:,}".replace(",", "."))
        self.kpi_tot.config(text=f"${s_tot:,}".replace(",", "."))

    def buscar_archivo_pdf_documento(self, doc):
        if not self.download_dir or not os.path.exists(self.download_dir):
            return None
        folio = str(doc.get("folio", "")).strip()
        if not folio:
            return None
        patrones = [f"*_{folio}_*", f"*_{folio},*", f"*Folio_{folio}_*", f"*Folio_{folio},*", f"*#{folio}*"]
        for p in patrones:
            encontrados = glob.glob(os.path.join(self.download_dir, p))
            for f in encontrados:
                if f.lower().endswith(".pdf"):
                    return f
        return None

    def actualizar_estados_pdf_en_datos(self):
        for d in self.documentos:
            d["pdf_ruta"] = self.buscar_archivo_pdf_documento(d)

    def filtrar_tabla(self):
        for it in self.tree.get_children():
            self.tree.delete(it)

        q = self.busqueda_texto.get().strip().lower()
        filtro_est = self.filtro_estado.get()

        self.documentos_visibles = []
        for d in self.documentos:
            if filtro_est != "Todos" and d.get("estado_rcv") != filtro_est:
                continue
            if q:
                match = (
                    q in str(d.get("folio", "")).lower() or
                    q in str(d.get("razon_social", "")).lower() or
                    q in str(d.get("rut_emisor", "")).lower() or
                    q in str(d.get("tipo_doc_nombre", "")).lower()
                )
                if not match:
                    continue
            self.documentos_visibles.append(d)

        for i, d in enumerate(self.documentos_visibles):
            tag_strip = "even" if i % 2 == 0 else "odd"
            tags = [tag_strip]
            tipo_cod = str(d.get("tipo_doc_codigo", d.get("tipo_doc", ""))).strip()
            if tipo_cod in ("33", "34", "61", "56"):
                tags.append(f"tipo_{tipo_cod}")
            pdf_str = "🟢" if d.get("pdf_ruta") else "📥"
            if d.get("pdf_ruta"):
                tags.append("pdf_listo")
            if d.get("estado_rcv") == "Pendientes":
                tags.append("pendiente")
            elif d.get("estado_rcv") == "Reclamados":
                tags.append("reclamado")

            valores = (
                "☐",
                d.get("folio", ""),
                d.get("tipo_doc_nombre", d.get("tipo_doc", "")),
                d.get("razon_social", ""),
                d.get("rut_emisor", ""),
                d.get("fecha_docto", ""),
                f"${d.get('monto_neto', 0):,}".replace(",", "."),
                f"${d.get('monto_iva', 0):,}".replace(",", "."),
                f"${d.get('monto_total', 0):,}".replace(",", "."),
                d.get("estado_rcv", "Registro"),
                pdf_str
            )
            self.tree.insert("", "end", iid=str(i), values=valores, tags=tuple(tags))

        if not self.documentos_visibles:
            self.empty_state_fac.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_state_fac.place_forget()

        self.on_seleccion_fila()

    def on_seleccion_fila(self, event=None):
        sel = self.tree.selection()
        total_sel = len(sel)
        if total_sel > 0:
            monto_sel = 0
            for it in sel:
                try:
                    idx = int(it)
                    monto_sel += self.documentos_visibles[idx].get("monto_total", 0)
                except Exception:
                    pass
            self.lbl_seleccion_resumen.config(text=f"✓ {total_sel} seleccionadas • Total: ${monto_sel:,}".replace(",", "."))
            self.btn_descargar_seleccionada.config(text=f"📥  DESCARGAR SELECCIÓN ({total_sel})")
        else:
            self.lbl_seleccion_resumen.config(text=f"0 de {len(self.documentos_visibles)} seleccionadas")
            self.btn_descargar_seleccionada.config(text="📥  DESCARGAR SELECCIÓN")

    def seleccionar_todo_rcv(self):
        self.tree.selection_set(self.tree.get_children())
        self.on_seleccion_fila()

    def limpiar_seleccion_rcv(self):
        self.tree.selection_set([])
        self.on_seleccion_fila()

    def ordenar_por_columna(self, col, es_num=False, es_monto=False, es_fecha=False):
        asc = self.orden_columnas_asc.get(col, True)
        self.orden_columnas_asc[col] = not asc

        def _key(d):
            val = d.get(col, "")
            if es_fecha:
                return parse_fecha_dt(val)
            if es_monto or es_num:
                try:
                    return float(str(val).replace("$", "").replace(".", "").replace(",", ".").strip() or 0)
                except Exception:
                    return 0
            return str(val).lower()

        self.documentos.sort(key=_key, reverse=not asc)
        self.filtrar_tabla()

    def on_cambio_orden(self, event=None):
        val = self.cb_orden.get()
        if "fecha_asc" in val or "Menor" in val and "Fecha" in val:
            self.documentos.sort(key=lambda d: parse_fecha_dt(d.get("fecha_docto", "")))
        elif "fecha_desc" in val or "Fecha" in val:
            self.documentos.sort(key=lambda d: parse_fecha_dt(d.get("fecha_docto", "")), reverse=True)
        elif "iva_desc" in val or "IVA" in val:
            self.documentos.sort(key=lambda d: d.get("monto_iva", 0), reverse=True)
        elif "monto_desc" in val or "Mayor" in val:
            self.documentos.sort(key=lambda d: d.get("monto_total", 0), reverse=True)
        elif "monto_asc" in val:
            self.documentos.sort(key=lambda d: d.get("monto_total", 0))
        self.filtrar_tabla()

    def on_doble_clic_fila(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        doc = self.documentos_visibles[idx]
        if doc.get("pdf_ruta") and os.path.exists(doc["pdf_ruta"]):
            VentanaVisorPDF(self, doc["pdf_ruta"], doc_info=doc)
        else:
            self.descargar_factura_individual_doc(doc)

    def mostrar_menu_contextual(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        self.on_seleccion_fila()
        idx = int(item)
        doc = self.documentos_visibles[idx]

        m = tk.Menu(self, tearoff=0, bg=C_SURFACE, fg=C_TEXT_MAIN, activebackground=C_PRIMARY, activeforeground="#ffffff")
        if doc.get("pdf_ruta") and os.path.exists(doc["pdf_ruta"]):
            m.add_command(label="👁️  Previsualizar en Visor PDF", font=("Segoe UI", 9, "bold"), command=lambda: VentanaVisorPDF(self, doc["pdf_ruta"], doc_info=doc))
            m.add_command(label="📄  Abrir con Lector Externo", command=lambda: abrir_archivo_o_carpeta(doc["pdf_ruta"]))
            m.add_command(label="📁  Mostrar en Carpeta", command=lambda: abrir_archivo_o_carpeta(os.path.dirname(doc["pdf_ruta"])))
        else:
            m.add_command(label="📥  Descargar y Ver PDF", command=lambda: self.descargar_factura_individual_doc(doc))
        m.add_separator()
        m.add_command(label="📋  Copiar RUT Emisor", command=lambda: self.copiar_al_portapapeles(doc.get("rut_emisor", "")))
        m.add_command(label="📋  Copiar Folio", command=lambda: self.copiar_al_portapapeles(str(doc.get("folio", ""))))
        m.add_command(label="📋  Copiar Razón Social", command=lambda: self.copiar_al_portapapeles(doc.get("razon_social", "")))
        m.tk_popup(event.x_root, event.y_root)

    def copiar_al_portapapeles(self, texto):
        self.clipboard_clear()
        self.clipboard_append(texto)
        self.log(f"Copiado: {texto}")

    def descargar_factura_individual_doc(self, doc):
        if self.en_ejecucion:
            return
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=False)

        folio = doc.get("folio", "")
        self.log(f"Descargando PDF individual folio #{folio}...")
        threading.Thread(target=self._hilo_descarga_individual, args=(doc,), daemon=True).start()

    def _hilo_descarga_individual(self, doc):
        exito = False
        ruta = None
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            ruta, corr_final = script.descargar_factura_individual(
                doc=doc,
                correlativo_actual=self.correlativo_val.get(),
                contexto_usuario=self.contexto_val.get(),
                usar_ia=self.chk_usar_ia.get(),
                gemini_api_key=self.gemini_api_key,
                openai_api_key=self.openai_api_key,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_individual_terminada(exito, ruta, corr_final, err_msg))

    def _on_descarga_individual_terminada(self, exito, ruta, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito:
            if corr_final is not None:
                self.correlativo_val.set(corr_final)
                self.guardar_configuracion()
            self.actualizar_estados_pdf_en_datos()
            self.filtrar_tabla()
            self.actualizar_conteo_archivos()
            self.log(f"✓ PDF descargado exitosamente: {os.path.basename(ruta)}")
            if ruta and os.path.exists(ruta):
                abrir_archivo_o_carpeta(ruta)
        else:
            messagebox.showwarning("Aviso de Descarga", f"No se pudo descargar el PDF:\n{err_msg}", parent=self)
            self.log(f"Aviso descarga individual: {err_msg}")

    def descargar_facturas_seleccionadas_lote(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Descarga", "Selecciona al menos una factura en la tabla para descargar.", parent=self)
            return
        folios = [self.documentos_visibles[int(i)].get("folio") for i in sel if str(self.documentos_visibles[int(i)].get("folio")).strip()]
        if not folios:
            return
        self.iniciar_descarga_lote_folios(folios)

    def iniciar_descarga_todas_pdf(self):
        if not self.documentos:
            messagebox.showinfo("Descarga", "Primero debes consultar las facturas del mes.", parent=self)
            return
        self.iniciar_descarga_lote_folios(None)

    def iniciar_descarga_lote_folios(self, folios_lista):
        if self.en_ejecucion:
            return
        self.cancelar_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        mes_nombre = self.sel_mes.get()
        mes_idx = script.NOMBRES_MESES.index(mes_nombre) if mes_nombre in script.NOMBRES_MESES else datetime.now().month
        anio_val = int(self.sel_anio.get())

        total_a_descargar = len(folios_lista) if folios_lista else len(self.documentos)
        self.log(f"Iniciando descarga de {total_a_descargar} PDFs...")
        threading.Thread(target=self._hilo_descarga_lote, args=(mes_idx, anio_val, folios_lista), daemon=True).start()

    def _hilo_descarga_lote(self, mes_idx, anio_val, folios_lista):
        exito = False
        total_desc = 0
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            exito, total_desc, msg, archivos, corr_final = script.descargar_facturas_pdf_mes(
                mes_num=mes_idx,
                anio_num=anio_val,
                folios_especificos=folios_lista,
                correlativo_inicial=self.correlativo_val.get(),
                contexto=self.contexto_val.get(),
                usar_ia=self.chk_usar_ia.get(),
                api_key_gemini=self.gemini_api_key,
                api_key_openai=self.openai_api_key,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_todas_terminada(exito, total_desc, corr_final, err_msg))

    def _on_descarga_todas_terminada(self, exito, total_desc, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if corr_final is not None:
            self.correlativo_val.set(corr_final)
            self.guardar_configuracion()

        self.actualizar_estados_pdf_en_datos()
        self.filtrar_tabla()
        self.actualizar_conteo_archivos()

        if exito:
            self.log(f"✓ Descarga finalizada: {total_desc} PDFs guardados en {self.download_dir}")
            messagebox.showinfo("Descarga Finalizada", f"Se descargaron correctamente {total_desc} archivos PDF.\n\nGuardados en:\n{self.download_dir}", parent=self)
        else:
            messagebox.showwarning("Aviso de Descarga", f"Resultado de la descarga:\n{err_msg}", parent=self)

    def exportar_rcv_csv(self):
        if not self.documentos:
            messagebox.showinfo("Exportar", "No hay facturas cargadas para exportar.", parent=self)
            return
        mes_nom = self.sel_mes.get()
        a_val = self.sel_anio.get()
        emp_nom = re.sub(r'[^a-zA-Z0-9]', '_', self.obtener_empresa_actual().get("nombre", "Empresa"))
        nombre_def = f"RCV_Compras_{emp_nom}_{mes_nom}_{a_val}.csv"
        ruta = filedialog.asksaveasfilename(title="Guardar Resumen CSV", initialfile=nombre_def, defaultextension=".csv", filetypes=[("Archivos CSV", "*.csv")])
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Folio", "Tipo Documento", "Código Tipo", "Razón Social Proveedor", "RUT Emisor", "Fecha Docto", "Monto Neto", "Monto Exento", "Monto IVA", "Monto Total", "Estado RCV", "PDF Guardado"])
                for d in self.documentos:
                    w.writerow([
                        d.get("folio", ""),
                        d.get("tipo_doc_nombre", ""),
                        d.get("tipo_doc_codigo", ""),
                        d.get("razon_social", ""),
                        d.get("rut_emisor", ""),
                        d.get("fecha_docto", ""),
                        d.get("monto_neto", 0),
                        d.get("monto_exento", 0),
                        d.get("monto_iva", 0),
                        d.get("monto_total", 0),
                        d.get("estado_rcv", ""),
                        "SÍ" if d.get("pdf_ruta") else "NO"
                    ])
            self.log(f"✓ Archivo CSV exportado: {os.path.basename(ruta)}")
            messagebox.showinfo("Exportación Exitosa", f"Archivo CSV guardado correctamente en:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Exportar", f"No se pudo guardar el archivo CSV:\n{e}", parent=self)

    def copiar_rcv_excel(self):
        docs = self.documentos_visibles if self.documentos_visibles else self.documentos
        if not docs:
            messagebox.showinfo("Copiar a Excel", "No hay facturas visibles en la tabla para copiar.", parent=self)
            return
        try:
            lineas = []
            lineas.append("\t".join(["Folio", "Tipo Documento", "Código Tipo", "Razón Social Proveedor", "RUT Emisor", "Fecha Docto", "Monto Neto", "Monto Exento", "Monto IVA", "Monto Total", "Estado RCV", "PDF Guardado"]))
            for d in docs:
                lineas.append("\t".join([
                    str(d.get("folio", "")),
                    str(d.get("tipo_doc_nombre", "")),
                    str(d.get("tipo_doc_codigo", "")),
                    str(d.get("razon_social", "")),
                    str(d.get("rut_emisor", "")),
                    str(d.get("fecha_docto", "")),
                    str(d.get("monto_neto", 0)),
                    str(d.get("monto_exento", 0)),
                    str(d.get("monto_iva", 0)),
                    str(d.get("monto_total", 0)),
                    str(d.get("estado_rcv", "")),
                    "SÍ" if d.get("pdf_ruta") else "NO"
                ]))
            tsv_data = "\n".join(lineas)
            self.clipboard_clear()
            self.clipboard_append(tsv_data)
            self.update()
            self.log(f"✓ {len(docs)} facturas copiadas al portapapeles. ¡Pégalas en Excel con Ctrl + V!")
            messagebox.showinfo("Copiado al Portapapeles", f"Se han copiado {len(docs)} facturas al portapapeles con éxito.\n\nPuedes pegarlas directamente en Excel con Ctrl + V.", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Copiar", f"No se pudieron copiar los datos:\n{e}", parent=self)

    # ==========================================================
    # MÓDULO 2 (BOLETAS DE HONORARIOS BHE) - OPERATIVO
    # ==========================================================
    def seleccionar_carpeta_guardado_hn(self):
        d = filedialog.askdirectory(title="Seleccionar Carpeta de Boletas de Honorarios", initialdir=self.hn_download_dir)
        if d:
            script_honorarios.gestor_honorarios.set_download_dir(d)
            self.hn_download_dir = script_honorarios.gestor_honorarios.download_dir
            self.hn_download_dir_var.set(self.hn_download_dir)
            self.guardar_configuracion()
            self.actualizar_conteo_archivos_hn()
            self.log(f"Carpeta BHE: {self.hn_download_dir}")

    def abrir_carpeta_descargas_hn(self):
        abrir_archivo_o_carpeta(self.hn_download_dir)

    def actualizar_conteo_archivos_hn(self):
        if os.path.exists(self.hn_download_dir):
            c = len(glob.glob(os.path.join(self.hn_download_dir, "*.pdf")))
            self.kpi_hn_pdf.config(text=str(c))

    def cancelar_consulta_hn(self):
        self.cancelar_hn_solicitado = True
        self.log("Cancelación solicitada para consulta de Honorarios...")

    def abrir_dialogo_credenciales_hn(self):
        emp = self.obtener_empresa_actual()
        rut_sug = emp.get("rut", self.hn_rut_empresa_var.get())
        clave_sug = emp.get("clave_sii", self.hn_clave_empresa_var.get())

        v = tk.Toplevel(self)
        v.title("Credenciales Boletas de Honorarios (SII)")
        v.geometry("460x280")
        v.configure(bg=C_CANVAS)
        v.transient(self)
        v.grab_set()

        p = tk.Frame(v, bg=C_SURFACE, padx=16, pady=16)
        p.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(p, text="🔑 Credenciales de Empresa para BHE", font=("Segoe UI", 11, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 6))
        tk.Label(p, text="El portal de Boletas de Honorarios requiere el RUT y Clave Tributaria del SII de la empresa.", font=("Segoe UI", 8), bg=C_SURFACE, fg=C_TEXT_MUTED, wraplength=400, justify="left").pack(anchor="w", pady=(0, 12))

        tk.Label(p, text="RUT Empresa:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_rut = tk.Entry(p, textvariable=self.hn_rut_empresa_var, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_rut.pack(fill="x", pady=(0, 8))

        tk.Label(p, text="Clave Tributaria SII:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_pwd = tk.Entry(p, textvariable=self.hn_clave_empresa_var, show="•", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_pwd.pack(fill="x", pady=(0, 14))

        def _guardar():
            rut = self.hn_rut_empresa_var.get().strip()
            clave = self.hn_clave_empresa_var.get().strip()
            for e in self.empresas:
                if e.get("rut", "").replace("-", "").replace(".", "").upper() == rut.replace("-", "").replace(".", "").upper():
                    e["clave_sii"] = clave
            self.guardar_empresas(self.empresas)
            self.guardar_configuracion()
            self.log(f"Credenciales de Honorarios guardadas para RUT {rut}.")
            v.destroy()

        btn_bar = tk.Frame(p, bg=C_SURFACE)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="Guardar Credenciales", font=("Segoe UI", 9, "bold"), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=14, pady=4, cursor="hand2", command=_guardar).pack(side="right")
        tk.Button(btn_bar, text="Cancelar", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=10, pady=4, cursor="hand2", command=v.destroy).pack(side="right", padx=(0, 6))

    def iniciar_consulta_honorarios(self):
        if self.en_ejecucion:
            return
        rut_emp = self.hn_rut_empresa_var.get().strip()
        clave_emp = self.hn_clave_empresa_var.get().strip()
        if not rut_emp or not clave_emp:
            self.abrir_dialogo_credenciales_hn()
            return

        self.cancelar_hn_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        mes_nombre = self.sel_mes.get()
        mes_idx = script.NOMBRES_MESES.index(mes_nombre) if mes_nombre in script.NOMBRES_MESES else datetime.now().month
        anio_val = int(self.sel_anio.get())
        tipo_val = self.hn_tipo_consulta.get()

        self.log(f"Consultando Boletas de Honorarios ({tipo_val.capitalize()}) para {mes_nombre} {anio_val}...")
        threading.Thread(target=self._hilo_consulta_honorarios, args=(rut_emp, clave_emp, mes_idx, anio_val, tipo_val), daemon=True).start()

    def _hilo_consulta_honorarios(self, rut_emp, clave_emp, mes_idx, anio_val, tipo_val):
        exito = False
        boletas = []
        err_msg = ""
        try:
            boletas = script_honorarios.consultar_resumen_honorarios_mes(
                rut_empresa=rut_emp,
                clave_empresa=clave_emp,
                mes_num=mes_idx,
                anio_num=anio_val,
                tipo=tipo_val,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_consulta_honorarios_terminada(exito, boletas, err_msg))

    def _on_consulta_honorarios_terminada(self, exito, boletas, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito:
            self.boletas_honorarios = boletas
            self.actualizar_estados_pdf_honorarios()
            self.filtrar_tabla_honorarios()
            self.actualizar_kpis_honorarios()
            self.actualizar_subtitulo_vistas()
            self.actualizar_conteo_archivos_hn()
            self.log(f"✓ Consulta de Honorarios completada: {len(boletas)} boletas encontradas.")
        else:
            messagebox.showerror("Error al Consultar Honorarios", f"No se pudo consultar Boletas de Honorarios:\n{err_msg}", parent=self)
            self.log(f"Error consulta honorarios: {err_msg}")

    def actualizar_kpis_honorarios(self):
        s_bruto = sum(b.get("monto_bruto", 0) for b in self.boletas_honorarios)
        s_ret = sum(b.get("retencion", 0) for b in self.boletas_honorarios)
        s_liq = sum(b.get("monto_liquido", 0) for b in self.boletas_honorarios)

        self.kpi_hn_tot.config(text=str(len(self.boletas_honorarios)))
        self.kpi_hn_bruto.config(text=f"${s_bruto:,}".replace(",", "."))
        self.kpi_hn_ret.config(text=f"${s_ret:,}".replace(",", "."))
        self.kpi_hn_liq.config(text=f"${s_liq:,}".replace(",", "."))

    def buscar_archivo_pdf_boleta(self, boleta):
        if not self.hn_download_dir or not os.path.exists(self.hn_download_dir):
            return None
        folio = str(boleta.get("folio", "")).strip()
        if not folio:
            return None
        patrones = [f"*Bol*#{folio}*", f"*BHE*#{folio}*", f"*_Folio_{folio}_*", f"*#{folio}*"]
        for p in patrones:
            for f in glob.glob(os.path.join(self.hn_download_dir, p)):
                if f.lower().endswith(".pdf"):
                    return f
        return None

    def actualizar_estados_pdf_honorarios(self):
        for b in self.boletas_honorarios:
            b["pdf_ruta"] = self.buscar_archivo_pdf_boleta(b)

    def filtrar_tabla_honorarios(self):
        for it in self.tree_hn.get_children():
            self.tree_hn.delete(it)

        q = self.hn_busqueda_texto.get().strip().lower()
        self.boletas_honorarios_visibles = []
        for b in self.boletas_honorarios:
            if q:
                match = (
                    q in str(b.get("folio", "")).lower() or
                    q in str(b.get("emisor", "")).lower() or
                    q in str(b.get("rut", "")).lower() or
                    q in str(b.get("glosa", "")).lower()
                )
                if not match:
                    continue
            self.boletas_honorarios_visibles.append(b)

        for i, b in enumerate(self.boletas_honorarios_visibles):
            tag_strip = "even" if i % 2 == 0 else "odd"
            tags = [tag_strip]
            if "anulad" in str(b.get("estado", "")).lower() or "anulad" in str(b.get("glosa", "")).lower():
                tags.append("bhe_anulada")
            else:
                tags.append("bhe_activa")
            pdf_str = "🟢" if b.get("pdf_ruta") else "📥"
            if b.get("pdf_ruta"):
                tags.append("pdf_listo")

            valores = (
                "☐",
                b.get("folio", ""),
                b.get("fecha", ""),
                b.get("emisor", ""),
                b.get("rut", ""),
                f"${b.get('monto_bruto', 0):,}".replace(",", "."),
                f"${b.get('retencion', 0):,}".replace(",", "."),
                f"${b.get('monto_liquido', 0):,}".replace(",", "."),
                b.get("glosa", ""),
                pdf_str
            )
            self.tree_hn.insert("", "end", iid=str(i), values=valores, tags=tuple(tags))

        if not self.boletas_honorarios_visibles:
            self.empty_state_hn.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_state_hn.place_forget()

        self.on_seleccion_fila_hn()

    def on_seleccion_fila_hn(self, event=None):
        sel = self.tree_hn.selection()
        total_sel = len(sel)
        if total_sel > 0:
            monto_sel = sum(self.boletas_honorarios_visibles[int(i)].get("monto_liquido", 0) for i in sel if int(i) < len(self.boletas_honorarios_visibles))
            self.lbl_seleccion_hn.config(text=f"✓ {total_sel} seleccionadas • Líquido: ${monto_sel:,}".replace(",", "."))
            self.btn_descargar_hn_selec.config(text=f"📥  DESCARGAR SELECCIÓN ({total_sel})")
        else:
            self.lbl_seleccion_hn.config(text=f"0 de {len(self.boletas_honorarios_visibles)} seleccionadas")
            self.btn_descargar_hn_selec.config(text="📥  DESCARGAR SELECCIÓN")

    def seleccionar_todo_hn(self):
        self.tree_hn.selection_set(self.tree_hn.get_children())
        self.on_seleccion_fila_hn()

    def limpiar_seleccion_hn(self):
        self.tree_hn.selection_set([])
        self.on_seleccion_fila_hn()

    def ordenar_por_columna_honorarios(self, col, es_num=False, es_monto=False, es_fecha=False):
        asc = self.hn_orden_columnas_asc.get(col, True)
        self.hn_orden_columnas_asc[col] = not asc

        def _key(b):
            val = b.get(col, "")
            if es_fecha:
                return parse_fecha_dt(val)
            if es_monto or es_num:
                try:
                    return float(str(val).replace("$", "").replace(".", "").replace(",", ".").strip() or 0)
                except Exception:
                    return 0
            return str(val).lower()

        self.boletas_honorarios.sort(key=_key, reverse=not asc)
        self.filtrar_tabla_honorarios()

    def on_doble_clic_fila_hn(self, event):
        item = self.tree_hn.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        b = self.boletas_honorarios_visibles[idx]
        if b.get("pdf_ruta") and os.path.exists(b["pdf_ruta"]):
            VentanaVisorPDF(self, b["pdf_ruta"], doc_info=b)
        else:
            self.descargar_boleta_individual_doc(b)

    def mostrar_menu_contextual_hn(self, event):
        item = self.tree_hn.identify_row(event.y)
        if not item:
            return
        self.tree_hn.selection_set(item)
        self.on_seleccion_fila_hn()
        idx = int(item)
        b = self.boletas_honorarios_visibles[idx]

        m = tk.Menu(self, tearoff=0, bg=C_SURFACE, fg=C_TEXT_MAIN, activebackground=C_PRIMARY, activeforeground="#ffffff")
        if b.get("pdf_ruta") and os.path.exists(b["pdf_ruta"]):
            m.add_command(label="👁️  Previsualizar en Visor PDF", font=("Segoe UI", 9, "bold"), command=lambda: VentanaVisorPDF(self, b["pdf_ruta"], doc_info=b))
            m.add_command(label="📄  Abrir con Lector Externo", command=lambda: abrir_archivo_o_carpeta(b["pdf_ruta"]))
            m.add_command(label="📁  Mostrar en Carpeta", command=lambda: abrir_archivo_o_carpeta(os.path.dirname(b["pdf_ruta"])))
        else:
            m.add_command(label="📥  Descargar y Ver PDF", command=lambda: self.descargar_boleta_individual_doc(b))
        m.add_separator()
        m.add_command(label="ℹ️  Ver Detalle Completo", command=lambda: self.mostrar_detalle_boleta(b))
        m.add_command(label="📋  Copiar RUT", command=lambda: self.copiar_al_portapapeles(b.get("rut", "")))
        m.add_command(label="📋  Copiar Folio", command=lambda: self.copiar_al_portapapeles(str(b.get("folio", ""))))
        m.tk_popup(event.x_root, event.y_root)

    def mostrar_detalle_boleta(self, b):
        v = tk.Toplevel(self)
        v.title(f"Detalle Boleta #{b.get('folio', '')}")
        v.geometry("520x420")
        v.configure(bg=C_CANVAS)
        v.transient(self)

        p = tk.Frame(v, bg=C_SURFACE, padx=16, pady=16)
        p.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(p, text=f"Boleta de Honorarios #{b.get('folio', '')}", font=("Segoe UI", 12, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 10))

        def _fila(lbl, val):
            r = tk.Frame(p, bg=C_SURFACE)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=lbl, font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED, width=16, anchor="w").pack(side="left")
            tk.Label(r, text=str(val), font=("Segoe UI", 9), bg=C_SURFACE, fg=C_TEXT_MAIN, anchor="w").pack(side="left", fill="x", expand=True)

        _fila("Emisor:", b.get("emisor", ""))
        _fila("RUT:", b.get("rut", ""))
        _fila("Fecha:", b.get("fecha", ""))
        _fila("Monto Bruto:", f"${b.get('monto_bruto', 0):,}".replace(",", "."))
        _fila("Retención:", f"${b.get('retencion', 0):,}".replace(",", "."))
        _fila("Monto Líquido:", f"${b.get('monto_liquido', 0):,}".replace(",", "."))

        tk.Label(p, text="Glosa / Detalle de Servicios:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(10, 2))
        txt_g = tk.Text(p, height=4, bg=C_INPUT, fg=C_TEXT_MAIN, font=("Segoe UI", 9), relief="flat", wrap="word")
        txt_g.insert("1.0", b.get("glosa", "Sin descripción registrada"))
        txt_g.config(state="disabled")
        txt_g.pack(fill="x", pady=(0, 12))

        tk.Button(p, text="Cerrar", font=("Segoe UI", 9), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=14, pady=4, cursor="hand2", command=v.destroy).pack(side="right")

    def descargar_boleta_individual_doc(self, boleta):
        if self.en_ejecucion:
            return
        rut_emp = self.hn_rut_empresa_var.get().strip()
        clave_emp = self.hn_clave_empresa_var.get().strip()
        if not rut_emp or not clave_emp:
            self.abrir_dialogo_credenciales_hn()
            return

        self.set_estado_interfaz_ocupada(True, permitir_cancelar=False)

        folio = boleta.get("folio", "")
        self.log(f"Descargando boleta individual #{folio}...")
        threading.Thread(target=self._hilo_descarga_boleta_individual, args=(boleta, rut_emp, clave_emp), daemon=True).start()

    def _hilo_descarga_boleta_individual(self, boleta, rut_emp, clave_emp):
        exito = False
        ruta = None
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            ruta, corr_final = script_honorarios.descargar_boleta_individual(
                boleta=boleta,
                rut_empresa=rut_emp,
                clave_empresa=clave_emp,
                tipo=self.hn_tipo_consulta.get(),
                correlativo_actual=self.correlativo_val.get(),
                contexto_usuario=self.hn_contexto_val.get(),
                usar_ia=self.hn_chk_usar_ia.get(),
                gemini_api_key=self.gemini_api_key,
                openai_api_key=self.openai_api_key,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_boleta_terminada(exito, ruta, corr_final, err_msg))

    def _on_descarga_boleta_terminada(self, exito, ruta, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito:
            if corr_final is not None:
                self.correlativo_val.set(corr_final)
                self.guardar_configuracion()
            self.actualizar_estados_pdf_honorarios()
            self.filtrar_tabla_honorarios()
            self.actualizar_conteo_archivos_hn()
            self.log(f"✓ Boleta descargada con éxito: {os.path.basename(ruta)}")
            if ruta and os.path.exists(ruta):
                abrir_archivo_o_carpeta(ruta)
        else:
            messagebox.showwarning("Aviso de Descarga", f"No se pudo descargar la boleta:\n{err_msg}", parent=self)
            self.log(f"Aviso descarga boleta: {err_msg}")

    def descargar_boletas_seleccionadas_lote(self):
        sel = self.tree_hn.selection()
        if not sel:
            messagebox.showinfo("Descarga", "Selecciona al menos una boleta para descargar.", parent=self)
            return
        folios = [self.boletas_honorarios_visibles[int(i)].get("folio") for i in sel if str(self.boletas_honorarios_visibles[int(i)].get("folio")).strip()]
        self.iniciar_descarga_lote_honorarios(folios)

    def iniciar_descarga_todas_honorarios_pdf(self):
        if not self.boletas_honorarios:
            messagebox.showinfo("Descarga", "Primero debes consultar las boletas de honorarios.", parent=self)
            return
        self.iniciar_descarga_lote_honorarios(None)

    def iniciar_descarga_lote_honorarios(self, folios_lista):
        if self.en_ejecucion:
            return
        rut_emp = self.hn_rut_empresa_var.get().strip()
        clave_emp = self.hn_clave_empresa_var.get().strip()
        if not rut_emp or not clave_emp:
            self.abrir_dialogo_credenciales_hn()
            return

        self.cancelar_hn_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        mes_nombre = self.sel_mes.get()
        mes_idx = script.NOMBRES_MESES.index(mes_nombre) if mes_nombre in script.NOMBRES_MESES else datetime.now().month
        anio_val = int(self.sel_anio.get())
        tipo_val = self.hn_tipo_consulta.get()

        total = len(folios_lista) if folios_lista else len(self.boletas_honorarios)
        self.log(f"Descargando {total} boletas de honorarios...")
        threading.Thread(target=self._hilo_descarga_todas_honorarios, args=(rut_emp, clave_emp, mes_idx, anio_val, tipo_val, folios_lista), daemon=True).start()

    def _hilo_descarga_todas_honorarios(self, rut_emp, clave_emp, mes_idx, anio_val, tipo_val, folios_lista):
        exito = False
        total = 0
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            total, corr_final = script_honorarios.ejecutar_descarga_completa_honorarios(
                rut_empresa=rut_emp,
                clave_empresa=clave_emp,
                mes_num=mes_idx,
                anio_num=anio_val,
                tipo=tipo_val,
                folios_especificos=folios_lista,
                correlativo_inicial=self.correlativo_val.get(),
                contexto_usuario=self.hn_contexto_val.get(),
                usar_ia=self.hn_chk_usar_ia.get(),
                gemini_api_key=self.gemini_api_key,
                openai_api_key=self.openai_api_key,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_todas_honorarios_terminada(exito, total, corr_final, err_msg))

    def _on_descarga_todas_honorarios_terminada(self, exito, total, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if corr_final is not None:
            self.correlativo_val.set(corr_final)
            self.guardar_configuracion()

        self.actualizar_estados_pdf_honorarios()
        self.filtrar_tabla_honorarios()
        self.actualizar_conteo_archivos_hn()

        if exito:
            self.log(f"✓ Descarga finalizada: {total} boletas guardadas en {self.hn_download_dir}")
            messagebox.showinfo("Descarga Finalizada", f"Se descargaron correctamente {total} boletas PDF.\n\nGuardadas en:\n{self.hn_download_dir}", parent=self)
        else:
            messagebox.showwarning("Aviso de Descarga", f"Resultado de la descarga:\n{err_msg}", parent=self)

    def exportar_honorarios_csv(self):
        if not self.boletas_honorarios:
            messagebox.showinfo("Exportar", "No hay boletas cargadas para exportar.", parent=self)
            return
        mes_nom = self.sel_mes.get()
        a_val = self.sel_anio.get()
        emp_nom = re.sub(r'[^a-zA-Z0-9]', '_', self.obtener_empresa_actual().get("nombre", "Empresa"))
        nombre_def = f"Boletas_Honorarios_{emp_nom}_{mes_nom}_{a_val}.csv"
        ruta = filedialog.asksaveasfilename(title="Guardar Resumen Honorarios CSV", initialfile=nombre_def, defaultextension=".csv", filetypes=[("Archivos CSV", "*.csv")])
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Folio", "Fecha Emisión", "Emisor / Prestador", "RUT Emisor", "Monto Bruto", "Retención", "Monto Líquido", "Glosa de Servicios", "PDF Guardado"])
                for b in self.boletas_honorarios:
                    w.writerow([
                        b.get("folio", ""),
                        b.get("fecha", ""),
                        b.get("emisor", ""),
                        b.get("rut", ""),
                        b.get("monto_bruto", 0),
                        b.get("retencion", 0),
                        b.get("monto_liquido", 0),
                        b.get("glosa", ""),
                        "SÍ" if b.get("pdf_ruta") else "NO"
                    ])
            self.log(f"✓ Archivo CSV de honorarios exportado: {os.path.basename(ruta)}")
            messagebox.showinfo("Exportación Exitosa", f"Archivo guardado correctamente en:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Exportar", f"No se pudo guardar el archivo CSV:\n{e}", parent=self)

    def copiar_honorarios_excel(self):
        bhes = self.boletas_honorarios_visibles if self.boletas_honorarios_visibles else self.boletas_honorarios
        if not bhes:
            messagebox.showinfo("Copiar a Excel", "No hay boletas de honorarios visibles para copiar.", parent=self)
            return
        try:
            lineas = []
            lineas.append("\t".join(["Folio", "Fecha Emisión", "Emisor / Prestador", "RUT Emisor", "Monto Bruto", "Retención", "Monto Líquido", "Glosa de Servicios", "PDF Guardado"]))
            for b in bhes:
                lineas.append("\t".join([
                    str(b.get("folio", "")),
                    str(b.get("fecha", "")),
                    str(b.get("emisor", "")),
                    str(b.get("rut", "")),
                    str(b.get("monto_bruto", 0)),
                    str(b.get("retencion", 0)),
                    str(b.get("monto_liquido", 0)),
                    str(b.get("glosa", "")),
                    "SÍ" if b.get("pdf_ruta") else "NO"
                ]))
            tsv_data = "\n".join(lineas)
            self.clipboard_clear()
            self.clipboard_append(tsv_data)
            self.update()
            self.log(f"✓ {len(bhes)} boletas de honorarios copiadas al portapapeles. ¡Pégalas en Excel con Ctrl + V!")
            messagebox.showinfo("Copiado al Portapapeles", f"Se han copiado {len(bhes)} boletas al portapapeles con éxito.\n\nPuedes pegarlas directamente en Excel con Ctrl + V.", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Copiar", f"No se pudieron copiar los datos:\n{e}", parent=self)

    # ==========================================================
    # MÓDULO 3 (FACTURACIÓN.CL - DESIS) - OPERATIVO
    # ==========================================================
    def seleccionar_carpeta_guardado_fcl(self):
        d = filedialog.askdirectory(title="Seleccionar Carpeta de Descargas Facturación.cl", initialdir=self.fcl_download_dir)
        if d:
            script_facturacion_cl.gestor_facturacion_cl.set_download_dir(d)
            self.fcl_download_dir = script_facturacion_cl.gestor_facturacion_cl.download_dir
            self.fcl_download_dir_var.set(self.fcl_download_dir)
            self.guardar_configuracion()
            self.actualizar_conteo_archivos_fcl()
            self.log(f"Carpeta Facturación.cl: {self.fcl_download_dir}")

    def abrir_carpeta_descargas_fcl(self):
        abrir_archivo_o_carpeta(self.fcl_download_dir)

    def actualizar_conteo_archivos_fcl(self):
        if os.path.exists(self.fcl_download_dir):
            c = len(glob.glob(os.path.join(self.fcl_download_dir, "*.pdf")))
            self.kpi_fcl_pdf.config(text=str(c))

    def cancelar_consulta_fcl(self):
        self.cancelar_fcl_solicitado = True
        self.log("Cancelación solicitada para Facturación.cl...")

    def abrir_dialogo_credenciales_fcl(self):
        v = tk.Toplevel(self)
        v.title("Credenciales Facturación.cl (Desis)")
        v.geometry("460x320")
        v.configure(bg=C_CANVAS)
        v.transient(self)
        v.grab_set()

        p = tk.Frame(v, bg=C_SURFACE, padx=16, pady=16)
        p.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(p, text="🔑 Credenciales de Acceso a Facturación.cl", font=("Segoe UI", 11, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 10))

        tk.Label(p, text="Código de Empresa:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_emp = tk.Entry(p, textvariable=self.fcl_empresa_var, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_emp.pack(fill="x", pady=(0, 8))

        tk.Label(p, text="Usuario:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_usr = tk.Entry(p, textvariable=self.fcl_usuario_var, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_usr.pack(fill="x", pady=(0, 8))

        tk.Label(p, text="Contraseña:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_pwd = tk.Entry(p, textvariable=self.fcl_password_var, show="•", font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_pwd.pack(fill="x", pady=(0, 14))

        def _guardar():
            self.guardar_configuracion()
            self.log(f"Credenciales de Facturación.cl guardadas para empresa {self.fcl_empresa_var.get()}.")
            v.destroy()

        btn_bar = tk.Frame(p, bg=C_SURFACE)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="Guardar Credenciales", font=("Segoe UI", 9, "bold"), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=14, pady=4, cursor="hand2", command=_guardar).pack(side="right")
        tk.Button(btn_bar, text="Cancelar", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=10, pady=4, cursor="hand2", command=v.destroy).pack(side="right", padx=(0, 6))

    def iniciar_consulta_facturacion_cl(self):
        if self.en_ejecucion:
            return
        emp = self.fcl_empresa_var.get().strip()
        usr = self.fcl_usuario_var.get().strip()
        pwd = self.fcl_password_var.get().strip()

        if not emp or not usr or not pwd:
            self.abrir_dialogo_credenciales_fcl()
            return

        self.cancelar_fcl_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        mes_nombre = self.sel_mes.get()
        mes_idx = script.NOMBRES_MESES.index(mes_nombre) if mes_nombre in script.NOMBRES_MESES else datetime.now().month
        anio_val = int(self.sel_anio.get())

        self.log(f"Consultando Facturación.cl ({emp}) para {mes_nombre} {anio_val}...")
        threading.Thread(target=self._hilo_consulta_facturacion_cl, args=(emp, usr, pwd, mes_idx, anio_val), daemon=True).start()

    def _hilo_consulta_facturacion_cl(self, emp, usr, pwd, mes_idx, anio_val):
        exito = False
        res = None
        err_msg = ""
        try:
            res = script_facturacion_cl.gestor_facturacion_cl.consultar_todo_facturacion_cl(
                mes_num=mes_idx,
                anio_num=anio_val,
                empresa=emp,
                usuario=usr,
                password=pwd,
                headless=self.modo_headless.get(),
                log_cb=self.log
            )
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_consulta_facturacion_cl_terminada(exito, res, err_msg))

    def _on_consulta_facturacion_cl_terminada(self, exito, res, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito and res:
            self.fcl_documentos = res.get("todos", [])
            self.actualizar_estados_pdf_facturacion_cl()
            self.filtrar_tabla_fcl()
            self.actualizar_kpis_fcl(res.get("totales", {}))
            self.actualizar_subtitulo_vistas()
            self.actualizar_conteo_archivos_fcl()
            self.log(f"✓ Facturación.cl completada: {len(self.fcl_documentos)} DTEs encontrados.")
        else:
            messagebox.showerror("Error Facturación.cl", f"No se pudo consultar Facturación.cl:\n{err_msg}", parent=self)
            self.log(f"Error Facturacion.cl: {err_msg}")

    def actualizar_kpis_fcl(self, totales=None):
        if not totales:
            s_neto = sum(d.get("monto_neto", 0) for d in self.fcl_documentos)
            s_iva = sum(d.get("monto_iva", 0) for d in self.fcl_documentos)
            s_tot = sum(d.get("monto_total", 0) for d in self.fcl_documentos)
            totales = {"total_documentos": len(self.fcl_documentos), "monto_neto_sum": s_neto, "monto_iva_sum": s_iva, "monto_total_sum": s_tot}

        self.kpi_fcl_tot.config(text=str(totales.get("total_documentos", len(self.fcl_documentos))))
        self.kpi_fcl_neto.config(text=f"${totales.get('monto_neto_sum', 0):,}".replace(",", "."))
        self.kpi_fcl_iva.config(text=f"${totales.get('monto_iva_sum', 0):,}".replace(",", "."))
        self.kpi_fcl_total.config(text=f"${totales.get('monto_total_sum', 0):,}".replace(",", "."))

    def buscar_archivo_pdf_fcl(self, doc):
        if not self.fcl_download_dir or not os.path.exists(self.fcl_download_dir):
            return None
        folio = str(doc.get("folio", "")).strip()
        if not folio:
            return None
        patrones = [f"*_{folio}_*", f"*_{folio},*", f"*Folio_{folio}_*", f"*Folio_{folio},*", f"*#{folio}*"]
        for p in patrones:
            for f in glob.glob(os.path.join(self.fcl_download_dir, p)):
                if f.lower().endswith(".pdf"):
                    return f
        return None

    def actualizar_estados_pdf_facturacion_cl(self):
        for d in self.fcl_documentos:
            d["pdf_ruta"] = self.buscar_archivo_pdf_fcl(d)

    def filtrar_tabla_fcl(self):
        for it in self.tree_fcl.get_children():
            self.tree_fcl.delete(it)

        q = self.fcl_busqueda_texto.get().strip().lower()
        filtro_tipo = self.fcl_tipo_doc_filtro.get()

        self.fcl_documentos_visibles = []
        for d in self.fcl_documentos:
            if filtro_tipo != "Todos":
                tipo_nom = str(d.get("tipo_doc_nombre", "")).lower()
                if filtro_tipo.lower() not in tipo_nom:
                    continue
            if q:
                match = (
                    q in str(d.get("folio", "")).lower() or
                    q in str(d.get("razon_social", "")).lower() or
                    q in str(d.get("rut_emisor", "")).lower() or
                    q in str(d.get("tipo_doc_nombre", "")).lower()
                )
                if not match:
                    continue
            self.fcl_documentos_visibles.append(d)

        for i, d in enumerate(self.fcl_documentos_visibles):
            tag_strip = "even" if i % 2 == 0 else "odd"
            tags = [tag_strip]
            tipo_cod = str(d.get("tipo_doc", "")).strip()
            if tipo_cod in ("33", "34", "61", "56"):
                tags.append(f"tipo_{tipo_cod}")
            else:
                tipo_nom = str(d.get("tipo_doc_nombre", "")).lower()
                if "exenta" in tipo_nom:
                    tags.append("tipo_34")
                elif "crédito" in tipo_nom or "credito" in tipo_nom:
                    tags.append("tipo_61")
                elif "débito" in tipo_nom or "debito" in tipo_nom:
                    tags.append("tipo_56")
                elif "factura" in tipo_nom:
                    tags.append("tipo_33")
            pdf_str = "🟢" if d.get("pdf_ruta") else "📥"
            if d.get("pdf_ruta"):
                tags.append("pdf_listo")

            valores = (
                "☐",
                d.get("folio", ""),
                d.get("tipo_doc_nombre", d.get("tipo_doc", "")),
                d.get("razon_social", ""),
                d.get("rut_emisor", ""),
                d.get("fecha_docto", ""),
                f"${d.get('monto_neto', 0):,}".replace(",", "."),
                f"${d.get('monto_iva', 0):,}".replace(",", "."),
                f"${d.get('monto_total', 0):,}".replace(",", "."),
                d.get("estado_acuse", "Recibido"),
                pdf_str
            )
            self.tree_fcl.insert("", "end", iid=str(i), values=valores, tags=tuple(tags))

        if not self.fcl_documentos_visibles:
            self.empty_state_fcl.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.empty_state_fcl.place_forget()

        self.on_seleccion_fila_fcl()

    def on_seleccion_fila_fcl(self, event=None):
        sel = self.tree_fcl.selection()
        total_sel = len(sel)
        if total_sel > 0:
            monto_sel = sum(self.fcl_documentos_visibles[int(i)].get("monto_total", 0) for i in sel if int(i) < len(self.fcl_documentos_visibles))
            self.lbl_seleccion_fcl.config(text=f"✓ {total_sel} seleccionadas • Total: ${monto_sel:,}".replace(",", "."))
            self.btn_descargar_fcl_selec.config(text=f"📥  DESCARGAR SELECCIÓN ({total_sel})")
        else:
            self.lbl_seleccion_fcl.config(text=f"0 de {len(self.fcl_documentos_visibles)} seleccionadas")
            self.btn_descargar_fcl_selec.config(text="📥  DESCARGAR SELECCIÓN")

    def seleccionar_todo_fcl(self):
        self.tree_fcl.selection_set(self.tree_fcl.get_children())
        self.on_seleccion_fila_fcl()

    def limpiar_seleccion_fcl(self):
        self.tree_fcl.selection_set([])
        self.on_seleccion_fila_fcl()

    def ordenar_por_columna_fcl(self, col, es_num=False, es_monto=False, es_fecha=False):
        asc = self.fcl_orden_columnas_asc.get(col, True)
        self.fcl_orden_columnas_asc[col] = not asc

        def _key(d):
            val = d.get(col, "")
            if es_fecha:
                return parse_fecha_dt(val)
            if es_monto or es_num:
                try:
                    return float(str(val).replace("$", "").replace(".", "").replace(",", ".").strip() or 0)
                except Exception:
                    return 0
            return str(val).lower()

        self.fcl_documentos.sort(key=_key, reverse=not asc)
        self.filtrar_tabla_fcl()

    def on_doble_clic_fila_fcl(self, event):
        item = self.tree_fcl.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        doc = self.fcl_documentos_visibles[idx]
        if doc.get("pdf_ruta") and os.path.exists(doc["pdf_ruta"]):
            VentanaVisorPDF(self, doc["pdf_ruta"], doc_info=doc)
        else:
            self.descargar_dte_individual_doc(doc)

    def mostrar_menu_contextual_fcl(self, event):
        item = self.tree_fcl.identify_row(event.y)
        if not item:
            return
        self.tree_fcl.selection_set(item)
        self.on_seleccion_fila_fcl()
        idx = int(item)
        doc = self.fcl_documentos_visibles[idx]

        m = tk.Menu(self, tearoff=0, bg=C_SURFACE, fg=C_TEXT_MAIN, activebackground=C_PRIMARY, activeforeground="#ffffff")
        if doc.get("pdf_ruta") and os.path.exists(doc["pdf_ruta"]):
            m.add_command(label="👁️  Previsualizar en Visor PDF", font=("Segoe UI", 9, "bold"), command=lambda: VentanaVisorPDF(self, doc["pdf_ruta"], doc_info=doc))
            m.add_command(label="📄  Abrir con Lector Externo", command=lambda: abrir_archivo_o_carpeta(doc["pdf_ruta"]))
            m.add_command(label="📁  Mostrar en Carpeta", command=lambda: abrir_archivo_o_carpeta(os.path.dirname(doc["pdf_ruta"])))
        else:
            m.add_command(label="📥  Descargar y Ver PDF", command=lambda: self.descargar_dte_individual_doc(doc))
        m.add_separator()
        m.add_command(label="📋  Copiar RUT Proveedor", command=lambda: self.copiar_al_portapapeles(doc.get("rut_emisor", "")))
        m.add_command(label="📋  Copiar Folio", command=lambda: self.copiar_al_portapapeles(str(doc.get("folio", ""))))
        m.add_command(label="📋  Copiar Razón Social", command=lambda: self.copiar_al_portapapeles(doc.get("razon_social", "")))
        m.tk_popup(event.x_root, event.y_root)

    def descargar_dte_individual_doc(self, doc):
        if self.en_ejecucion:
            return
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=False)

        folio = doc.get("folio", "")
        self.log(f"Descargando DTE individual Facturación.cl folio #{folio}...")
        threading.Thread(target=self._hilo_descarga_dte_individual_fcl, args=(doc,), daemon=True).start()

    def _hilo_descarga_dte_individual_fcl(self, doc):
        exito = False
        ruta = None
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            exito, ruta, corr_final = script_facturacion_cl.gestor_facturacion_cl.descargar_pdf_dte(
                doc=doc,
                download_dir=self.fcl_download_dir,
                correlativo=self.correlativo_val.get(),
                contexto_usuario=self.fcl_contexto_val.get(),
                usar_ia=self.fcl_chk_usar_ia.get(),
                gemini_api_key=self.gemini_api_key,
                openai_api_key=self.openai_api_key,
                system_prompt=self.fcl_system_prompt,
                log_cb=self.log
            )
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_dte_terminada_fcl(exito, ruta, corr_final, err_msg))

    def _on_descarga_dte_terminada_fcl(self, exito, ruta, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if exito:
            if corr_final is not None:
                self.correlativo_val.set(corr_final)
                self.guardar_configuracion()
            self.actualizar_estados_pdf_facturacion_cl()
            self.filtrar_tabla_fcl()
            self.actualizar_conteo_archivos_fcl()
            self.log(f"✓ DTE descargado exitosamente: {os.path.basename(ruta)}")
            if ruta and os.path.exists(ruta):
                abrir_archivo_o_carpeta(ruta)
        else:
            messagebox.showwarning("Aviso de Descarga", f"No se pudo descargar el DTE:\n{err_msg}", parent=self)
            self.log(f"Aviso descarga DTE: {err_msg}")

    def descargar_fcl_seleccionados_lote(self):
        sel = self.tree_fcl.selection()
        if not sel:
            messagebox.showinfo("Descarga", "Selecciona al menos un DTE para descargar.", parent=self)
            return
        docs_a_descargar = [self.fcl_documentos_visibles[int(i)] for i in sel if int(i) < len(self.fcl_documentos_visibles)]
        self.iniciar_descarga_lote_fcl(docs_a_descargar)

    def iniciar_descarga_todas_facturacion_cl_pdf(self):
        if not self.fcl_documentos:
            messagebox.showinfo("Descarga", "Primero debes consultar los DTEs de Facturación.cl.", parent=self)
            return
        self.iniciar_descarga_lote_fcl(self.fcl_documentos)

    def iniciar_descarga_lote_fcl(self, docs_lista):
        if self.en_ejecucion:
            return
        self.cancelar_fcl_solicitado = False
        self.set_estado_interfaz_ocupada(True, permitir_cancelar=True)

        self.log(f"Descargando {len(docs_lista)} DTEs desde Facturación.cl...")
        threading.Thread(target=self._hilo_descarga_todas_facturacion_cl, args=(docs_lista,), daemon=True).start()

    def _hilo_descarga_todas_facturacion_cl(self, docs_lista):
        exito = False
        total = 0
        corr_final = self.correlativo_val.get()
        err_msg = ""
        try:
            curr_corr = self.correlativo_val.get()
            for doc in docs_lista:
                if self.cancelar_fcl_solicitado:
                    break
                ok, ruta, nuevo_corr = script_facturacion_cl.gestor_facturacion_cl.descargar_pdf_dte(
                    doc=doc,
                    download_dir=self.fcl_download_dir,
                    correlativo=curr_corr,
                    contexto_usuario=self.fcl_contexto_val.get(),
                    usar_ia=self.fcl_chk_usar_ia.get(),
                    gemini_api_key=self.gemini_api_key,
                    openai_api_key=self.openai_api_key,
                    system_prompt=self.fcl_system_prompt,
                    log_cb=self.log
                )
                if ok:
                    total += 1
                    if nuevo_corr is not None:
                        curr_corr = nuevo_corr
            corr_final = curr_corr
            exito = True
        except Exception as e:
            err_msg = str(e)
        self.after(0, lambda: self._on_descarga_todas_facturacion_cl_terminada(exito, total, corr_final, err_msg))

    def _on_descarga_todas_facturacion_cl_terminada(self, exito, total, corr_final, err_msg):
        self.set_estado_interfaz_ocupada(False)

        if corr_final is not None:
            self.correlativo_val.set(corr_final)
            self.guardar_configuracion()

        self.actualizar_estados_pdf_facturacion_cl()
        self.filtrar_tabla_fcl()
        self.actualizar_conteo_archivos_fcl()

        if exito:
            self.log(f"✓ Descarga Facturación.cl finalizada: {total} DTEs guardados en {self.fcl_download_dir}")
            messagebox.showinfo("Descarga Finalizada", f"Se descargaron correctamente {total} DTEs en PDF.\n\nGuardados en:\n{self.fcl_download_dir}", parent=self)
        else:
            messagebox.showwarning("Aviso de Descarga", f"Resultado de la descarga:\n{err_msg}", parent=self)

    def exportar_fcl_seccion_csv(self, seccion="todos"):
        if not self.fcl_documentos:
            messagebox.showinfo("Exportar", "No hay DTEs cargados para exportar.", parent=self)
            return
        mes_nom = self.sel_mes.get()
        a_val = self.sel_anio.get()
        emp_nom = self.fcl_empresa_var.get()
        nombre_def = f"FacturacionCL_DTEs_{emp_nom}_{mes_nom}_{a_val}.csv"
        ruta = filedialog.asksaveasfilename(title="Guardar Resumen Facturación.cl CSV", initialfile=nombre_def, defaultextension=".csv", filetypes=[("Archivos CSV", "*.csv")])
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Folio", "Tipo Documento", "Código Tipo", "Proveedor / Razón Social", "RUT Proveedor", "Fecha Docto", "Monto Neto", "Monto IVA", "Monto Total", "Fecha Recepción SII", "Estado Acuse", "PDF Guardado"])
                for d in self.fcl_documentos:
                    w.writerow([
                        d.get("folio", ""),
                        d.get("tipo_doc_nombre", ""),
                        d.get("tipo_doc", ""),
                        d.get("razon_social", ""),
                        d.get("rut_emisor", ""),
                        d.get("fecha_docto", ""),
                        d.get("monto_neto", 0),
                        d.get("monto_iva", 0),
                        d.get("monto_total", 0),
                        d.get("fecha_recepcion", ""),
                        d.get("estado_acuse", ""),
                        "SÍ" if d.get("pdf_ruta") else "NO"
                    ])
            self.log(f"✓ Archivo CSV de Facturación.cl exportado: {os.path.basename(ruta)}")
            messagebox.showinfo("Exportación Exitosa", f"Archivo guardado correctamente en:\n{ruta}", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Exportar", f"No se pudo guardar el archivo CSV:\n{e}", parent=self)

    def copiar_fcl_excel(self):
        docs = self.fcl_documentos_visibles if self.fcl_documentos_visibles else self.fcl_documentos
        if not docs:
            messagebox.showinfo("Copiar a Excel", "No hay DTEs visibles para copiar.", parent=self)
            return
        try:
            lineas = []
            lineas.append("\t".join(["Folio", "Tipo Documento", "Código Tipo", "Proveedor / Razón Social", "RUT Proveedor", "Fecha Docto", "Monto Neto", "Monto IVA", "Monto Total", "Fecha Recepción SII", "Estado Acuse", "PDF Guardado"]))
            for d in docs:
                lineas.append("\t".join([
                    str(d.get("folio", "")),
                    str(d.get("tipo_doc_nombre", "")),
                    str(d.get("tipo_doc", "")),
                    str(d.get("razon_social", "")),
                    str(d.get("rut_emisor", "")),
                    str(d.get("fecha_docto", "")),
                    str(d.get("monto_neto", 0)),
                    str(d.get("monto_iva", 0)),
                    str(d.get("monto_total", 0)),
                    str(d.get("fecha_recepcion", "")),
                    str(d.get("estado_acuse", "")),
                    "SÍ" if d.get("pdf_ruta") else "NO"
                ]))
            tsv_data = "\n".join(lineas)
            self.clipboard_clear()
            self.clipboard_append(tsv_data)
            self.update()
            self.log(f"✓ {len(docs)} DTEs de Facturación.cl copiados al portapapeles. ¡Pégalas en Excel con Ctrl + V!")
            messagebox.showinfo("Copiado al Portapapeles", f"Se han copiado {len(docs)} DTEs al portapapeles con éxito.\n\nPuedes pegarlos directamente en Excel con Ctrl + V.", parent=self)
        except Exception as e:
            messagebox.showerror("Error al Copiar", f"No se pudieron copiar los datos:\n{e}", parent=self)

    # ==========================================================
    # MODAL DE CONFIGURACIÓN DE IA & API KEYS
    # ==========================================================
    def dialogo_configurar_ia(self):
        v = tk.Toplevel(self)
        v.title("Configuración de Inteligencia Artificial (Glosa)")
        v.geometry("540x380")
        v.configure(bg=C_CANVAS)
        v.transient(self)
        v.grab_set()

        p = tk.Frame(v, bg=C_SURFACE, padx=16, pady=16)
        p.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(p, text="🤖 Inteligencia Artificial para Glosas Comerciales", font=("Segoe UI", 11, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        tk.Label(p, text="Analiza la glosa del PDF para deducir automáticamente el contexto comercial limpio.", font=("Segoe UI", 8), bg=C_SURFACE, fg=C_TEXT_MUTED, wraplength=480, justify="left").pack(anchor="w", pady=(0, 12))

        # Google Gemini API Key
        tk.Label(p, text="Google Gemini API Key (Recomendada / Gratuita):", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_INFO).pack(anchor="w", pady=(0, 2))
        var_gemini = tk.StringVar(value=self.gemini_api_key)
        ent_gem = tk.Entry(p, textvariable=var_gemini, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_gem.pack(fill="x", pady=(0, 8))

        # OpenAI API Key
        tk.Label(p, text="OpenAI API Key (Opcional):", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_SUCCESS).pack(anchor="w", pady=(0, 2))
        var_openai = tk.StringVar(value=self.openai_api_key)
        ent_oai = tk.Entry(p, textvariable=var_openai, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_oai.pack(fill="x", pady=(0, 8))

        # Contexto manual fallback
        tk.Label(p, text="Contexto Manual Predeterminado (Fallback si no hay IA):", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MUTED).pack(anchor="w", pady=(0, 2))
        ent_ctx = tk.Entry(p, textvariable=self.contexto_val, font=("Segoe UI", 9), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat")
        ent_ctx.pack(fill="x", pady=(0, 16))

        def _guardar():
            self.gemini_api_key = var_gemini.get().strip()
            self.openai_api_key = var_openai.get().strip()
            self.guardar_configuracion()
            self.log("Configuración de IA y API Keys guardada.")
            v.destroy()

        btn_bar = tk.Frame(p, bg=C_SURFACE)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="Guardar Cambios", font=("Segoe UI", 9, "bold"), bg=C_PRIMARY, fg="#ffffff", activebackground=C_PRIMARY_HOV, relief="flat", padx=14, pady=4, cursor="hand2", command=_guardar).pack(side="right")
        tk.Button(btn_bar, text="Cancelar", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=10, pady=4, cursor="hand2", command=v.destroy).pack(side="right", padx=(0, 6))

    # ==========================================================
    # MODAL DE CONFIGURACIÓN DE CREDENCIALES DEL SII (.env)
    # ==========================================================
    def dialogo_configurar_sii_credenciales(self):
        v = tk.Toplevel(self)
        v.title("Credenciales de Acceso SII (Facturas & RCV)")
        v.geometry("520x400")
        v.configure(bg=C_CANVAS)
        v.transient(self)
        v.grab_set()

        creds = leer_credenciales_env()

        p = tk.Frame(v, bg=C_SURFACE, padx=20, pady=18, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        p.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(p, text="🔑 Credenciales de Acceso al SII", font=("Segoe UI", 12, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 4))
        tk.Label(p, text="Ingresa el RUT y la Clave Tributaria que utilizas para ingresar al portal del SII (zeus.sii.cl). Se guardarán en tu archivo .env local.", font=("Segoe UI", 8), bg=C_SURFACE, fg=C_TEXT_MUTED, wraplength=460, justify="left").pack(anchor="w", pady=(0, 14))

        # RUT Personal / Representante
        tk.Label(p, text="RUT de Acceso SII (Ej: 12345678-9):", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 2))
        var_rut = tk.StringVar(value=creds.get("SII_RUT", ""))
        ent_rut = tk.Entry(p, textvariable=var_rut, font=("Segoe UI", 10), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        ent_rut.pack(fill="x", pady=(0, 12), ipady=3)

        # Clave Tributaria
        tk.Label(p, text="Clave Tributaria SII:", font=("Segoe UI", 8, "bold"), bg=C_SURFACE, fg=C_TEXT_MAIN).pack(anchor="w", pady=(0, 2))
        row_clv = tk.Frame(p, bg=C_SURFACE)
        row_clv.pack(fill="x", pady=(0, 20))

        var_clave = tk.StringVar(value=creds.get("SII_CLAVE", ""))
        ent_clv = tk.Entry(row_clv, textvariable=var_clave, show="•", font=("Segoe UI", 10), bg=C_INPUT, fg=C_TEXT_MAIN, insertbackground=C_TEXT_MAIN, relief="flat", highlightbackground=C_BORDER, highlightthickness=1)
        ent_clv.pack(side="left", fill="x", expand=True, ipady=3)

        def _toggle_ver_clave():
            if ent_clv.cget("show") == "":
                ent_clv.configure(show="•")
                btn_ver.configure(text="👁️")
            else:
                ent_clv.configure(show="")
                btn_ver.configure(text="🙈")

        btn_ver = tk.Button(row_clv, text="👁️", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MAIN, relief="flat", padx=8, pady=2, cursor="hand2", command=_toggle_ver_clave)
        btn_ver.pack(side="right", padx=(6, 0))

        def _guardar():
            r = var_rut.get().strip()
            c = var_clave.get().strip()
            if not r or not c:
                messagebox.showerror("Error", "Debes ingresar tanto el RUT como la Clave Tributaria del SII.", parent=v)
                return
            guardar_credenciales_env(sii_rut=r, sii_clave=c)
            script.recargar_credenciales()
            self.log(f"Credenciales del SII actualizadas para RUT: {r}")
            messagebox.showinfo("Guardado", "Credenciales del SII guardadas correctamente en .env", parent=v)
            v.destroy()

        btn_bar = tk.Frame(p, bg=C_SURFACE)
        btn_bar.pack(fill="x", side="bottom")
        tk.Button(btn_bar, text="💾 Guardar Credenciales", font=("Segoe UI", 9, "bold"), bg=C_SUCCESS, fg="#ffffff", activebackground=C_SUCCESS_HOV, relief="flat", padx=14, pady=5, cursor="hand2", command=_guardar).pack(side="right")
        tk.Button(btn_bar, text="Cancelar", font=("Segoe UI", 9), bg=C_SURFACE_ALT, fg=C_TEXT_MUTED, relief="flat", padx=10, pady=5, cursor="hand2", command=v.destroy).pack(side="right", padx=(0, 6))

    # ==========================================================
    # GESTIÓN DE SESIONES & CIERRE LIMPIO
    # ==========================================================
    def actualizar_badge_sesion(self, conectado=True):
        if conectado:
            self.lbl_sesion_badge.config(text="● SII Conectado", fg=C_SUCCESS)
        else:
            self.lbl_sesion_badge.config(text="○ SII Inactivo", fg=C_TEXT_MUTED)

    def _cerrar_todas_sesiones_sincrono(self, log_cb=print):
        """Cierra en paralelo todas las sesiones activas en el SII y Facturación.cl."""
        def _c_rcv():
            try:
                script.gestor_sesion.cerrar_sesion(log_cb=log_cb)
            except Exception:
                pass

        def _c_bhe():
            try:
                script_honorarios.gestor_honorarios.cerrar_sesion(log_cb=log_cb)
            except Exception:
                pass

        def _c_fcl():
            try:
                script_facturacion_cl.gestor_facturacion_cl.cerrar_sesion(log_cb=log_cb)
            except Exception:
                pass

        threads = [
            threading.Thread(target=_c_rcv, daemon=True),
            threading.Thread(target=_c_bhe, daemon=True),
            threading.Thread(target=_c_fcl, daemon=True)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.5)

    def desconectar_todas_sesiones(self):
        if messagebox.askyesno("Desconectar Sesiones", "¿Deseas cerrar limpiamente todas las sesiones persistentes en los servidores del SII y Facturación.cl?", parent=self):
            self.log("Cerrando todas las conexiones...")
            threading.Thread(target=self._hilo_desconectar, daemon=True).start()

    def _hilo_desconectar(self):
        self._cerrar_todas_sesiones_sincrono(log_cb=self.log)
        self.after(0, lambda: self.actualizar_badge_sesion(False))
        self.log("✓ Todas las sesiones han sido desconectadas del SII.")

    def ejecutar_cierre_definitivo(self):
        """Guarda configuración, libera sesiones en SII y cierra la app."""
        try:
            if hasattr(self, "btn_salir") and self.btn_salir.winfo_exists():
                self.btn_salir.config(text="⏳ Cerrando sesión SII...", state="disabled")
            if hasattr(self, "lbl_sesion_badge") and self.lbl_sesion_badge.winfo_exists():
                self.lbl_sesion_badge.config(text="○ Desconectando...", fg=C_WARNING)
            self.update_idletasks()
        except Exception:
            pass

        self.guardar_configuracion()
        self._cerrar_todas_sesiones_sincrono(log_cb=print)
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def confirmar_y_salir(self):
        """Pregunta confirmación antes de salir y libera las sesiones activas en el SII."""
        if self.en_ejecucion:
            if not messagebox.askyesno(
                "Operación en Curso",
                "Hay una consulta o descarga en ejecución.\n\n¿Deseas cancelarla y salir del programa de todos modos?",
                icon="warning",
                parent=self
            ):
                return
            self.cancelar_consulta_actual()

        if messagebox.askyesno(
            "Salir del Gestor",
            "¿Deseas salir del Gestor Tributario?\n\nSe cerrarán y liberarán limpiamente las sesiones abiertas en el SII y Facturación.cl.",
            parent=self
        ):
            self.ejecutar_cierre_definitivo()

    def al_cerrar_app(self):
        """Manejador del botón cerrar [X] de la ventana."""
        if self.en_ejecucion:
            if not messagebox.askyesno(
                "Operación en Curso",
                "Hay una consulta o descarga en curso.\n\n¿Deseas cancelarla y salir del programa?",
                icon="warning",
                parent=self
            ):
                return
            self.cancelar_consulta_actual()

        self.ejecutar_cierre_definitivo()


if __name__ == "__main__":
    app = AppSII()
    app.mainloop()

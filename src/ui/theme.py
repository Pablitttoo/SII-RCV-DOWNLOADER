"""
Paleta de colores, tipografías y configuración de estilos ttk (Deep Slate / Obsidian Pro).
Basado exactamente en el diseño de referencia UI (diseño_nuevo_app.png).
"""

from tkinter import ttk

# ==========================================================
# PALETA DE COLORES MODERNA (Obsidian Deep / Sidebar)
# ==========================================================
C_CANVAS       = "#0a0e1a"  # Fondo base principal
C_SIDEBAR      = "#0c1322"  # Fondo de la barra lateral
C_SIDEBAR_CARD = "#121b2d"  # Fondo de bloques y tarjetas en sidebar
C_SURFACE      = "#121b2d"  # Fondo de tarjetas y paneles principales
C_SURFACE_ALT  = "#19243b"  # Fondo secundario para cabeceras, botones oscuros y hover
C_INPUT        = "#080d18"  # Fondo de campos de texto, combos y buscador
C_BORDER       = "#1c2842"  # Bordes sutiles y limpios
C_BORDER_FOCUS = "#6366f1"  # Borde al enfocar / acento índigo

C_TEXT_MAIN    = "#f8fafc"  # Texto principal blanco nítido
C_TEXT_MUTED   = "#94a3b8"  # Texto secundario / etiquetas
C_TEXT_DIM     = "#64748b"  # Texto atenuado / hints

C_PRIMARY      = "#6366f1"  # Indigo primario (Descargar Selección / Acentos)
C_PRIMARY_HOV  = "#818cf8"  # Indigo hover
C_SUCCESS      = "#10b981"  # Verde esmeralda (Consultar / Descargar Todos)
C_SUCCESS_HOV  = "#34d399"  # Verde hover
C_WARNING      = "#f59e0b"  # Ámbar (Pendientes / Retenciones)
C_DANGER       = "#f43f5e"  # Coral / Rojo (IVA / Desconexión)
C_INFO         = "#38bdf8"  # Azul cielo brillante (Total DTEs)
C_PURPLE       = "#a855f7"  # Púrpura brillante (Monto Total)
C_TEAL         = "#2dd4bf"  # Verde azulado / Cian (PDFs Guardados)

# Fondos circulares para insignias KPI
C_BADGE_BLUE   = "#0c2844"
C_BADGE_GREEN  = "#093325"
C_BADGE_RED    = "#3b121f"
C_BADGE_PURPLE = "#2a154a"
C_BADGE_TEAL   = "#093230"


def aplicar_estilos_ttk(root):
    """Aplica la paleta de colores y estilos a todos los widgets ttk de la aplicación."""
    style = ttk.Style(root)
    style.theme_use("clam")

    root.option_add("*selectBackground", C_PRIMARY)
    root.option_add("*selectForeground", "#ffffff")
    root.option_add("*insertBackground", C_TEXT_MAIN)
    root.option_add("*TCombobox*Listbox.background", C_SURFACE)
    root.option_add("*TCombobox*Listbox.foreground", C_TEXT_MAIN)
    root.option_add("*TCombobox*Listbox.selectBackground", C_PRIMARY)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

    root.bind_class("TCombobox", "<FocusIn>", lambda e: e.widget.selection_clear())

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
        padding=5
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
        rowheight=32,
        font=("Segoe UI", 9)
    )
    style.configure(
        "Treeview.Heading",
        background=C_SURFACE_ALT,
        foreground=C_TEXT_MAIN,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        padding=[6, 8]
    )
    style.map(
        "Treeview",
        background=[("selected", "#242a4a")],
        foreground=[("selected", "#ffffff")]
    )
    style.map("Treeview.Heading", background=[("active", "#223150")])
    style.configure("Custom.Horizontal.TProgressbar", troughcolor=C_INPUT, background=C_PRIMARY, bordercolor=C_BORDER)

# 💼 SII-RCV-DOWNLOADER: Gestor Tributario Unificado

Aplicación de escritorio en Python / Tkinter para la consulta, gestión y descarga masiva automatizada de:
1. **Facturas y Registro de Compras y Ventas (RCV / MIPE)** - Servicio de Impuestos Internos (SII).
2. **Boletas de Honorarios Electrónicas (BHE)** - SII.
3. **Panel DTE y Facturas** - Facturación.cl (Desis).

---

## 🚀 Ejecución

### Modo directo
```bash
python main.py
```
*(O también `python app.py` gracias a los shims de compatibilidad).*

---

## 📂 Estructura Modular del Proyecto (`src/` Layout)

```text
SII-RCV-DOWNLOADER/
│
├── .github/workflows/          # Automatización CI/CD con GitHub Actions
│   └── build_exe.yml           # Compilación automática a .exe en la nube
│
├── assets/                     # Recursos gráficos e iconos de la app
│   ├── app_icon.ico
│   └── app_icon.png
│
├── src/                        # Código fuente modular
│   ├── ui/                     # Interfaz Gráfica (Deep Slate / Obsidian)
│   │   ├── theme.py            # Paleta de colores y estilos ttk
│   │   └── app_window.py       # Controlador y ventana principal AppSII
│   │
│   ├── core/                   # Motores de automatización y scraping
│   │   ├── rcv_engine.py       # Motor SII RCV / MIPE y sesión persistente
│   │   ├── bhe_engine.py       # Motor Boletas de Honorarios Electrónicas
│   │   └── desis_engine.py     # Motor Facturación.cl (Desis)
│   │
│   ├── ai/                     # Inteligencia Artificial y Glosas
│   │   └── glosa_extractor.py  # Extracción con Gemini API, OpenAI y local
│   │
│   └── utils/                  # Utilidades y configuración
│       ├── config.py           # Gestión de config_app.json y empresas.json
│       └── helpers.py          # Manejo de rutas, fechas y apertura de archivos
│
├── main.py                     # Punto de entrada principal
├── requirements.txt            # Dependencias del proyecto
├── SII_GestorFacturas.spec     # Especificación de empaquetado PyInstaller
├── empresas.json               # Base de datos local multi-empresa
└── config_app.json             # Preferencias de usuario
```

---

## 📦 Compilación a `.EXE` (Windows Autónomo)

### Opción A: Compilación Automática en GitHub (Recomendada)
Cada vez que haces `git push`, GitHub Actions compila automáticamente el ejecutable en una máquina virtual de Windows.
- Ve a la pestaña **Actions** en tu repositorio de GitHub.
- Descarga el artefacto **`SII_GestorFacturas-Windows`**.

### Opción B: Compilación Local
```bash
pip install -r requirements.txt
pyinstaller SII_GestorFacturas.spec --noconfirm --clean
```
El ejecutable resultante quedará en la carpeta `dist/SII_GestorFacturas.exe`.

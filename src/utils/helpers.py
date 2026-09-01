"""
Funciones auxiliares para apertura de archivos, parseo de fechas, manejo de rutas y carga de .env.
"""

import os
import sys
import subprocess
from datetime import datetime


def obtener_ruta_base():
    """Retorna la ruta raíz de la aplicación (compatible con PyInstaller y ejecución directa)."""
    if getattr(sys, 'frozen', False):
        return os.path.abspath(os.path.dirname(sys.executable))

    # Subir niveles buscando marcadores del proyecto (main.py, requirements.txt, .env)
    dir_actual = os.path.abspath(os.path.dirname(__file__))
    for _ in range(4):
        if (os.path.exists(os.path.join(dir_actual, "main.py")) or
            os.path.exists(os.path.join(dir_actual, "requirements.txt")) or
            os.path.exists(os.path.join(dir_actual, ".env")) or
            os.path.exists(os.path.join(dir_actual, "config_app.json"))):
            return dir_actual
        padre = os.path.dirname(dir_actual)
        if padre == dir_actual:
            break
        dir_actual = padre

    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def obtener_ruta_appdata(nombre_app="GestorSII"):
    """
    Retorna la ruta segura de almacenamiento de datos del usuario en AppData / Application Support / .local/share.
    Crea el directorio si no existe.
    """
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")

    ruta_app = os.path.join(base, nombre_app)
    try:
        os.makedirs(ruta_app, exist_ok=True)
    except Exception:
        pass
    return ruta_app


def cargar_variables_entorno():
    """Busca y carga el archivo .env desde AppData (con migración transparente si existía en la raíz)."""
    try:
        from dotenv import load_dotenv
        import shutil
        appdata_dir = obtener_ruta_appdata()
        env_appdata = os.path.join(appdata_dir, ".env")

        # 1. Si existe en AppData, cargar prioritariamente
        if os.path.exists(env_appdata):
            load_dotenv(env_appdata, override=True)
            return True

        # 2. Si no existe en AppData pero existe en la raíz, migrar a AppData y cargar
        base = obtener_ruta_base()
        env_local = os.path.join(base, ".env")
        if os.path.exists(env_local):
            try:
                shutil.copy2(env_local, env_appdata)
            except Exception:
                pass
            load_dotenv(env_appdata if os.path.exists(env_appdata) else env_local, override=True)
            return True
    except Exception:
        pass
    return False


def obtener_ruta_recurso(nombre_recurso):
    """
    Busca un recurso estático (como un icono o imagen) en _MEIPASS, assets/ o en la raíz.
    """
    base_res = getattr(sys, '_MEIPASS', obtener_ruta_base())

    # 1. En carpeta assets
    ruta_assets = os.path.join(base_res, "assets", nombre_recurso)
    if os.path.exists(ruta_assets):
        return ruta_assets

    # 2. En la raíz de recursos
    ruta_raiz = os.path.join(base_res, nombre_recurso)
    if os.path.exists(ruta_raiz):
        return ruta_raiz

    # 3. Fallback en disco
    ruta_disco = os.path.join(obtener_ruta_base(), "assets", nombre_recurso)
    if os.path.exists(ruta_disco):
        return ruta_disco

    return os.path.join(obtener_ruta_base(), nombre_recurso)


def abrir_archivo_o_carpeta(ruta):
    """Abre un archivo o directorio de forma segura en Windows, Linux o macOS."""
    if not ruta or not os.path.exists(ruta):
        return
    try:
        if sys.platform == "win32":
            os.startfile(ruta)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", ruta])
        else:
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

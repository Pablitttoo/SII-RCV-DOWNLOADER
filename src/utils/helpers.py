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


def cargar_variables_entorno():
    """Busca y carga el archivo .env desde la raíz del proyecto."""
    try:
        from dotenv import load_dotenv
        base = obtener_ruta_base()
        ruta_env = os.path.join(base, ".env")
        if os.path.exists(ruta_env):
            load_dotenv(ruta_env, override=True)
            return True
        if os.path.exists(".env"):
            load_dotenv(".env", override=True)
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

"""
Gestión de persistencia y archivos de configuración (config_app.json), empresas (empresas.json) y .env
almacenados de forma segura y aislada en AppData del usuario.
"""

import os
import json
import shutil
from .helpers import obtener_ruta_base, obtener_ruta_appdata, cargar_variables_entorno

CONFIG_FILE = os.path.join(obtener_ruta_appdata(), "config_app.json")
EMPRESAS_FILE = os.path.join(obtener_ruta_appdata(), "empresas.json")

# Lista inicial de muestra para nuevos usuarios (sin datos reales)
LISTA_EMPRESAS_DEFECTO = [
    {"nombre": "MI EMPRESA SPA (EJEMPLO)", "rut": "76.111.111-1", "clave_sii": ""}
]


def leer_credenciales_env():
    """Retorna un diccionario con las credenciales y variables actuales desde AppData."""
    cargar_variables_entorno()
    return {
        "SII_RUT": os.getenv("SII_RUT", "").strip(),
        "SII_CLAVE": os.getenv("SII_CLAVE", "").strip(),
        "RUT_EMPRESA": os.getenv("RUT_EMPRESA", "").strip(),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "").strip(),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
    }


def guardar_credenciales_env(sii_rut=None, sii_clave=None, rut_empresa=None, gemini_key=None, openai_key=None):
    """Guarda o actualiza de forma segura las variables en el archivo .env de AppData."""
    ruta_env = os.path.join(obtener_ruta_appdata(), ".env")

    lineas_existentes = {}
    if os.path.exists(ruta_env):
        try:
            with open(ruta_env, "r", encoding="utf-8") as f:
                for linea in f:
                    linea_strip = linea.strip()
                    if linea_strip and not linea_strip.startswith("#") and "=" in linea_strip:
                        k, v = linea_strip.split("=", 1)
                        lineas_existentes[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    if sii_rut is not None:
        lineas_existentes["SII_RUT"] = str(sii_rut).strip()
    if sii_clave is not None:
        lineas_existentes["SII_CLAVE"] = str(sii_clave).strip()
    if rut_empresa is not None:
        lineas_existentes["RUT_EMPRESA"] = str(rut_empresa).strip()
    if gemini_key is not None:
        lineas_existentes["GEMINI_API_KEY"] = str(gemini_key).strip()
    if openai_key is not None:
        lineas_existentes["OPENAI_API_KEY"] = str(openai_key).strip()

    try:
        with open(ruta_env, "w", encoding="utf-8") as f:
            f.write("# Credenciales Oficiales SII & API Keys (AppData Seguro)\n")
            for k, v in lineas_existentes.items():
                f.write(f'{k}="{v}"\n')
                os.environ[k] = v
        return True
    except Exception:
        return False


def cargar_configuracion(ruta_archivo=None):
    """Carga el diccionario de configuración de la app (con migración transparente desde la raíz local)."""
    ruta = ruta_archivo or CONFIG_FILE
    
    # Si no existe en AppData pero existe en la raíz del proyecto, migrar automáticamente
    if ruta_archivo is None and not os.path.exists(CONFIG_FILE):
        ruta_local = os.path.join(obtener_ruta_base(), "config_app.json")
        if os.path.exists(ruta_local):
            try:
                shutil.copy2(ruta_local, CONFIG_FILE)
            except Exception:
                pass

    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    return {
        "correlativo": 2000,
        "contexto": "",
        "usar_ia": True,
        "gemini_api_key": "",
        "openai_api_key": "",
        "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "empresa_rut": "",
        "rut_empresa_hn": "",
        "sii_clave_hn": "",
        "download_dir_hn": os.path.join(os.path.expanduser("~"), "Downloads"),
        "hn_usar_ia": True,
        "hn_contexto": "",
        "facturacion_empresa": "",
        "facturacion_usuario": "",
        "facturacion_password": "",
        "download_dir_fcl": os.path.join(os.path.expanduser("~"), "Downloads"),
        "fcl_usar_ia": True,
        "fcl_contexto": "",
        "fcl_system_prompt": ""
    }


def guardar_configuracion(config_dict, ruta_archivo=None):
    """Guarda el diccionario de configuración en AppData."""
    ruta = ruta_archivo or CONFIG_FILE
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def cargar_empresas(ruta_archivo=None):
    """Carga la lista de empresas registradas (con migración transparente desde la raíz local)."""
    ruta = ruta_archivo or EMPRESAS_FILE
    
    # Si no existe en AppData pero existe en la raíz del proyecto, migrar automáticamente
    if ruta_archivo is None and not os.path.exists(EMPRESAS_FILE):
        ruta_local = os.path.join(obtener_ruta_base(), "empresas.json")
        if os.path.exists(ruta_local):
            try:
                shutil.copy2(ruta_local, EMPRESAS_FILE)
            except Exception:
                pass

    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
            
    guardar_empresas(LISTA_EMPRESAS_DEFECTO, ruta)
    return [dict(e) for e in LISTA_EMPRESAS_DEFECTO]


def guardar_empresas(lista_empresas, ruta_archivo=None):
    """Guarda la lista de empresas en disco en AppData."""
    ruta = ruta_archivo or EMPRESAS_FILE
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(lista_empresas, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

"""
Gestión de persistencia y archivos de configuración (config_app.json), empresas (empresas.json) y .env.
"""

import os
import json
from .helpers import obtener_ruta_base, cargar_variables_entorno

CONFIG_FILE = os.path.join(obtener_ruta_base(), "config_app.json")
EMPRESAS_FILE = os.path.join(obtener_ruta_base(), "empresas.json")

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


def leer_credenciales_env():
    """Retorna un diccionario con las credenciales y variables actuales de .env."""
    cargar_variables_entorno()
    return {
        "SII_RUT": os.getenv("SII_RUT", "").strip(),
        "SII_CLAVE": os.getenv("SII_CLAVE", "").strip(),
        "RUT_EMPRESA": os.getenv("RUT_EMPRESA", "").strip(),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", "").strip(),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "").strip(),
    }


def guardar_credenciales_env(sii_rut=None, sii_clave=None, rut_empresa=None, gemini_key=None, openai_key=None):
    """Guarda o actualiza de forma segura las variables en el archivo .env de la raíz."""
    base = obtener_ruta_base()
    ruta_env = os.path.join(base, ".env")

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
            f.write("# Credenciales Oficiales SII & API Keys\n")
            for k, v in lineas_existentes.items():
                f.write(f'{k}="{v}"\n')
                os.environ[k] = v
        return True
    except Exception:
        return False


def cargar_configuracion(ruta_archivo=None):
    """Carga el diccionario de configuración de la app."""
    ruta = ruta_archivo or CONFIG_FILE
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
    """Guarda el diccionario de configuración en disco."""
    ruta = ruta_archivo or CONFIG_FILE
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False


def cargar_empresas(ruta_archivo=None):
    """Carga la lista de empresas registradas."""
    ruta = ruta_archivo or EMPRESAS_FILE
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
    """Guarda la lista de empresas en disco."""
    ruta = ruta_archivo or EMPRESAS_FILE
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(lista_empresas, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

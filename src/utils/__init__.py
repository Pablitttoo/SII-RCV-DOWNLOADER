"""
Módulo de utilidades, configuración y auto-actualizador del Gestor SII.
"""

from .helpers import (
    abrir_archivo_o_carpeta,
    parse_fecha_dt,
    obtener_ruta_base,
    obtener_ruta_appdata,
    obtener_ruta_recurso,
    cargar_variables_entorno,
)
from .config import (
    CONFIG_FILE,
    EMPRESAS_FILE,
    LISTA_EMPRESAS_DEFECTO,
    cargar_configuracion,
    guardar_configuracion,
    cargar_empresas,
    guardar_empresas,
    leer_credenciales_env,
    guardar_credenciales_env,
)
from .updater import (
    verificar_actualizaciones_inicio,
    verificar_actualizaciones_manual,
    consultar_version_github,
    aplicar_actualizacion_windows,
    VERSION_LOCAL,
)

__all__ = [
    "abrir_archivo_o_carpeta",
    "parse_fecha_dt",
    "obtener_ruta_base",
    "obtener_ruta_appdata",
    "obtener_ruta_recurso",
    "cargar_variables_entorno",
    "CONFIG_FILE",
    "EMPRESAS_FILE",
    "LISTA_EMPRESAS_DEFECTO",
    "cargar_configuracion",
    "guardar_configuracion",
    "cargar_empresas",
    "guardar_empresas",
    "leer_credenciales_env",
    "guardar_credenciales_env",
    "verificar_actualizaciones_inicio",
    "verificar_actualizaciones_manual",
    "consultar_version_github",
    "aplicar_actualizacion_windows",
    "VERSION_LOCAL",
]

"""
Módulo de Inteligencia Artificial para extracción y refinamiento de glosas en Facturas, Honorarios y DTEs.
"""

from .glosa_extractor import (
    PROMPT_SISTEMA_GLOSA,
    PROMPT_SISTEMA_FACTURACION_CL,
    formatear_glosa_natural,
    extraer_texto_pdf,
    limpiar_metadatos_basura,
    es_glosa_invalida_o_nula,
    deducir_contexto_por_proveedor,
    extraer_glosa_heuristica,
    limpiar_glosa_sin_emisor,
    construir_payload_texto,
    consultar_gemini_api,
    consultar_openai_api,
    obtener_contexto_factura,
)

PROMPT_SISTEMA_HONORARIOS = PROMPT_SISTEMA_GLOSA

__all__ = [
    "PROMPT_SISTEMA_GLOSA",
    "PROMPT_SISTEMA_FACTURACION_CL",
    "PROMPT_SISTEMA_HONORARIOS",
    "formatear_glosa_natural",
    "extraer_texto_pdf",
    "limpiar_metadatos_basura",
    "es_glosa_invalida_o_nula",
    "deducir_contexto_por_proveedor",
    "extraer_glosa_heuristica",
    "limpiar_glosa_sin_emisor",
    "construir_payload_texto",
    "consultar_gemini_api",
    "consultar_openai_api",
    "obtener_contexto_factura",
]

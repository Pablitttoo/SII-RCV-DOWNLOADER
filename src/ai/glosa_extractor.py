"""
Módulo de Inteligencia Artificial para extracción y resumen de contexto específico de facturas (DTE).
Extrae el texto de la glosa/detalle del PDF descargado y utiliza Gemini API / OpenAI API
(o un extractor heurístico local de respaldo) para generar un contexto ESPECÍFICO y descriptivo
(ej: 'Arriendo de oficina Agosto 2026', 'Auspicio La Junta Betsson', 'Envíos comerciales TV Agosto').
"""

import os
import sys
import re
import requests
from dotenv import load_dotenv

from ..utils import obtener_ruta_base, cargar_variables_entorno

DIRECTORIO_ACTUAL = obtener_ruta_base()
cargar_variables_entorno()

# Intentar importar pypdf
try:
    from pypdf import PdfReader
    PYPDF_DISPONIBLE = True
except ImportError:
    PYPDF_DISPONIBLE = False

MESES_SET = {
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
}


def formatear_glosa_natural(texto):
    """
    Formatea el texto a formato legible natural con mayúscula inicial, nombres de meses capitalizados
    y siglas comunes en mayúsculas, evitando textos completamente en mayúsculas.
    Ejemplos:
      'AUSPICIO LAJUNTA BETSSON AGOSTO' -> 'Auspicio Lajunta Betsson Agosto'
      'ARRIENDO OFICINA AGOSTO 2026'    -> 'Arriendo Oficina Agosto 2026'
    """
    if not texto:
        return ""

    limpio = re.sub(r'[\\/*?:"<>|\n\r]+', ' ', str(texto)).strip()
    palabras = limpio.split()
    if not palabras:
        return ""

    siglas = {
        "HD", "TV", "PC", "IT", "TI", "DTE", "SII", "GPS", "WEB", "IA", "AI",
        "LED", "SPA", "SA", "EIRL", "LTDA", "USB", "POS", "SEO", "SEM", "PDF",
        "ERP", "CRM", "API", "SSL", "VPN", "SIM", "GSM", "VOIP", "I", "II", "III", "IV", "V",
        "MP", "BHE", "UI", "UX", "QA", "RRHH", "RRSS", "CM", "AV", "HQ", "B2B", "B2C", "SWIFT"
    }
    conectores = {"de", "del", "en", "a", "la", "el", "los", "las", "y", "o", "por", "con", "para", "un", "una", "al"}

    resultado = []
    for idx, p in enumerate(palabras):
        p_clean = p.strip()
        p_lower = p_clean.lower()
        p_upper = p_clean.upper()

        if p_upper in siglas:
            resultado.append(p_upper)
        elif p_clean.isupper() and 2 <= len(p_clean) <= 4 and p_lower not in conectores and p_lower not in {"mes", "ano", "año", "dia", "día", "sol", "sur", "red", "gas", "luz"}:
            resultado.append(p_upper)
        elif p_lower in MESES_SET:
            resultado.append(p_lower.capitalize())
        elif idx == 0:
            resultado.append(p_lower.capitalize())
        elif p_lower in conectores:
            resultado.append(p_lower)
        else:
            if p_clean.isdigit():
                resultado.append(p_clean)
            else:
                resultado.append(p_lower.capitalize())

    frase = " ".join(resultado)
    if frase:
        frase = frase[0].upper() + frase[1:]
    return frase


def extraer_texto_pdf(ruta_pdf):
    """Extrae el contenido textual de un archivo PDF."""
    if not PYPDF_DISPONIBLE or not os.path.exists(ruta_pdf):
        return ""
    try:
        reader = PdfReader(ruta_pdf)
        texto = "\n".join([page.extract_text() or "" for page in reader.pages])
        return texto.strip()
    except Exception:
        return ""


def limpiar_metadatos_basura(texto_crudo):
    """Elimina etiquetas de formulario y códigos técnicos basura (ej: CH1688@, PEPB, NULL, etc.)."""
    if not texto_crudo:
        return ""
    t = re.sub(r'[\w\d]+@[\w\s_]+:', ' ', texto_crudo)
    t = re.sub(r'@[\w\s_]+:', ' ', t)
    t = re.sub(r'\b[A-Za-z]{1,4}\d{2,8}@?\b', ' ', t)
    t = re.sub(r'\b(pepb|null|none|undefined|nil|nan|facturacion\s+null|pepb\s+facturacion)\b', ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'\b(nombre\s+de\s+la\s+campa[nñ]a|detalle\s+del\s+trabajo|tipo\s+de\s+trabajo|cuenta\s+pro|copias\s+canal)\b[:\s]*', ' ', t, flags=re.IGNORECASE)
    return t


def es_glosa_invalida_o_nula(glosa):
    """Verifica si la glosa es nula, vacía o contiene texto de error de ERP (como PEPB o NULL)."""
    if not glosa:
        return True
    g_clean = glosa.lower().strip()
    if len(g_clean) < 3:
        return True
    patrones_invalidos = [
        r'\bnull\b', r'\bnone\b', r'\bundefined\b', r'\bpepb\b', r'\bnil\b',
        r'\bfacturacion\s+null\b', r'\bpepb\s+facturacion\b', r'\bsin\s+descripci[oó]n\b', r'\bno\s+informa(do)?\b',
        r'^(facturacion|servicio|servicios|venta|ventas|compra|compras|detalle|item|glosa|total|n/a)$'
    ]
    for p in patrones_invalidos:
        if re.search(p, g_clean):
            return True
    palabras = [p for p in g_clean.split() if p not in {'total', 'facturacion', 'servicio', 'servicios', 'venta', 'compra', 'detalle', 'item', 'glosa', 'valor', 'monto'}]
    if not palabras:
        return True
    return False


DICCIONARIO_PROVEEDORES_COMUNES = [
    (r"jetsmart|latam|sky\s+airline|copa\s+airline|iberia|avianca|aerolinea|airline", "Venta Pasaje Aereo Vuelo"),
    (r"uber|cabify|didi|beat", "Servicio Transporte Traslado"),
    (r"enel|cge|chilquinta|saesa|colbun", "Servicio Suministro Electrico"),
    (r"aguas\s+andinas|essbio|esval|aguas\s+del\s+valle|aguas\s+nuevas", "Servicio Agua Potable"),
    (r"copec|shell|petrobras|enex", "Compra Combustible"),
    (r"google|microsoft|amazon\s+web|aws|digitalocean|adobe|zoom|slack|openai|github", "Servicios Cloud y Software"),
    (r"entel|movistar|claro|wom|vtr|gtd|mundo\s+pacifico", "Servicio Telecomunicaciones"),
    (r"hotel|hostal|resort|lodge|apart\s+hotel", "Servicio Alojamiento Hotel"),
    (r"restaurant|restaurante|gastronomia|comidas|cafe|bistro", "Consumo Restaurant Gastronomia"),
    (r"manager\s+software|manager\s+erp|erp\s+manager|manager\+", "Mantencion Manager Usuario"),
    (r"sodimac|easy|homecenter|imperial|construmart", "Compra Materiales Insumos"),
    (r"lider|jumbo|tottus|santa\s+isabel|unimarc", "Compra Insumos Supermercado"),
]


def deducir_contexto_por_proveedor(razon_social, giro=""):
    """Deducción inteligente del servicio según la empresa emisora."""
    rz_l = (razon_social or "").lower()
    giro_l = (giro or "").lower()
    for patron, concepto in DICCIONARIO_PROVEEDORES_COMUNES:
        if re.search(patron, rz_l) or re.search(patron, giro_l):
            palabras_rz = razon_social.split()
            nombre_corto = palabras_rz[0].capitalize() if palabras_rz else ""
            if "jetsmart" in rz_l:
                nombre_corto = "JetSMART"
            elif "latam" in rz_l:
                nombre_corto = "LATAM"
            elif "uber" in rz_l:
                nombre_corto = "Uber"
            elif "copec" in rz_l:
                nombre_corto = "Copec"
            elif "enel" in rz_l:
                nombre_corto = "Enel"
            elif "manager" in rz_l:
                return formatear_glosa_natural(f"{concepto}")
            return formatear_glosa_natural(f"{concepto} {nombre_corto}")
    return ""


def extraer_glosa_heuristica(texto, doc_info=None):
    """
    Extracción local sin IA basada en el patrón estándar de facturas y boletas de honorarios chilenas.
    Busca 'Por atención profesional' (BHE), 'Descripción' o 'Detalle', filtra basura técnica y captura conceptos.
    Si la glosa es nula, vacía o inválida (ej: 'PEPB FACTURACION NULL'), deduce por la Razón Social / Proveedor.
    """
    texto_limpio = limpiar_metadatos_basura(texto) if texto else ""
    texto_raw_l = (texto or "").lower()
    rz_emisor_l = ((doc_info.get("razon_social") or doc_info.get("emisor") or "") if doc_info else "").lower()

    # 0. Detección específica para Banco de Chile (4 tipos de facturas)
    if "banco de chile" in rz_emisor_l or "banco chile" in rz_emisor_l or "banco de chile" in texto_raw_l or "bancochile" in texto_raw_l or any(k in texto_raw_l for k in ["mensaje swift", "envio garantizado", "orden de pago", "cuenta corriente pyme", "plan cuenta corriente"]):
        if "mensaje swift" in texto_raw_l or ("swift" in texto_raw_l and "cambios" in texto_raw_l):
            return "Comisión operaciones de cambio - Mensaje Swift"
        if "envio garantizado" in texto_raw_l or "transferencias envio garantizado" in texto_raw_l or "transferencias envio" in texto_raw_l:
            return "Comisión operaciones de cambio"
        if "orden de pago" in texto_raw_l or "ordenes de pago" in texto_raw_l:
            return "Comisión ordenes de pago"
        if "cuenta corriente pyme" in texto_raw_l or "plan cuenta corriente" in texto_raw_l or "comision mensaul plan" in texto_raw_l or "comision mensual plan" in texto_raw_l:
            return "Comisión Mantención Cuenta Corriente"
    
    # 1. Detección especializada para Boletas de Honorarios Electrónicas (BHE)
    if texto_limpio:
        m_bhe = re.search(r'(?:por\s+atenci[oó]n\s+profesional|atenci[oó]n\s+profesional|por\s+servicios\s+profesionales|servicios\s+prestados)\s*[:.-]*\s*([^\n\r]+(?:\n[^\n\r]+)?)', texto_limpio, re.IGNORECASE)
        if m_bhe:
            raw_bhe = m_bhe.group(1).strip()
            # Limpiar posibles delimitadores de corte
            raw_bhe = re.split(r'\b(total\s+honorarios|retenci[oó]n|l[ií]quido|fecha\s+de\s+emisi|se[nñ]or\(es\)|rut|domicilio)\b', raw_bhe, flags=re.IGNORECASE)[0].strip()
            # Quitar prefijos comunes
            raw_bhe = re.sub(r'^(por\s+|servicios\s+de\s+|honorarios\s+por\s+)', '', raw_bhe, flags=re.IGNORECASE).strip()
            if raw_bhe and not es_glosa_invalida_o_nula(raw_bhe):
                palabras = raw_bhe.split()
                res = " ".join(palabras[:18])
                return formatear_glosa_natural(res)

    lineas = texto_limpio.split("\n") if texto_limpio else []
    en_detalle = False
    items = []
    palabras_cabecera = {
        "codigo", "descripci", "descripcion", "cantidad", "precio", "valor", 
        "impto", "adic", "desc", "dcto", "item", "unid", "unit", "total", "neto"
    }

    for l in lineas:
        l_str = l.strip()
        if not en_detalle:
            if any(w in l_str.lower() for w in ["descripci", "detalle", "item", "glosa", "atenci"]):
                en_detalle = True
                l_str_limpia = re.sub(r'^(item\s*\d*[:.-]*|descripci[oó]n[:.-]*|detalle[:.-]*|glosa[:.-]*|por\s+atenci[oó]n\s+profesional[:.-]*)\s*', '', l_str, flags=re.IGNORECASE).strip()
                if not l_str_limpia:
                    continue
                l_str = l_str_limpia

        if en_detalle:
            if any(w in l_str.lower() for w in ["referencias:", "monto neto", "timbre", "total", "iva 19%", "sub total", "fecha de emisi", "monto total", "total honorarios", "retención"]):
                break
            if l_str and not l_str.isdigit():
                palabras_linea = l_str.split()
                limpias = []
                for p in palabras_linea:
                    p_clean = re.sub(r'[@\-_/|#.*%]+', '', p).strip()
                    if not p_clean or p_clean.lower() in palabras_cabecera:
                        continue
                    if p_clean.replace(".", "").replace(",", "").replace("$", "").isdigit():
                        if len(p_clean) == 4 and p_clean.startswith("20"):
                            limpias.append(p_clean)
                        continue
                    if len(p_clean) > 1:
                        limpias.append(p_clean)

                if limpias:
                    items.append(" ".join(limpias))

    if items:
        frase = " ".join(items)
        if not es_glosa_invalida_o_nula(frase):
            palabras = frase.split()
            res = " ".join(palabras[:65])
            return formatear_glosa_natural(res)

    # Si la descripción es nula, vacía o inválida, deducir por la empresa
    if doc_info:
        rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
        giro_doc = doc_info.get("giro", "")
        deducido = deducir_contexto_por_proveedor(rz, giro_doc)
        if deducido:
            return deducido

    # Si no encontró detalle, usar el Giro si está disponible en el texto
    if texto:
        m_giro = re.search(r'Giro\s*:\s*([^\n\r]+)', texto, re.IGNORECASE)
        if m_giro:
            giro = m_giro.group(1).strip()
            deducido_giro = deducir_contexto_por_proveedor("", giro)
            if deducido_giro:
                return deducido_giro
            palabras = [p for p in giro.split() if len(p) > 2 and p.lower() not in {"servicios", "venta", "giro"}]
            giro_str = " ".join(palabras[:8])
            if giro_str and not es_glosa_invalida_o_nula(giro_str):
                return formatear_glosa_natural(giro_str)

    if doc_info:
        rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
        if rz:
            return formatear_glosa_natural(rz[:35])

    return ""


def limpiar_glosa_sin_emisor(glosa, doc_info=None):
    """
    Elimina del texto de la glosa el nombre del emisor/profesional si fue incluido por la IA o por el extractor,
    para evitar duplicidades al armar el nombre final del archivo (ej: 'Filmación Contenido MP - Alejandro Maldonado' -> 'Filmación Contenido MP').
    """
    if not glosa:
        return ""
    g = str(glosa).strip()
    if not doc_info:
        return formatear_glosa_natural(g)

    emisor = str(doc_info.get("razon_social") or doc_info.get("nombre_emisor") or doc_info.get("emisor") or "").strip()
    if not emisor:
        return formatear_glosa_natural(g)

    # 1. Si contiene el nombre completo del emisor precedido de guion, "por", "de", "profesional", "a"
    patron_por = re.compile(r'\b(?:por|de|para|profesional|atenci[oó]n|a\s+favor\s+de)\s+' + re.escape(emisor) + r'\b', re.IGNORECASE)
    g = patron_por.sub('', g).strip()

    # 2. Si la glosa termina con " - Emisor" o " - Nombre Profesional" o ", Emisor" o " Emisor"
    patron_sufijo = re.compile(r'[\s,\-]+' + re.escape(emisor) + r'[\s.]*$', re.IGNORECASE)
    g = patron_sufijo.sub('', g).strip()

    # 3. Quitar el nombre si está exacto y la glosa tiene contenido adicional
    if len(emisor) >= 5 and emisor.lower() in g.lower():
        g_rem = re.sub(re.escape(emisor), '', g, flags=re.IGNORECASE).strip()
        if len(g_rem) >= 3:
            g = g_rem

    # 4. Limpiar conectores o preposiciones colgantes al final
    g = re.sub(r'\b(?:por|de|del|para|con|a|en|profesional|atenci[oó]n|correspondiente\s+a)\s*$', '', g, flags=re.IGNORECASE).strip()

    # 5. Limpiar caracteres de puntuación sobrantes al inicio o al final
    g = re.sub(r'^[\s,:\-_.]+|[\s,:\-_.]+$', '', g).strip()
    return formatear_glosa_natural(g)


PROMPT_SISTEMA_GLOSA = (
    "Eres un asistente contable experto en tributación y documentación electrónica chilena (Facturas DTE y Boletas de Honorarios BHE del SII).\n"
    "Tu objetivo es extraer o deducir un resumen simple, limpio, descriptivo y profesional del servicio o producto prestado/adquirido, con un MÁXIMO DE 10 A 15 PALABRAS (frase concisa y directa).\n\n"
    "REGLAS CRÍTICAS OBLIGATORIAS:\n"
    "1. REGLAS PARA BOLETAS DE HONORARIOS ELECTRÓNICAS (BHE):\n"
    "   - En las Boletas de Honorarios, la glosa se encuentra principalmente en 'Por atención profesional:' o 'Servicios prestados:'.\n"
    "   - Extrae el concepto esencial, limpio y directo del trabajo (ejemplos: 'Filmación Contenido MP', 'Asesoría Tributaria Julio', 'Diseño Gráfico Campaña', 'Desarrollo Web Frontend', 'Edición Audiovisual Spot').\n"
    "   - NUNCA incluyas frases de relleno como 'Por atención profesional', 'Servicios profesionales de', 'Honorarios correspondientes a'.\n"
    "   - **PROHIBIDO INCLUIR EL NOMBRE DEL PROFESIONAL O EMISOR EN LA GLOSA**: NUNCA incluyas el nombre del profesional, emisor ni receptor en la glosa (por ejemplo, si el emisor es 'Alejandro Maldonado', NO pongas 'Filmación Contenido MP - Alejandro Maldonado' ni 'Filmación Contenido MP Alejandro Maldonado'). El sistema agrega automáticamente el nombre del emisor al final del archivo. La glosa debe contener ÚNICAMENTE la descripción del servicio (ejemplo: 'Filmación Contenido MP').\n"
    "   - Si la descripción menciona un proyecto, cliente, mes o campaña específica, inclúyelo de forma breve (ej: 'Filmación Contenido MP').\n\n"
    "2. REGLAS ESPECÍFICAS PARA BANCO DE CHILE:\n"
    "   Si el proveedor es 'BANCO DE CHILE' o el documento es una factura del Banco de Chile, aplica estrictamente las siguientes equivalencias según el tipo de glosa/detalle:\n"
    "   • Glosa: 'Comision servicio de transferencias envio garantizado numero de operacion' (o relacionada a transferencias envío garantizado / número de operación)\n"
    "     -> Genera exactamente: 'Comisión operaciones de cambio'\n"
    "   • Glosa: 'Comision mensaje swift operaciones de cambios internacionales' (o relacionada a mensaje SWIFT / operaciones de cambios internacionales)\n"
    "     -> Genera exactamente: 'Comisión operaciones de cambio - Mensaje Swift'\n"
    "   • Glosa: 'comision por orden de pago emitida y/o recibida' (o relacionada a orden de pago emitida y/o recibida)\n"
    "     -> Genera exactamente: 'Comisión ordenes de pago'\n"
    "   • Glosa: 'comision mensaul plan cuenta corriente pyme' / 'comision mensual plan cuenta corriente pyme' (o relacionada a mantención o plan cuenta corriente pyme)\n"
    "     -> Genera exactamente: 'Comisión Mantención Cuenta Corriente'\n\n"
    "3. PROHIBICIÓN ESTRICTA DE PALABRAS DE ERROR O BASURA ('NULL', 'PEPB', 'FACTURACION NULL'):\n"
    "   - NUNCA generes las palabras 'Null', 'PEPB', 'Facturación Null', 'Sin descripción' ni códigos de error.\n"
    "   - Descarta códigos internos y prefijos de sistema (ejemplos: 'CH1688@', 'CH188@', '@NOMBRE DE LA CAMPAÑA:', '@DETALLE DEL TRABAJO:', 'PRO@', 'ITEM 1:', 'COD. 1234', 'OC 542', 'HES', etc.).\n\n"
    "4. REGLAS ESPECÍFICAS POR OTROS PROVEEDORES / SOFTWARE:\n"
    "   - Si el Proveedor es 'MANAGER SOFTWARE S.A.' o el texto menciona 'MANAGER' / 'LICENCIAS ERP':\n"
    "     * Genera exactamente: 'Mantención Manager Usuario [Mes] [Año]' o 'Mantención Manager Usuario Periodo [Mes] [Año]' (según el periodo facturado o fecha del documento).\n"
    "   - Si el Proveedor es 'ENEL' o 'CGE' -> 'Servicio Suministro Electrico'\n"
    "   - Si el Proveedor es 'AGUAS ANDINAS' o 'ESSBIO' -> 'Servicio Agua Potable'\n"
    "   - Si el Proveedor es 'COPEC' o 'SHELL' -> 'Compra Combustible Copec'\n"
    "   - Si el Proveedor es 'JETSMART' o 'LATAM' o 'SKY' -> 'Venta de Pasaje Aereo Vuelo JetSMART'\n"
    "   - Si el Proveedor es 'UBER' o 'CABIFY' -> 'Servicio Transporte de Pasajeros'\n"
    "   - Si el Proveedor es 'GOOGLE' o 'MICROSOFT' o 'AWS' -> 'Servicios Cloud y Software'\n\n"
    "5. DEDUCCIÓN INTELIGENTE SI LA GLOSA ES NULA O VACÍA:\n"
    "   - Si el texto no tiene una descripción clara, es nula o vacía, analiza el Emisor, su profesión/giro y el Monto para DEDUCIR lógicamente qué se contrató de manera precisa.\n\n"
    "6. REGLA DEL MES / PERIODO:\n"
    "   - Prioriza el mes o periodo mencionado DENTRO DE LA DESCRIPCIÓN (ej: 'copias canal Julio', 'arriendo oficina mes de Julio', 'servicios de Junio').\n\n"
    "7. FORMATO Y ESTILO:\n"
    "   - Usa formato natural legible (primera letra en mayúscula, marcas y nombres capitalizados, siglas como TV, HD, MP, GPS, TI, ERP, SWIFT en mayúsculas, NUNCA todo el texto en mayúsculas sostenidas).\n"
    "   - Debe ser una frase fluida, concisa y comprensible para humanos.\n"
    "   - Devuelve ÚNICAMENTE el texto resumen limpio, sin comillas, viñetas, puntos finales ni explicaciones adicionales.\n\n"
    "EJEMPLOS DE ENTRADA Y SALIDA ESPERADA:\n"
    "• Factura: 'COMISION SERVICIO DE TRANSFERENCIAS ENVIO GARANTIZADO NUMERO DE OPERACION 987654', Proveedor: 'BANCO DE CHILE'\n"
    "  -> 'Comisión operaciones de cambio'\n\n"
    "• Factura: 'COMISION MENSAJE SWIFT OPERACIONES DE CAMBIOS INTERNACIONALES', Proveedor: 'BANCO DE CHILE'\n"
    "  -> 'Comisión operaciones de cambio - Mensaje Swift'\n\n"
    "• Factura: 'COMISION POR ORDEN DE PAGO EMITIDA Y/O RECIBIDA', Proveedor: 'BANCO DE CHILE'\n"
    "  -> 'Comisión ordenes de pago'\n\n"
    "• Factura: 'COMISION MENSUAL PLAN CUENTA CORRIENTE PYME', Proveedor: 'BANCO DE CHILE'\n"
    "  -> 'Comisión Mantención Cuenta Corriente'\n\n"
    "• Boleta de Honorarios: 'POR ATENCIÓN PROFESIONAL: FILMACIÓN Y EDICIÓN DE CONTENIDO AUDIOVISUAL MP MES DE JULIO', Emisor: 'ALEJANDRO MALDONADO'\n"
    "  -> 'Filmación Contenido MP'\n\n"
    "• Boleta de Honorarios: 'POR ATENCIÓN PROFESIONAL: ASESORÍA LEGAL Y TRIBUTARIA EN REVISIÓN DE CONTRATOS JULIO 2026', Emisor: 'MARÍA GONZÁLEZ'\n"
    "  -> 'Asesoría Legal y Tributaria Julio'\n\n"
    "• Factura: 'MANTENCION MANAGER USUARIO LICENCIAS SISTEMA ERP MANAGER AGOSTO 2026', Proveedor: 'MANAGER SOFTWARE S.A.'\n"
    "  -> 'Mantención Manager Usuario Agosto 2026'\n\n"
    "• Factura con texto: 'PEPB FACTURACION NULL', Proveedor: 'JETSMART AIRLINES SPA'\n"
    "  -> 'Venta de Pasaje Aereo Vuelo JetSMART'\n\n"
    "• Factura: 'HD - ENVIOS DE COMERCIALES A CANALES DE TV CH1688@NOMBRE DE LA CAMPANA: CUENTA PRO@DETALLE DEL TRABAJO: COPIAS CANAL JULIO'\n"
    "  -> 'Envios Comerciales a Canales TV Julio'\n"
)

# System Prompt base para Facturacion.cl (puede ser personalizado por el usuario)
PROMPT_SISTEMA_FACTURACION_CL = PROMPT_SISTEMA_GLOSA


def construir_payload_texto(texto_pdf, doc_info=None):
    """Construye el contenido para la IA combinando metadatos del documento y texto extraído."""
    partes = []
    if doc_info:
        rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
        rut = doc_info.get("rut_emisor") or ""
        monto = doc_info.get("monto_total") or ""
        tipo = doc_info.get("tipo_doc_nombre") or doc_info.get("tipo_doc") or ""
        if rz:
            partes.append(f"Proveedor / Emisor: {rz}")
        if rut:
            partes.append(f"RUT Proveedor: {rut}")
        if monto:
            partes.append(f"Monto Total: ${monto}")
        if tipo:
            partes.append(f"Tipo Documento: {tipo}")

    texto_limpio = limpiar_metadatos_basura(texto_pdf) if texto_pdf else ""
    if texto_limpio and texto_limpio.strip() and not es_glosa_invalida_o_nula(texto_limpio):
        partes.append(f"Contenido del PDF:\n{texto_limpio[:2800]}")
    else:
        partes.append("Contenido del PDF: [La glosa viene vacía/nula o con error interno de ERP]")

    return "\n".join(partes)


def consultar_gemini_api(texto_factura, doc_info=None, api_key=None, prompt_sistema=None):
    """Consulta la API de Google Gemini (Gemini 3.5 Flash Lite / 3.5 Flash / 3.6 Flash / Flash Latest) para extraer o deducir un contexto específico."""
    if not api_key:
        return None

    sys_prompt = prompt_sistema if (prompt_sistema and prompt_sistema.strip()) else PROMPT_SISTEMA_GLOSA
    cuerpo = construir_payload_texto(texto_factura, doc_info=doc_info)

    modelos = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]
    for mod in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": sys_prompt}]
            },
            "contents": [{
                "parts": [{"text": f"Datos de la factura a resumir/deducir:\n---\n{cuerpo}\n---"}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 300,
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                candidatos = data.get("candidates", [])
                if candidatos:
                    partes = candidatos[0].get("content", {}).get("parts", [])
                    if partes:
                        respuesta = partes[0].get("text", "").strip()
                        respuesta_limpia = re.sub(r'[\\/*?:"<>|\n\r]+', ' ', respuesta).strip()
                        if es_glosa_invalida_o_nula(respuesta_limpia) and doc_info:
                            rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
                            ded = deducir_contexto_por_proveedor(rz, doc_info.get("giro", ""))
                            if ded:
                                return ded
                        palabras = respuesta_limpia.split()
                        texto_completo = " ".join(palabras[:65])
                        return formatear_glosa_natural(texto_completo)
        except Exception:
            continue

    if doc_info:
        rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
        return deducir_contexto_por_proveedor(rz, doc_info.get("giro", ""))

    return None


def consultar_openai_api(texto_factura, doc_info=None, api_key=None, prompt_sistema=None):
    """Consulta la API de OpenAI (gpt-4o-mini / gpt-3.5-turbo) para extraer o deducir un contexto específico."""
    if not api_key:
        return None

    sys_prompt = prompt_sistema if (prompt_sistema and prompt_sistema.strip()) else PROMPT_SISTEMA_GLOSA
    cuerpo = construir_payload_texto(texto_factura, doc_info=doc_info)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": sys_prompt
            },
            {
                "role": "user",
                "content": f"Datos de la factura:\n---\n{cuerpo}\n---"
            }
        ],
        "temperature": 0.1,
        "max_tokens": 250
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            elecciones = data.get("choices", [])
            if elecciones:
                txt = elecciones[0].get("message", {}).get("content", "").strip()
                txt_limpio = re.sub(r'[\\/*?:"<>|\n\r]+', ' ', txt).strip()
                if es_glosa_invalida_o_nula(txt_limpio) and doc_info:
                    rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
                    ded = deducir_contexto_por_proveedor(rz, doc_info.get("giro", ""))
                    if ded:
                        return ded
                texto_completo = " ".join(txt_limpio.split()[:65])
                return formatear_glosa_natural(texto_completo)
    except Exception:
        pass

    if doc_info:
        rz = doc_info.get("razon_social") or doc_info.get("emisor") or ""
        return deducir_contexto_por_proveedor(rz, doc_info.get("giro", ""))

    return None


def obtener_contexto_factura(ruta_pdf, doc_info=None, api_key_gemini=None, api_key_openai=None, prompt_sistema=None, log_cb=print):
    """
    Función principal: Extrae el texto del PDF y obtiene o deduce el contexto específico vía IA o fallback heurístico.
    Soporta prompt_sistema personalizado si se desea alterar el comportamiento del modelo.
    """
    texto = extraer_texto_pdf(ruta_pdf) if os.path.exists(ruta_pdf) else ""

    # 1. Intentar con Gemini
    key_gemini = api_key_gemini or os.getenv("GEMINI_API_KEY")
    if key_gemini:
        log_cb("   -> [IA] Consultando/deduciendo contexto específico a Gemini API...")
        res = consultar_gemini_api(texto, doc_info=doc_info, api_key=key_gemini, prompt_sistema=prompt_sistema)
        if res:
            res_limpio = limpiar_glosa_sin_emisor(res, doc_info=doc_info)
            log_cb(f"   -> [IA Gemini] Contexto generado: '{res_limpio}'")
            return res_limpio

    # 2. Intentar con OpenAI
    key_openai = api_key_openai or os.getenv("OPENAI_API_KEY")
    if key_openai:
        log_cb("   -> [IA] Consultando/deduciendo contexto específico a OpenAI API...")
        res = consultar_openai_api(texto, doc_info=doc_info, api_key=key_openai, prompt_sistema=prompt_sistema)
        if res:
            res_limpio = limpiar_glosa_sin_emisor(res, doc_info=doc_info)
            log_cb(f"   -> [IA OpenAI] Contexto generado: '{res_limpio}'")
            return res_limpio

    # 3. Fallback Heurístico local (Sin API key / Offline)
    log_cb("   -> [Glosa] Extrayendo/deduciendo descripción local de la factura...")
    res_local = extraer_glosa_heuristica(texto, doc_info=doc_info)
    if res_local:
        res_limpio = limpiar_glosa_sin_emisor(res_local, doc_info=doc_info)
        log_cb(f"   -> [Glosa Local] Contexto detectado: '{res_limpio}'")
        return res_limpio

    return ""

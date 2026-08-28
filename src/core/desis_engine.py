"""
Módulo para interacción y descarga automatizada de documentos tributarios electrónicos (DTE)
desde la plataforma Facturacion.cl (Desis).
Permite consultar documentos recibidos (Panel DTE), filtrar por periodo y descargar PDFs oficiales.
"""

import os
import sys
import re
import csv
import time
import base64
import calendar
import threading
import requests
from datetime import datetime
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    NoAlertPresentException,
)
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

from ..utils import obtener_ruta_base, cargar_variables_entorno

DIRECTORIO_ACTUAL = obtener_ruta_base()
cargar_variables_entorno()

URL_HOME_FACTURACION = "https://www.facturacion.cl/"
URL_AUTH_ENDPOINT    = "https://www.facturacion.cl/desis/accesoFE3.php"

# Nombres de meses en español
NOMBRES_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

TIPOS_DTE_NOMBRES = {
    "33": "Factura Electrónica",
    "34": "Factura Exenta",
    "43": "Liquidación Factura",
    "46": "Factura de Compra",
    "52": "Guía de Despacho",
    "56": "Nota de Débito",
    "61": "Nota de Crédito",
    "110": "Factura de Exportación",
    "111": "Nota de Débito Exportación",
    "112": "Nota de Crédito Exportación",
}

TIPO_TEXTO_A_CODIGO = {
    "FACTURA ELECTRONICA": "33",
    "FACTURA NO AFECTA O EXENTA ELECTRONICA": "34",
    "FACTURA EXENTA ELECTRONICA": "34",
    "LIQUIDACION FACTURA ELECTRONICA": "43",
    "FACTURA DE COMPRA ELECTRONICA": "46",
    "GUIA DE DESPACHO ELECTRONICA": "52",
    "NOTA DE DEBITO ELECTRONICA": "56",
    "NOTA DE CREDITO ELECTRONICA": "61",
    "FACTURA DE EXPORTACION ELECTRONICA": "110",
    "NOTA DE DEBITO DE EXPORTACION ELECTRONICA": "111",
    "NOTA DE CREDITO DE EXPORTACION ELECTRONICA": "112",
    "BOLETA ELECTRONICA": "39",
    "BOLETA NO AFECTA O EXENTA ELECTRONICA": "41",
}


def sanitizar_nombre_archivo(texto):
    """Limpia caracteres inválidos para nombres de archivo en Windows/Linux."""
    if not texto:
        return ""
    limpio = re.sub(r'[\\/*?:"<>|]', '', str(texto))
    limpio = ' '.join(limpio.split())
    return limpio.strip()


def extraer_numero_mes(doc_info, mes_seleccionado=None):
    """Extrae el número de mes a 2 dígitos (01 a 12)."""
    fecha = str(doc_info.get("fecha_docto", "")).strip()
    if fecha:
        m = re.search(r'[-/](\d{1,2})[-/]', fecha)
        if m:
            return f"{int(m.group(1)):02d}"
        m2 = re.search(r'^\d{4}-(\d{1,2})-\d{1,2}', fecha)
        if m2:
            return f"{int(m2.group(1)):02d}"
    if mes_seleccionado:
        if isinstance(mes_seleccionado, int):
            return f"{mes_seleccionado:02d}"
        if str(mes_seleccionado).isdigit():
            return f"{int(mes_seleccionado):02d}"
        if mes_seleccionado in NOMBRES_MESES:
            idx = NOMBRES_MESES.index(mes_seleccionado)
            return f"{idx:02d}"
    return datetime.now().strftime("%m")


def generar_nombre_archivo_facturacion_cl(doc_info, correlativo=None, glosa="", mes_num=None):
    """
    Genera el nombre de archivo según el formato requerido para Facturacion.cl:
    numeroCorrelación_numeroMes_Factura#NumFolio, glosa dependiendo contexto - NOMBRE EMPRESA(MAYUSCULA).pdf
    
    Ejemplo con IA / Glosa:
      2316_08_Factura#15718, Arriendo Oficina Agosto 2026 - ENTEL PCS TELECOMUNICACIONES S.A..pdf
    Ejemplo sin glosa:
      2316_08_Factura#15718 - ENTEL PCS TELECOMUNICACIONES S.A..pdf
    """
    folio = str(doc_info.get("folio", "")).strip()
    razon_social = str(doc_info.get("razon_social", doc_info.get("emisor", ""))).strip().upper()
    empresa_limpia = sanitizar_nombre_archivo(razon_social).upper()
    if not empresa_limpia:
        empresa_limpia = str(doc_info.get("rut_emisor", "PROVEEDOR")).strip().upper()

    num_mes = extraer_numero_mes(doc_info, mes_seleccionado=mes_num)

    tipo_cod = str(doc_info.get("tipo_doc", "")).strip()
    tipo_nom = str(doc_info.get("tipo_doc_nombre", "")).lower()

    if tipo_cod == "61" or "crédito" in tipo_nom:
        tipo_prefix = "NotaCredito"
    elif tipo_cod == "56" or "débito" in tipo_nom:
        tipo_prefix = "NotaDebito"
    elif tipo_cod == "34" or "exenta" in tipo_nom:
        tipo_prefix = "FacturaExenta"
    elif tipo_cod == "52" or "guía" in tipo_nom:
        tipo_prefix = "Guia"
    else:
        tipo_prefix = "Factura"

    doc_id = f"{tipo_prefix}#{folio}" if folio else tipo_prefix

    partes_prefijo = []
    if correlativo is not None and str(correlativo).strip():
        partes_prefijo.append(str(correlativo).strip())
    partes_prefijo.append(str(num_mes))
    partes_prefijo.append(doc_id)

    prefijo = "_".join(partes_prefijo)

    glosa_limpia = sanitizar_nombre_archivo(str(glosa).strip()) if glosa else ""

    if glosa_limpia:
        nombre = f"{prefijo}, {glosa_limpia} - {empresa_limpia}.pdf"
    else:
        nombre = f"{prefijo} - {empresa_limpia}.pdf"

    return sanitizar_nombre_archivo(nombre)


def parse_monto_int(val):
    """Convierte strings de dinero (ej: '$ 110.547') a entero."""
    if not val:
        return 0
    try:
        limpio = str(val).replace("$", "").replace(".", "").replace(",", "").strip()
        if limpio.startswith("-"):
            return -int(limpio[1:]) if limpio[1:].isdigit() else 0
        return int(limpio) if limpio.isdigit() else 0
    except Exception:
        return 0



class GestorFacturacionCL:
    """Administrador de sesión y descargas para Facturacion.cl."""

    def __init__(self):
        self.driver = None
        self.session = None
        self.empresa_activa = ""
        self.usuario_activo = ""
        self.password_activa = ""
        self.subdominio_web = ""
        self.autenticado = False
        self.download_dir = os.path.join(DIRECTORIO_ACTUAL, "facturas_descargadas")
        self.lock = threading.RLock()

    def set_download_dir(self, ruta):
        if ruta:
            try:
                ruta_abs = os.path.abspath(ruta)
                os.makedirs(ruta_abs, exist_ok=True)
                self.download_dir = ruta_abs
            except (FileNotFoundError, OSError, Exception):
                self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                try:
                    os.makedirs(self.download_dir, exist_ok=True)
                except Exception:
                    pass

    def _crear_driver(self, headless=True):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        try:
            os.makedirs(self.download_dir, exist_ok=True)
        except (FileNotFoundError, OSError, Exception):
            self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            try:
                os.makedirs(self.download_dir, exist_ok=True)
            except Exception:
                pass
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        # Inicializar driver con Selenium Manager nativo (resuelve versión exacta de Chromium/Chrome)
        try:
            driver = webdriver.Chrome(options=options)
        except Exception:
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception:
                driver = webdriver.Chrome(options=options)

        try:
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": self.download_dir}
            )
        except Exception:
            pass

        stealth(
            driver,
            languages=["es-CL", "es"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        return driver

    def iniciar_sesion(self, empresa, usuario, password, headless=True, log_cb=print):
        """Autentica contra facturacion.cl y obtiene la sesión web."""
        with self.lock:
            empresa_clean = empresa.strip().upper()
            usuario_clean = usuario.strip().upper()
            password_clean = password.strip()

            if (self.autenticado and self.driver and
                self.empresa_activa == empresa_clean and
                self.usuario_activo == usuario_clean):
                log_cb(f"Reutilizando sesión activa en Facturacion.cl para {empresa_clean}")
                return True

            self.cerrar_sesion(log_cb=lambda m: None)

            log_cb(f"Iniciando sesión en Facturacion.cl (Empresa: {empresa_clean}, Usuario: {usuario_clean})...")
            self.driver = self._crear_driver(headless=headless)
            wait = WebDriverWait(self.driver, 25)

            try:
                log_cb("Abriendo portal de acceso https://www.facturacion.cl/...")
                self.driver.get(URL_HOME_FACTURACION)
                time.sleep(2.5)

                # Llenar formulario de acceso
                emp_inp = wait.until(EC.presence_of_element_located((By.ID, "empresa")))
                emp_inp.clear()
                emp_inp.send_keys(empresa_clean)

                usr_inp = self.driver.find_element(By.ID, "user")
                usr_inp.clear()
                usr_inp.send_keys(usuario_clean)

                pwd_inp = self.driver.find_element(By.ID, "pass")
                pwd_inp.clear()
                pwd_inp.send_keys(password_clean)

                log_cb("Enviando credenciales de acceso al servidor...")
                self.driver.execute_script("""
                    var trig = document.getElementById('trigger');
                    if (trig) {
                        trig.click();
                    } else if (typeof xLog !== 'undefined' && typeof xLog.Send === 'function') {
                        xLog.Send();
                    } else {
                        var form = document.getElementById('login');
                        if (form) form.submit();
                    }
                """)

                # Esperar redirección al portal de la empresa o captura de alertas
                tiempo_inicio = time.time()
                redireccionado = False
                while time.time() - tiempo_inicio < 20:
                    time.sleep(0.6)

                    # 1. Comprobar alertas emergentes JS
                    try:
                        al = self.driver.switch_to.alert
                        al_text = al.text
                        al.accept()
                        if al_text:
                            al_lower = al_text.lower()
                            if any(w in al_lower for w in ["incorrect", "no existe", "invalido", "inválido", "bloquead"]):
                                raise Exception(f"Facturacion.cl informa: '{al_text}'")
                            log_cb(f"Alerta Facturacion.cl: '{al_text}'")
                    except (NoAlertPresentException, NoSuchElementException):
                        pass

                    # 2. Comprobar modales o mensajes de error en HTML
                    try:
                        page_src = self.driver.page_source.lower()
                        if "password incorrecta" in page_src or "clave incorrecta" in page_src:
                            raise Exception("Usuario y/o Contraseña incorrecta en Facturacion.cl.")
                        elif "no existe en nuestro sistema" in page_src:
                            raise Exception(f"La empresa '{empresa_clean}' no existe en Facturacion.cl.")
                    except Exception as err_mod:
                        if "no existe" in str(err_mod) or "incorrecta" in str(err_mod):
                            raise err_mod

                    # 3. Comprobar si hubo redirección exitosa
                    try:
                        curr = self.driver.current_url.lower()
                        if (empresa_clean.lower() in curr or "index.php" in curr or "sistema" in curr or "form" in curr):
                            if curr.rstrip('/') != URL_HOME_FACTURACION.rstrip('/') and "acceso" not in curr:
                                redireccionado = True
                                break
                    except Exception:
                        pass

                if not redireccionado:
                    raise Exception("Tiempo de espera agotado al iniciar sesión en Facturacion.cl. Verifica las credenciales.")

                time.sleep(2.5)
                curr_url = self.driver.current_url
                clean_base = re.sub(r'/(index\.php|sistema.*|form/.*)?(\?.*)?$', '', curr_url).rstrip('/')
                if clean_base and clean_base != "https://www.facturacion.cl":
                    self.subdominio_web = clean_base
                else:
                    self.subdominio_web = f"https://www.facturacion.cl/{empresa_clean.lower()}"

                self.empresa_activa = empresa_clean
                self.usuario_activo = usuario_clean
                self.password_activa = password_clean
                self.autenticado = True

                # Sincronizar sesión requests
                self.session = requests.Session()
                for c in self.driver.get_cookies():
                    self.session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))

                log_cb(f"✓ Sesión en Facturacion.cl iniciada con éxito ({self.subdominio_web})")
                return True

            except Exception as e:
                log_cb(f"ERROR en login de Facturacion.cl: {e}")
                self.cerrar_sesion(log_cb=lambda m: None)
                raise e

    def consultar_libro_compras(self, mes_num=None, anio_num=None,
                                 empresa="", usuario="", password="", headless=True, log_cb=print):
        """
        Consulta las facturas ingresadas / contabilizadas en el Libro de Compras de Facturacion.cl.
        """
        if not self.autenticado or not self.driver:
            self.iniciar_sesion(empresa=empresa, usuario=usuario, password=password, headless=headless, log_cb=log_cb)

        mes_num = mes_num or datetime.now().month
        anio_num = anio_num or datetime.now().year

        mes_str = f"{mes_num:02d}"
        anio_str = str(anio_num)

        url_libro = f"{self.subdominio_web}/form/contabilidad/libros2/?indice=2"
        log_cb(f"Navegando a Libro de Compras (Contabilidad) ({mes_str}/{anio_str})...")

        self.driver.get(url_libro)
        time.sleep(2.5)

        # Seleccionar año, mes y pedir hasta 500 registros
        log_cb(f"Consultando Libro de Compras para el periodo {mes_str}-{anio_str}...")
        self.driver.execute_script(f"""
            if (document.getElementById('anno')) document.getElementById('anno').value = '{anio_str}';
            if (document.getElementById('mes')) document.getElementById('mes').value = '{mes_str}';
            if (document.getElementById('GRID_NumReg')) document.getElementById('GRID_NumReg').value = '500';
            if (document.formulario && typeof document.formulario.submit === 'function') {{
                document.formulario.submit();
            }}
        """)
        time.sleep(2.5)

        html = self.driver.page_source

        tr_matches = re.findall(r'<tr[^>]*class=["\']tr_lista_fila[^"\']*["\'][^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
        log_cb(f"Procesando {len(tr_matches)} filas del Libro de Compras...")

        documentos_libro = []
        for tr in tr_matches:
            # 1. Folio
            folio_m = re.search(r'name=["\']FOLIO["\'][^>]*>.*?value=["\'](\d+)["\']', tr, re.DOTALL | re.IGNORECASE)
            folio = folio_m.group(1) if folio_m else ""
            if not folio:
                folio_m2 = re.search(r'name=["\']FOLIO["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
                folio = re.sub(r'<[^>]+>', '', folio_m2.group(1)).strip() if folio_m2 else ""

            if not folio or not folio.isdigit():
                continue

            # 2. Documento (Tipo)
            tipo_m = re.search(r'name=["\']DOCUMENTO["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            tipo_texto = re.sub(r'<[^>]+>', '', tipo_m.group(1)).strip().upper() if tipo_m else ""
            tipo_codigo = TIPO_TEXTO_A_CODIGO.get(tipo_texto, "33")
            tipo_nombre = TIPOS_DTE_NOMBRES.get(tipo_codigo, tipo_texto or "Factura Electrónica")

            # 3. Fecha Documento
            fecha_m = re.search(r'name=["\']FECHA["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            fecha_texto = re.sub(r'<[^>]+>', '', fecha_m.group(1)).strip() if fecha_m else ""

            # 4. Recepción SII
            recep_m = re.search(r'name=["\']RECEPCIONSII["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            recep_texto = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', recep_m.group(1))).strip() if recep_m else ""

            # 5. Razón Social y RUT Emisor
            rz_m = re.search(r'name=["\']RAZONSOCIAL["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            rz_content = rz_m.group(1) if rz_m else ""
            rut_m = re.search(r'seenopago\(["\']([0-9kK\.\-]+)["\']\)', rz_content)
            rut_emisor = rut_m.group(1) if rut_m else ""
            razon_social = re.sub(r'<[^>]+>', '', rz_content).strip()

            # 6. Monto Total
            total_m = re.search(r'name=["\']TOTAL["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            total_str = re.sub(r'<[^>]+>', '', total_m.group(1)).strip() if total_m else "$ 0"
            m_total = parse_monto_int(total_str)

            # Estimación de neto e IVA si es Factura Electrónica Afecta
            if tipo_codigo == "33" and m_total > 0:
                m_neto = int(round(m_total / 1.19))
                m_iva  = m_total - m_neto
            else:
                m_neto = m_total
                m_iva  = 0

            # 7. URL de Vista Previa / PDF
            pdf_url = ""
            pdf_link_m = re.search(r'vistaprevia\.php\?data=([^"\'&]+)', tr, re.IGNORECASE)
            if pdf_link_m:
                data_param = pdf_link_m.group(1).replace("&quot;", "").strip()
                pdf_url = f"{self.subdominio_web}/vistaprevia.php?data={data_param}"

            # 8. Estado Acuse / Pago
            acuse_m = re.search(r'name=["\']ACUSEC["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            acuse_content = acuse_m.group(1) if acuse_m else ""
            acuse_title_m = re.search(r'title=["\']([^"\']+)["\']', acuse_content)
            acuse_estado = acuse_title_m.group(1).strip() if acuse_title_m else "-"

            pagada_m = re.search(r'name=["\']PAGADA["\'][^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            pagada_content = pagada_m.group(1) if pagada_m else ""
            pagada_title_m = re.search(r'title=["\']([^"\']+)["\']', pagada_content)
            pago_estado = pagada_title_m.group(1).strip() if pagada_title_m else ""

            estado_combinado = f"{acuse_estado} ({pago_estado})" if pago_estado else acuse_estado

            doc_info = {
                "folio": str(folio),
                "tipo_doc": str(tipo_codigo),
                "tipo_doc_nombre": tipo_nombre,
                "tipo_compra": "Libro de Compras",
                "rut_emisor": rut_emisor,
                "razon_social": razon_social,
                "fecha_docto": fecha_texto,
                "fecha_recepcion": recep_texto,
                "monto_neto": m_neto,
                "monto_iva": m_iva,
                "monto_total": m_total,
                "estado_acuse": estado_combinado,
                "pdf_url": pdf_url,
                "pdf_descargado": False,
                "ruta_pdf": "",
                "pdf_status": "❌ No descargado",
                "origen": "Libro Compras"
            }
            documentos_libro.append(doc_info)

        log_cb(f"✓ Libro de Compras: {len(documentos_libro)} documentos contabilizados encontrados.")
        return documentos_libro

    def consultar_panel_dte(self, mes_num=None, anio_num=None, fecha_desde="", fecha_hasta="",
                             empresa="", usuario="", password="", headless=True, log_cb=print):
        """
        Consulta las facturas y DTEs en el Panel DTE (Recibidos / Pendientes).
        """
        if not self.autenticado or not self.driver:
            self.iniciar_sesion(empresa=empresa, usuario=usuario, password=password, headless=headless, log_cb=log_cb)

        # Calcular fechas si se especificó mes y año
        if mes_num and anio_num and (not fecha_desde or not fecha_hasta):
            _, ultimo_dia = calendar.monthrange(anio_num, mes_num)
            fecha_desde = f"01-{mes_num:02d}-{anio_num}"
            fecha_hasta = f"{ultimo_dia:02d}-{mes_num:02d}-{anio_num}"

        url_panel = f"{self.subdominio_web}/form/compra/paneldte2/index.php"
        log_cb(f"Navegando a Panel DTE Recibidos ({url_panel})...")

        self.driver.get(url_panel)

        wait = WebDriverWait(self.driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "FechaDesdeEmitido")))
        except TimeoutException:
            time.sleep(2.5)

        # Aplicar filtros de fecha y recargar grilla con DataGrid
        log_cb(f"Filtrando Panel DTE emitidos entre {fecha_desde} y {fecha_hasta}...")
        script_filtro = f"""
            if (document.getElementById('FechaDesdeEmitido')) {{
                document.getElementById('FechaDesdeEmitido').value = '{fecha_desde}';
            }}
            if (document.getElementById('FechaHastaEmitido')) {{
                document.getElementById('FechaHastaEmitido').value = '{fecha_hasta}';
            }}
            if (document.getElementById('registros')) {{
                document.getElementById('registros').value = '500';
            }}
            if (window.grdOC && typeof grdOC.reload === 'function') {{
                grdOC.reload();
            }}
        """
        self.driver.execute_script(script_filtro)
        time.sleep(2.5)

        page_html = self.driver.page_source

        # Si no aparecen resultados directos, verificar iframes
        if "vistaPrevia" not in page_html:
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for ifr in iframes:
                    try:
                        self.driver.switch_to.frame(ifr)
                        ifr_html = self.driver.page_source
                        if "vistaPrevia" in ifr_html:
                            page_html = ifr_html
                            break
                    except Exception:
                        pass
                    finally:
                        self.driver.switch_to.default_content()
            except Exception:
                pass

        tr_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', page_html, re.DOTALL | re.IGNORECASE)

        documentos_panel = []
        for tr in tr_blocks:
            pdf_match = re.search(r'onclick=["\']vistaPrevia\(["\']([^"\']+)["\']\)', tr)
            if not pdf_match:
                continue

            b64_url = pdf_match.group(1)
            try:
                decoded_url = base64.b64decode(b64_url).decode('utf-8', errors='ignore')
            except Exception:
                decoded_url = ""

            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
            tds_clean = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', td)).strip() for td in tds]

            folio_m = re.search(r'par1=(\d+)', decoded_url)
            tipo_m = re.search(r'par2=(\d+)', decoded_url)
            rut_m = re.search(r'par3=([0-9kK\.\-]+)', decoded_url)

            folio = folio_m.group(1) if folio_m else ""
            tipo_doc = tipo_m.group(1) if tipo_m else ""
            rut_emisor = rut_m.group(1) if rut_m else ""

            folio_en_celda = tds_clean[2] if len(tds_clean) > 2 else ""
            if not folio and folio_en_celda:
                folio = folio_en_celda

            tipo_compra = tds_clean[3] if len(tds_clean) > 3 else ""
            tipo_texto = tds_clean[4].upper() if len(tds_clean) > 4 else ""
            
            if not tipo_doc:
                tipo_doc = TIPO_TEXTO_A_CODIGO.get(tipo_texto, "33")

            tipo_nombre = TIPOS_DTE_NOMBRES.get(str(tipo_doc), tipo_texto or f"Doc {tipo_doc}")

            fecha_doc = tds_clean[5] if len(tds_clean) > 5 else ""
            rut_en_celda = tds_clean[6] if len(tds_clean) > 6 else ""
            if not rut_emisor and rut_en_celda:
                rut_emisor = rut_en_celda

            razon_social = tds_clean[7] if len(tds_clean) > 7 else ""
            neto_raw = tds_clean[8] if len(tds_clean) > 8 else "$ 0"
            iva_raw = tds_clean[9] if len(tds_clean) > 9 else "$ 0"
            total_raw = tds_clean[10] if len(tds_clean) > 10 else "$ 0"
            fecha_recep = tds_clean[11] if len(tds_clean) > 11 else ""
            plazo_acuse = tds_clean[12] if len(tds_clean) > 12 else ""
            estado_acuse = tds_clean[15] if len(tds_clean) > 15 else plazo_acuse

            m_neto = parse_monto_int(neto_raw)
            m_iva = parse_monto_int(iva_raw)
            m_total = parse_monto_int(total_raw)

            doc_info = {
                "folio": str(folio),
                "tipo_doc": str(tipo_doc),
                "tipo_doc_nombre": tipo_nombre,
                "tipo_compra": tipo_compra,
                "rut_emisor": rut_emisor,
                "razon_social": razon_social,
                "fecha_docto": fecha_doc,
                "fecha_recepcion": fecha_recep,
                "monto_neto": m_neto,
                "monto_iva": m_iva,
                "monto_total": m_total,
                "estado_acuse": estado_acuse,
                "pdf_url": decoded_url,
                "pdf_descargado": False,
                "ruta_pdf": "",
                "pdf_status": "❌ No descargado",
                "origen": "Panel DTE"
            }
            documentos_panel.append(doc_info)

        log_cb(f"✓ Panel DTE: {len(documentos_panel)} documentos pendientes encontrados.")
        return documentos_panel

    def consultar_todo_facturacion_cl(self, mes_num=None, anio_num=None,
                                       empresa="", usuario="", password="", headless=True, log_cb=print):
        """
        Realiza una consulta combinada de Facturación.cl:
          1. Libro de Compras (Contabilizados)
          2. Panel DTE (Recibidos / Pendientes)
        Retorna un diccionario con ambas listas y la lista unificada.
        """
        mes_num = mes_num or datetime.now().month
        anio_num = anio_num or datetime.now().year

        log_cb(f"🔍 Iniciando consulta combinada de Facturación.cl para {NOMBRES_MESES[mes_num]} {anio_num}...")

        # 1. Consultar Libro de Compras
        docs_libro = self.consultar_libro_compras(
            mes_num=mes_num,
            anio_num=anio_num,
            empresa=empresa,
            usuario=usuario,
            password=password,
            headless=headless,
            log_cb=log_cb
        )

        # 2. Consultar Panel DTE
        docs_panel = self.consultar_panel_dte(
            mes_num=mes_num,
            anio_num=anio_num,
            empresa=empresa,
            usuario=usuario,
            password=password,
            headless=headless,
            log_cb=log_cb
        )

        # 3. Consolidar lista unificada sin duplicados
        docs_unificados = []
        vistos = set()

        for d in docs_libro:
            key = (str(d.get("folio")), str(d.get("tipo_doc")), str(d.get("rut_emisor")))
            if key not in vistos:
                vistos.add(key)
                docs_unificados.append(d)

        for d in docs_panel:
            key = (str(d.get("folio")), str(d.get("tipo_doc")), str(d.get("rut_emisor")))
            if key not in vistos:
                vistos.add(key)
                docs_unificados.append(d)

        log_cb(f"✨ Consulta combinada completada: {len(docs_libro)} en Libro Compras, {len(docs_panel)} en Panel DTE (Total: {len(docs_unificados)} documentos).")

        return {
            "libro_compras": docs_libro,
            "panel_dte": docs_panel,
            "todos": docs_unificados
        }

    # Compatibilidad con método anterior
    def consultar_dtes_recibidos(self, *args, **kwargs):
        return self.consultar_panel_dte(*args, **kwargs)

    def descargar_pdf_dte(self, doc, download_dir=None, correlativo=None, contexto_usuario="",
                          usar_ia=False, gemini_api_key="", openai_api_key="", prompt_sistema=None,
                          mes_num=None, log_cb=print):
        """
        Descarga el PDF oficial de un DTE (desde Libro de Compras o Panel DTE)
        y lo guarda con la nomenclatura estándar.
        """
        if not doc or not doc.get("pdf_url"):
            raise ValueError(f"El documento Folio #{doc.get('folio', '')} no contiene una URL válida de PDF.")

        destino_carpeta = download_dir or self.download_dir
        os.makedirs(destino_carpeta, exist_ok=True)

        pdf_url = str(doc.get("pdf_url")).strip()
        folio = str(doc.get("folio", "")).strip()

        # Si es URL relativa, agregar subdominio
        if pdf_url.startswith("/"):
            pdf_url = f"https://www.facturacion.cl{pdf_url}"
        elif not pdf_url.startswith("http"):
            pdf_url = f"{self.subdominio_web}/{pdf_url.lstrip('/')}"

        # Asegurar cookies de sesión
        if not self.session and self.driver:
            self.session = requests.Session()
            for c in self.driver.get_cookies():
                self.session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))

        log_cb(f"Descargando PDF Folio #{folio} ({doc.get('tipo_doc_nombre', 'DTE')}) [{doc.get('origen', '')}]...")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.subdominio_web}/form/contabilidad/libros2/?indice=2"
        }

        r = self.session.get(pdf_url, headers=headers, timeout=30)
        if r.status_code != 200 or len(r.content) < 500:
            # Fallback: navegar con Selenium si requests no captura
            if self.driver:
                self.driver.get(pdf_url)
                time.sleep(2.5)
                for c in self.driver.get_cookies():
                    self.session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
                r = self.session.get(pdf_url, headers=headers, timeout=30)

        if r.status_code != 200 or len(r.content) < 500:
            raise Exception(f"No se pudo descargar el PDF (HTTP {r.status_code}, {len(r.content)} bytes).")

        # Determinar glosa (IA o manual)
        glosa_final = str(contexto_usuario).strip()
        if usar_ia:
            ruta_temp = os.path.join(destino_carpeta, f"temp_fcl_ia_{folio}.pdf")
            try:
                with open(ruta_temp, "wb") as f_tmp:
                    f_tmp.write(r.content)
                import ai_context
                glosa_ia = ai_context.obtener_contexto_factura(
                    ruta_pdf=ruta_temp,
                    doc_info=doc,
                    api_key_gemini=gemini_api_key,
                    api_key_openai=openai_api_key,
                    prompt_sistema=prompt_sistema,
                    log_cb=log_cb
                )
                if glosa_ia and glosa_ia.strip():
                    glosa_final = glosa_ia.strip()
            except Exception as e_ia:
                log_cb(f"Aviso IA Facturacion.cl: {e_ia}")
            finally:
                if os.path.exists(ruta_temp):
                    try:
                        os.remove(ruta_temp)
                    except Exception:
                        pass

        # Generar nombre oficial
        nombre_archivo = generar_nombre_archivo_facturacion_cl(
            doc_info=doc,
            correlativo=correlativo,
            glosa=glosa_final,
            mes_num=mes_num
        )

        ruta_final = os.path.join(destino_carpeta, nombre_archivo)

        with open(ruta_final, "wb") as f:
            f.write(r.content)

        doc["pdf_descargado"] = True
        doc["ruta_pdf"] = ruta_final
        doc["pdf_status"] = "✓ Descargado"

        log_cb(f"✓ Documento DTE guardado: {os.path.basename(ruta_final)}")
        return ruta_final

    def cerrar_sesion(self, log_cb=print):
        """Cierra el navegador y limpia la sesión."""
        with self.lock:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
            self.session = None
            self.autenticado = False
            log_cb("Sesión de Facturacion.cl cerrada.")


# Instancia global singleton
gestor_facturacion_cl = GestorFacturacionCL()

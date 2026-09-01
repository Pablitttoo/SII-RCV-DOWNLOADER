"""
Script para interactuar con el SII (Registro de Compras RCV y Portal MIPE).
Utiliza una sesión persistente de Selenium + Requests para mantener la sesión
abierta en segundo plano, evitando bloqueos por re-autenticación constante y
haciendo las consultas y descargas de facturas prácticamente instantáneas.
"""

import os
import sys
import re
import csv
import glob
import time
import calendar
import tempfile
import threading
import requests

# Forzar encoding UTF-8 y flush inmediato en prints
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
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
    UnexpectedAlertPresentException,
)
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

from ..utils import obtener_ruta_base, cargar_variables_entorno

DIRECTORIO_ACTUAL = obtener_ruta_base()
cargar_variables_entorno()

# ---------- Configuración ----------
DOWNLOAD_DIR = r"C:\Users\Pablo\Documents\test_facs"
# Carpeta temporal del sistema para descargas intermedias de scraping (CSVs de RCV)
TEMP_RCV_DIR = os.path.join(tempfile.gettempdir(), "sii_rcv_temp_downloads")


def recargar_credenciales():
    """Recarga las credenciales de .env por si fueron modificadas o cargadas tarde."""
    global SII_RUT, SII_CLAVE, RUT_EMPRESA
    cargar_variables_entorno()
    SII_RUT = os.getenv("SII_RUT", "").strip()
    SII_CLAVE = os.getenv("SII_CLAVE", "").strip()
    if not RUT_EMPRESA:
        RUT_EMPRESA = os.getenv("RUT_EMPRESA", "").strip()
    return SII_RUT, SII_CLAVE


def set_download_dir(nueva_ruta):
    """Actualiza la carpeta de destino final para los PDFs descargados."""
    global DOWNLOAD_DIR
    if nueva_ruta:
        try:
            ruta_abs = os.path.abspath(nueva_ruta)
            os.makedirs(ruta_abs, exist_ok=True)
            DOWNLOAD_DIR = ruta_abs
        except (FileNotFoundError, OSError, Exception):
            fallback = os.path.join(os.path.expanduser("~"), "Downloads")
            try:
                os.makedirs(fallback, exist_ok=True)
            except Exception:
                pass
            DOWNLOAD_DIR = fallback


SII_RUT     = os.getenv("SII_RUT", "").strip()
SII_CLAVE   = os.getenv("SII_CLAVE", "").strip()
RUT_EMPRESA = os.getenv("RUT_EMPRESA", "").strip()


def set_rut_empresa(nuevo_rut):
    """Actualiza el RUT de la empresa objetivo de forma global."""
    global RUT_EMPRESA
    if nuevo_rut:
        RUT_EMPRESA = str(nuevo_rut).strip()
    else:
        RUT_EMPRESA = ""


def limpiar_monto_int(val):
    """Parsea un monto monetario a entero limpio (sin puntos ni signos)."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    val_str = str(val).replace(".", "").replace(",", "").replace("$", "").strip()
    try:
        return int(val_str)
    except Exception:
        return 0


_hoy = datetime.now()
FECHA_CONSULTA_STR = _hoy.strftime("%d/%m/%Y")
FECHA_CONSULTA_ISO = _hoy.strftime("%Y-%m-%d")

URL_LOGIN = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?https://www4.sii.cl/consdcvinternetui/#/index"
URL_RCV   = "https://www4.sii.cl/consdcvinternetui/#/index"
URL_MIPE_SEL = "https://www1.sii.cl/cgi-bin/Portal001/mipeSelEmpresa.cgi?DESDE_DONDE_URL=OPCION%3D1%26TIPO%3D4"

NOMBRES_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

MAPA_TIPOS_DOC = {
    "33": "Factura Electrónica",
    "34": "Factura Exenta Electrónica",
    "43": "Liquidación Factura Electrónica",
    "46": "Factura de Compra Electrónica",
    "56": "Nota de Débito Electrónica",
    "61": "Nota de Crédito Electrónica",
    "110": "Factura Exportación Electrónica",
    "111": "Nota de Débito Exportación",
    "112": "Nota de Crédito Exportación",
}


def crear_driver(headless=True):
    """Crea un WebDriver de Chrome con modo stealth activado."""
    global DOWNLOAD_DIR
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    except (FileNotFoundError, OSError, Exception):
        DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        except Exception:
            pass

    options = Options()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")

    # Necesario para stealth
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Configurar carpeta de descarga automática aislada en TEMP
    os.makedirs(TEMP_RCV_DIR, exist_ok=True)
    prefs = {
        "download.default_directory": TEMP_RCV_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)

    # Inicializar driver con Selenium Manager nativo (resuelve la versión exacta de Chromium/Chrome)
    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            driver = webdriver.Chrome(options=options)

    # Permitir descargas en segundo plano a la carpeta temporal aislada
    try:
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": TEMP_RCV_DIR}
        )
    except Exception:
        pass

    # Aplica técnicas de evasión de detección de bots
    stealth(
        driver,
        languages=["es-CL", "es"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    if not headless:
        driver.maximize_window()
    return driver


def cerrar_sesion_sii(driver, log_cb=print):
    """Cierra limpiamente la sesión en el servidor del SII."""
    try:
        driver.get("https://zeusr.sii.cl/cgi_AUT2000/autLogout.cgi")
        time.sleep(1.5)
    except Exception:
        pass


def es_pagina_login_o_expirada(driver):
    """
    Detecta de forma precisa si el navegador se encuentra en la pantalla de login del SII
    o si la sesión ha expirado por inactividad.
    """
    if not driver:
        return True
    try:
        url_actual = (driver.current_url or "").lower()

        # 1. Chequeo de URLs de autenticación, logout o Zeus
        indicadores_url = [
            "ingresorutclave",
            "aut2000",
            "autlogout",
            "autautenticacion",
            "zeusr.sii.cl",
            "zeus.sii.cl",
        ]
        if any(ind in url_actual for ind in indicadores_url):
            return True

        # 2. Chequeo de campos de login presentes en pantalla
        if driver.find_elements(By.ID, "rutcntr") or driver.find_elements(By.ID, "bt_ingresar"):
            return True
        if driver.find_elements(By.ID, "clave") and driver.find_elements(By.NAME, "RUTCtr"):
            return True

        # 3. Chequeo de textos de expiración en el cuerpo del documento
        try:
            body_text = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
            textos_expiracion = [
                "su sesión ha expirado",
                "sesión terminada",
                "sesión finalizada",
                "para acceder a este servicio debe autenticarse",
                "ha superado el tiempo límite",
                "error 01.01.203",
                "sesión no válida",
                "sesión caducada"
            ]
            if any(t in body_text for t in textos_expiracion):
                return True
        except Exception:
            pass

        return False
    except Exception:
        return True


def login(driver, wait, log_cb=print):
    """Rellena RUT y clave del SII y hace click en Ingresar."""
    driver.get(URL_LOGIN)
    log_cb("Abriendo página de autenticación del SII...")

    campo_rut = wait.until(EC.element_to_be_clickable((By.ID, "rutcntr")))
    campo_rut.clear()
    campo_rut.send_keys(SII_RUT)

    campo_clave = driver.find_element(By.ID, "clave")
    campo_clave.clear()
    campo_clave.send_keys(SII_CLAVE)

    boton = driver.find_element(By.ID, "bt_ingresar")
    boton.click()

    log_cb("Credenciales enviadas, validando sesión en el SII...")
    time.sleep(2.5)

    try:
        wait.until(lambda d: "IngresoRutClave" not in d.current_url)
    except TimeoutException:
        raise RuntimeError("Tiempo de espera agotado al conectar con el servidor de autenticación del SII.")

    # Verificar mensaje de exceso de sesiones
    body_text = ""
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        pass

    if "superado el máximo de sesiones" in body_text.lower() or "01.01.203" in body_text:
        msg = (
            "El SII indica: 'Ha superado el máximo de sesiones autenticadas simultáneas (Error 01.01.203)'. "
            "Por favor espera unos 5 minutos a que el SII expire las sesiones previas."
        )
        log_cb(f"\n[AVISO] {msg}\n")
        raise RuntimeError(msg)

    log_cb("¡Sesión iniciada correctamente en el SII!")


def cerrar_modales_bloqueantes(driver):
    """
    Cierra o elimina modales y capas oscuras (modal-backdrop) del SII
    que puedan bloquear o interceptar clicks en la interfaz.
    """
    if not driver:
        return
    try:
        driver.execute_script("""
            // 1. Click en botones de cierre de modales activos
            document.querySelectorAll('.modal.in button, .modal.show button, .modal button[data-dismiss="modal"], .modal .close, button.btn-primary').forEach(function(b) {
                if (b.offsetWidth > 0 || b.offsetHeight > 0) {
                    try { b.click(); } catch(e) {}
                }
            });
            // 2. Eliminar capas backdrop que bloquean la pantalla
            document.querySelectorAll('.modal-backdrop, .modal-open .modal-backdrop').forEach(function(el) {
                try { el.parentNode.removeChild(el); } catch(e) {}
            });
            // 3. Restaurar scroll y clases del body
            if (document.body) {
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('padding-right');
            }
        """)
    except Exception:
        pass


def click_seguro(driver, elem):
    """
    Intenta hacer click estándar. Si es interceptado por un modal o backdrop,
    limpia los modales y ejecuta el click directamente vía JavaScript.
    """
    if not elem or not driver:
        return
    try:
        elem.click()
    except Exception:
        cerrar_modales_bloqueantes(driver)
        time.sleep(0.3)
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", elem)
        except Exception:
            driver.execute_script("arguments[0].click();", elem)


def ir_a_rcv(driver, wait, log_cb=print):
    """Navega al Registro de Compras y Ventas (RCV) y valida que la sesión no haya expirado."""
    log_cb("Navegando al Registro de Compras (RCV)...")
    driver.get(URL_RCV)
    time.sleep(2.0)

    # 1. Si el servidor del SII nos redirigió a la pantalla de login por inactividad
    if es_pagina_login_o_expirada(driver):
        log_cb("⚠️ Sesión expirada detectada al ingresar al RCV. Reautenticando en el SII...")
        login(driver, wait, log_cb=log_cb)
        gestor_sesion.actualizar_cookies_requests()
        log_cb("Cargando RCV tras reautenticación...")
        driver.get(URL_RCV)
        time.sleep(2.0)

    # 2. Esperar elemento principal del RCV con recuperación automática
    try:
        wait.until(EC.presence_of_element_located((By.ID, "periodoMes")))
        cerrar_modales_bloqueantes(driver)
        time.sleep(2.0)
    except TimeoutException:
        # Segundo chequeo por si tardó en cargar la redirección
        if es_pagina_login_o_expirada(driver):
            log_cb("⚠️ Redirección a login detectada en RCV. Reautenticando...")
            login(driver, wait, log_cb=log_cb)
            gestor_sesion.actualizar_cookies_requests()
            driver.get(URL_RCV)
            wait.until(EC.presence_of_element_located((By.ID, "periodoMes")))
        cerrar_modales_bloqueantes(driver)
        time.sleep(2.0)
    except Exception:
        cerrar_modales_bloqueantes(driver)
        time.sleep(2.0)


def seleccionar_empresa(driver, wait, rut_empresa=None, log_cb=print):
    """Selecciona la empresa en el RCV si hay selector múltiple."""
    rut_target = rut_empresa or RUT_EMPRESA
    if not rut_target:
        return

    rut_limpio = rut_target.replace("-", "").replace(".", "").strip()
    cerrar_modales_bloqueantes(driver)
    try:
        selects = driver.find_elements(By.TAG_NAME, "select")
        encontrado = False
        for sel_elem in selects:
            try:
                opciones = Select(sel_elem)
                for opcion in opciones.options:
                    texto = opcion.text.replace("-", "").replace(".", "").replace(" ", "")
                    val = (opcion.get_attribute("value") or "").replace("-", "").replace(".", "").replace(" ", "")
                    if rut_limpio in texto or (val and rut_limpio in val):
                        if not opcion.is_selected():
                            opciones.select_by_visible_text(opcion.text)
                            driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", sel_elem)
                            log_cb(f"Empresa seleccionada en RCV: {opcion.text.strip()}")
                            time.sleep(2.5)
                        encontrado = True
                        return
            except Exception:
                continue
        if not encontrado:
            log_cb(f"Aviso: RUT empresa ({rut_target}) no requirió selección o ya está activa.")
    except Exception as e:
        log_cb(f"Aviso seleccionando empresa en RCV: {e}")


def seleccionar_periodo(driver, wait, mes_num=None, anio_num=None, log_cb=print):
    """Selecciona mes y año en el RCV."""
    m = int(mes_num or _hoy.month)
    a = int(anio_num or _hoy.year)
    nombre_mes = NOMBRES_MESES[m] if 1 <= m <= 12 else str(m)

    log_cb(f"Configurando periodo: {nombre_mes} {a}...")
    cerrar_modales_bloqueantes(driver)
    try:
        sel_mes = wait.until(EC.presence_of_element_located((By.ID, "periodoMes")))
        sel_mes_obj = Select(sel_mes)
        try:
            sel_mes_obj.select_by_value(f"{m:02d}")
        except NoSuchElementException:
            sel_mes_obj.select_by_visible_text(nombre_mes)

        try:
            sel_anio = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "select[ng-model='periodoAnio']"))
            )
            Select(sel_anio).select_by_value(str(a))
        except TimeoutException:
            todos = driver.find_elements(By.TAG_NAME, "select")
            if len(todos) >= 3:
                Select(todos[2]).select_by_value(str(a))

        log_cb(f"Periodo seleccionado: {nombre_mes} {a}")
    except Exception as e:
        log_cb(f"Aviso seleccionando periodo: {e}")


def consultar(driver, wait, log_cb=print):
    """Hace click en Consultar y espera carga de resultados cerrando cualquier popup."""
    log_cb("Consultando datos en RCV...")
    cerrar_modales_bloqueantes(driver)
    try:
        boton = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//button[normalize-space(text())='Consultar'] | //input[@type='submit' and contains(@value, 'Consultar')] | //button[contains(@class, 'btn') and contains(., 'Consultar')]"
        )))
        click_seguro(driver, boton)
        time.sleep(2.5)
        # Si apareció un modal de aviso (ej: "No se registran compras"), intentar cerrarlo suavemente
        cerrar_modales_bloqueantes(driver)
    except TimeoutException:
        log_cb("AVISO: No se encontró el botón Consultar o la página no cargó a tiempo.")
    except Exception as e:
        log_cb(f"Aviso al presionar Consultar: {e}")


def ir_a_facturas_recibidas(driver, wait, rut_empresa=None, log_cb=print):
    """Navega al sistema MIPE (Facturas Recibidas) y valida la sesión."""
    rut_target = rut_empresa or RUT_EMPRESA
    rut_limpio = rut_target.replace("-", "").replace(".", "").strip() if rut_target else ""

    log_cb("Navegando al portal de Facturas Recibidas (MIPE)...")
    driver.get(URL_MIPE_SEL)
    time.sleep(2.0)

    # Si redirigió a login
    if es_pagina_login_o_expirada(driver):
        log_cb("⚠️ Sesión expirada detectada al ingresar a MIPE. Reautenticando en el SII...")
        login(driver, wait, log_cb=log_cb)
        gestor_sesion.actualizar_cookies_requests()
        log_cb("Cargando portal MIPE tras reautenticación...")
        driver.get(URL_MIPE_SEL)
        time.sleep(2.0)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
    except TimeoutException:
        if es_pagina_login_o_expirada(driver):
            log_cb("⚠️ Redirección a login en MIPE. Reautenticando...")
            login(driver, wait, log_cb=log_cb)
            gestor_sesion.actualizar_cookies_requests()
            driver.get(URL_MIPE_SEL)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))

    sel = Select(driver.find_element(By.TAG_NAME, "select"))
    for op in sel.options:
        texto = op.text.replace("-", "").replace(".", "").replace(" ", "")
        val   = op.get_attribute("value").replace("-", "").replace(".", "")
        if rut_limpio and (rut_limpio in texto or rut_limpio in val):
            sel.select_by_value(op.get_attribute("value"))
            log_cb(f"Empresa seleccionada en MIPE: {op.text}")
            break

    try:
        btn_submit = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
        click_seguro(driver, btn_submit)
    except Exception:
        pass
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    except Exception:
        pass
    time.sleep(2.5)


# ==========================================================
# GESTOR DE SESIÓN PERSISTENTE (SINGLETON)
# ==========================================================
class GestorSesionSII:
    _instancia = None

    @classmethod
    def get_instancia(cls):
        if cls._instancia is None:
            cls._instancia = cls()
        return cls._instancia

    def __init__(self):
        self.driver = None
        self.wait = None
        self.session_req = None
        self.lock = threading.Lock()
        self.mapa_mipe_por_periodo = {}  # {(mes, anio): {folio: {'codigo': ..., 'emisor': ...}}}

    def esta_activo(self):
        """Comprueba si el navegador sigue vivo y respondiendo."""
        if self.driver is None:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def sesion_valida(self):
        """Comprueba si el navegador no se encuentra en pantalla de login o con sesión expirada."""
        if not self.esta_activo():
            return False
        return not es_pagina_login_o_expirada(self.driver)

    def reautenticar(self, headless=True, log_cb=print):
        """Vuelve a iniciar sesión limpia en el SII si la sesión actual caducó."""
        log_cb("⚠️ Sesión del SII caducada o inactiva. Reautenticando...")
        try:
            if self.esta_activo():
                login(self.driver, self.wait, log_cb=log_cb)
                self.actualizar_cookies_requests()
                log_cb("✓ Sesión reestablecida exitosamente.")
                return self.driver, self.wait
        except Exception as e:
            log_cb(f"Reinicio completo de sesión tras aviso: {e}")
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            self.driver = None

        self.driver = crear_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, 20)
        login(self.driver, self.wait, log_cb=log_cb)
        self.actualizar_cookies_requests()
        return self.driver, self.wait

    def asegurar_sesion(self, headless=True, log_cb=print):
        """Mantiene y reutiliza la sesión abierta. Si no existe, se cerró o expiró, autentica."""
        with self.lock:
            if self.esta_activo():
                if es_pagina_login_o_expirada(self.driver):
                    return self.reautenticar(headless=headless, log_cb=log_cb)

                log_cb("✓ Reutilizando sesión activa del SII...")
                self.actualizar_cookies_requests()
                return self.driver, self.wait

            # Iniciar nueva sesión
            log_cb("Iniciando conexión persistente con el SII...")
            self.driver = crear_driver(headless=headless)
            self.wait = WebDriverWait(self.driver, 20)
            login(self.driver, self.wait, log_cb=log_cb)
            self.actualizar_cookies_requests()
            return self.driver, self.wait

    def actualizar_cookies_requests(self):
        if not self.driver:
            return
        s = requests.Session()
        for c in self.driver.get_cookies():
            s.cookies.set(c['name'], c['value'])
        s.headers.update({
            "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
            "Referer": "https://www1.sii.cl",
        })
        self.session_req = s

    def obtener_mapa_mipe(self, mes, anio, headless=True, forzar_recarga=False, log_cb=print):
        """Obtiene y cachea el mapeo de folios a códigos de descarga en MIPE para el mes, recorriendo todas las páginas disponibles."""
        clave = (int(mes), int(anio))
        if not forzar_recarga and clave in self.mapa_mipe_por_periodo and self.mapa_mipe_por_periodo[clave]:
            return self.mapa_mipe_por_periodo[clave]

        driver, wait = self.asegurar_sesion(headless=headless, log_cb=log_cb)
        with self.lock:
            ir_a_facturas_recibidas(driver, wait, log_cb=log_cb)

            ultimo_dia = calendar.monthrange(anio, mes)[1]
            f_desde = f"01/{mes:02d}/{anio}"
            f_hasta = f"{ultimo_dia:02d}/{mes:02d}/{anio}"

            log_cb(f"Consultando catálogo MIPE del mes ({f_desde} al {f_hasta})...")

            for nombre in ["FEC_DESDE", "fec_desde"]:
                for c in driver.find_elements(By.NAME, nombre):
                    driver.execute_script("arguments[0].value = arguments[1];", c, f_desde)

            for nombre in ["FEC_HASTA", "fec_hasta"]:
                for c in driver.find_elements(By.NAME, nombre):
                    driver.execute_script("arguments[0].value = arguments[1];", c, f_hasta)

            try:
                btns = driver.find_elements(
                    By.XPATH,
                    "//input[@type='submit' and (contains(@value, 'Buscar') or contains(@value, 'Consultar'))] | //button[contains(., 'Buscar') or contains(., 'Consultar')]"
                )
                if btns:
                    driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(2.5)
            except Exception as e:
                log_cb(f"Aviso al enviar filtro MIPE: {e}")

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            except Exception:
                pass

            time.sleep(2.0)

            mapa = {}
            pagina_actual = 1
            max_paginas = 25

            while pagina_actual <= max_paginas:
                filas = driver.find_elements(By.XPATH, "//table//tr")
                nuevos_en_pagina = 0

                for fila in filas:
                    celdas = fila.find_elements(By.XPATH, ".//td")
                    if len(celdas) < 5:
                        continue

                    links = fila.find_elements(By.XPATH, ".//a[contains(@href, 'CODIGO=')]")
                    if not links:
                        continue

                    href = links[0].get_attribute("href") or ""
                    m_cod = re.search(r"CODIGO=(\d+)", href)
                    if not m_cod:
                        continue

                    codigo = m_cod.group(1)
                    emisor = celdas[1].text.strip() if len(celdas) > 1 else ""
                    razon_social = celdas[2].text.strip() if len(celdas) > 2 else ""
                    tipo_doc = celdas[3].text.strip() if len(celdas) > 3 else "Factura"
                    folio = celdas[4].text.strip() if len(celdas) > 4 else codigo
                    fecha = celdas[5].text.strip() if len(celdas) > 5 else ""

                    if folio and str(folio) not in mapa:
                        mapa[str(folio)] = {
                            "codigo": codigo,
                            "emisor": emisor,
                            "razon_social": razon_social,
                            "tipo_doc": tipo_doc,
                            "folio": str(folio),
                            "fecha": fecha,
                        }
                        nuevos_en_pagina += 1

                # Intentar avanzar a la siguiente página si existe paginación
                candidatos_sig = driver.find_elements(
                    By.XPATH,
                    "//a[contains(translate(text(), 'SIGUIENTE', 'siguiente'), 'siguiente') or contains(text(), '>>') or contains(text(), 'Próxima')] | "
                    "//input[@type='submit' and (contains(translate(@value, 'SIGUIENTE', 'siguiente'), 'siguiente') or contains(@value, '>>'))] | "
                    f"//a[normalize-space(text())='{pagina_actual + 1}']"
                )

                if candidatos_sig and nuevos_en_pagina > 0:
                    try:
                        log_cb(f"   -> Indexando página {pagina_actual + 1} de MIPE ({len(mapa)} folios hasta ahora)...")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", candidatos_sig[0])
                        time.sleep(2.5)
                        pagina_actual += 1
                    except Exception:
                        break
                else:
                    break

            self.mapa_mipe_por_periodo[clave] = mapa
            log_cb(f"Catálogo MIPE indexado: {len(mapa)} folios encontrados para {NOMBRES_MESES[mes]} {anio}.")
            self.actualizar_cookies_requests()
            return mapa

    def buscar_folio_directo_mipe(self, folio, mes=None, anio=None, rut_emisor=None, headless=True, log_cb=print):
        """Búsqueda directa e individual de un folio específico en el formulario de búsqueda de MIPE."""
        driver, wait = self.asegurar_sesion(headless=headless, log_cb=log_cb)
        with self.lock:
            ir_a_facturas_recibidas(driver, wait, log_cb=log_cb)
            f_folio = str(folio).strip()

            # Configurar rango amplio del año si no se tiene fecha precisa
            a_val = int(anio or datetime.now().year)
            m_val = int(mes or datetime.now().month)
            f_desde = f"01/01/{a_val}"
            f_hasta = f"31/12/{a_val}"

            for nombre in ["FEC_DESDE", "fec_desde"]:
                for c in driver.find_elements(By.NAME, nombre):
                    driver.execute_script("arguments[0].value = arguments[1];", c, f_desde)

            for nombre in ["FEC_HASTA", "fec_hasta"]:
                for c in driver.find_elements(By.NAME, nombre):
                    driver.execute_script("arguments[0].value = arguments[1];", c, f_hasta)

            # Llenar campo de búsqueda de Folio
            for nombre in ["FOLIO", "folio", "NUM_FOLIO", "num_folio"]:
                for c in driver.find_elements(By.NAME, nombre):
                    driver.execute_script("arguments[0].value = arguments[1];", c, f_folio)

            if rut_emisor:
                rut_clean = rut_emisor.replace(".", "").strip()
                for nombre in ["RUT_EMISOR", "rut_emisor", "RUT", "rut"]:
                    for c in driver.find_elements(By.NAME, nombre):
                        driver.execute_script("arguments[0].value = arguments[1];", c, rut_clean)

            try:
                btns = driver.find_elements(
                    By.XPATH,
                    "//input[@type='submit' and (contains(@value, 'Buscar') or contains(@value, 'Consultar'))] | //button[contains(., 'Buscar') or contains(., 'Consultar')]"
                )
                if btns:
                    driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(2.5)
            except Exception as e:
                log_cb(f"Aviso búsqueda directa folio #{f_folio}: {e}")

            time.sleep(1.5)
            filas = driver.find_elements(By.XPATH, "//table//tr")
            for fila in filas:
                links = fila.find_elements(By.XPATH, ".//a[contains(@href, 'CODIGO=')]")
                if links:
                    href = links[0].get_attribute("href") or ""
                    m_cod = re.search(r"CODIGO=(\d+)", href)
                    if m_cod:
                        codigo = m_cod.group(1)
                        celdas = fila.find_elements(By.XPATH, ".//td")
                        emisor = celdas[1].text.strip() if len(celdas) > 1 else ""
                        razon_social = celdas[2].text.strip() if len(celdas) > 2 else ""
                        tipo_doc = celdas[3].text.strip() if len(celdas) > 3 else "Factura"
                        f_text = celdas[4].text.strip() if len(celdas) > 4 else f_folio
                        fecha = celdas[5].text.strip() if len(celdas) > 5 else ""

                        item = {
                            "codigo": codigo,
                            "emisor": emisor,
                            "razon_social": razon_social,
                            "tipo_doc": tipo_doc,
                            "folio": f_text or f_folio,
                            "fecha": fecha,
                        }
                        clave = (m_val, a_val)
                        if clave not in self.mapa_mipe_por_periodo:
                            self.mapa_mipe_por_periodo[clave] = {}
                        self.mapa_mipe_por_periodo[clave][f_folio] = item
                        if f_text:
                            self.mapa_mipe_por_periodo[clave][str(f_text)] = item
                        self.actualizar_cookies_requests()
                        return item
        return None

    def cerrar(self, log_cb=print):
        with self.lock:
            if self.session_req:
                try:
                    self.session_req.get("https://zeusr.sii.cl/cgi_AUT2000/autLogout.cgi", timeout=4)
                except Exception:
                    pass
                self.session_req = None
            if self.driver:
                log_cb("Cerrando sesión en el servidor del SII...")
                try:
                    cerrar_sesion_sii(self.driver, log_cb=log_cb)
                except Exception:
                    pass
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                self.wait = None
                self.mapa_mipe_por_periodo.clear()
                log_cb("Sesión cerrada limpiamente.")

    def cerrar_sesion(self, log_cb=print):
        return self.cerrar(log_cb=log_cb)


gestor_sesion = GestorSesionSII.get_instancia()


# ==========================================================
# FUNCIONES PRINCIPALES (USAN EL GESTOR DE SESIÓN PERSISTENTE)
# ==========================================================
def consultar_facturas_rcv(mes_num=None, anio_num=None, pestanas=None, rut_empresa=None, headless=True, log_cb=print):
    """
    Consulta el RCV reutilizando la sesión persistente (no cierra el navegador).
    """
    recargar_credenciales()
    if not SII_RUT or not SII_CLAVE:
        msg = "ERROR: Faltan SII_RUT o SII_CLAVE en el archivo .env"
        log_cb(msg)
        return {"exito": False, "mensaje": msg, "documentos": [], "totales": {}}

    if rut_empresa:
        set_rut_empresa(rut_empresa)

    rut_objetivo = rut_empresa or RUT_EMPRESA
    m = int(mes_num or _hoy.month)
    a = int(anio_num or _hoy.year)
    pills = pestanas or ["Registro", "Pendientes", "Reclamados"]
    nombre_mes = NOMBRES_MESES[m] if 1 <= m <= 12 else str(m)

    log_cb(f"\n==========================================")
    log_cb(f"Consultando RCV: {nombre_mes} {a} | RUT Empresa: {rut_objetivo or 'Predeterminado'}")
    log_cb(f"==========================================\n")

    MAPA_SELECTORES_TABS = {
        "Registro": "//a[@ui-sref='compraRegistro' or contains(@href, 'compraRegistro')]",
        "Pendientes": "//a[@ui-sref='compraPendiente' or contains(@href, 'compraPendiente')]",
        "Reclamados": "//a[@ui-sref='compraReclamados' or contains(@href, 'compraReclamados')]",
        "No Incluir": "//a[@ui-sref='compraNoIncluir' or contains(@href, 'compraNoIncluir')]",
    }

    todos_documentos = []

    try:
        driver, wait = gestor_sesion.asegurar_sesion(headless=headless, log_cb=log_cb)

        with gestor_sesion.lock:
            # Asegurar que la carpeta temporal existe y está limpia
            os.makedirs(TEMP_RCV_DIR, exist_ok=True)
            for f_tmp in glob.glob(os.path.join(TEMP_RCV_DIR, "*")):
                try:
                    os.remove(f_tmp)
                except Exception:
                    pass

            # Limpiar posibles CSVs residuales previos en DOWNLOAD_DIR
            if DOWNLOAD_DIR and os.path.exists(DOWNLOAD_DIR):
                for f_old in glob.glob(os.path.join(DOWNLOAD_DIR, "RCV_COMPRAS_*.csv")):
                    try:
                        os.remove(f_old)
                    except Exception:
                        pass

            try:
                driver.execute_cdp_cmd(
                    "Page.setDownloadBehavior",
                    {"behavior": "allow", "downloadPath": TEMP_RCV_DIR}
                )
            except Exception:
                pass

            ir_a_rcv(driver, wait, log_cb=log_cb)
            seleccionar_empresa(driver, wait, rut_empresa=rut_objetivo, log_cb=log_cb)
            seleccionar_periodo(driver, wait, mes_num=m, anio_num=a, log_cb=log_cb)
            consultar(driver, wait, log_cb=log_cb)

            for pestana in pills:
                log_cb(f"Consultando pestaña: {pestana}...")
                cerrar_modales_bloqueantes(driver)

                xpath_tab = MAPA_SELECTORES_TABS.get(
                    pestana,
                    f"//ul[contains(@class, 'nav')]//a[contains(., '{pestana}')]"
                )

                try:
                    tab_elem = driver.find_element(By.XPATH, xpath_tab)
                    click_seguro(driver, tab_elem)
                    time.sleep(2.5)
                except Exception as e:
                    log_cb(f"Aviso pestaña {pestana}: {e}")

                cerrar_modales_bloqueantes(driver)
                # Limpiar cualquier archivo previo en la carpeta temporal de scraping
                for f_tmp in glob.glob(os.path.join(TEMP_RCV_DIR, "*")):
                    try:
                        os.remove(f_tmp)
                    except Exception:
                        pass

                archivos_antes = set(glob.glob(os.path.join(TEMP_RCV_DIR, "*.csv")))

                try:
                    btns = driver.find_elements(By.XPATH, "//button | //a[contains(@class, 'btn')] | //input[@type='button']")
                    btn_desc = [b for b in btns if "detalle" in b.text.lower() and b.is_displayed()]
                    if not btn_desc:
                        btn_desc = [b for b in btns if "descargar" in b.text.lower() and "resumen" not in b.text.lower() and b.is_displayed()]
                    if not btn_desc:
                        btn_desc = [b for b in btns if "descargar" in b.text.lower() and b.is_displayed()]

                    if not btn_desc:
                        log_cb(f"No hay botón de detalles visible en '{pestana}' (0 documentos).")
                        continue

                    click_seguro(driver, btn_desc[0])
                except Exception as e:
                    log_cb(f"Aviso descargando detalles de '{pestana}': {e}")
                    continue

                csv_path = None
                for _ in range(20):
                    time.sleep(0.5)
                    archivos_despues = set(glob.glob(os.path.join(TEMP_RCV_DIR, "*.csv")))
                    nuevos = list(archivos_despues - archivos_antes)
                    nuevos_detalles = [f for f in nuevos if "resumen" not in os.path.basename(f).lower()]
                    if nuevos_detalles:
                        csv_path = nuevos_detalles[0]
                        break
                    elif nuevos:
                        csv_path = nuevos[0]
                        break

                if not csv_path:
                    all_csvs = glob.glob(os.path.join(TEMP_RCV_DIR, "*.csv"))
                    all_csvs_detalles = [f for f in all_csvs if "resumen" not in os.path.basename(f).lower()]
                    if all_csvs_detalles:
                        all_csvs_detalles.sort(key=os.path.getmtime, reverse=True)
                        if time.time() - os.path.getmtime(all_csvs_detalles[0]) < 30:
                            csv_path = all_csvs_detalles[0]

                if not csv_path:
                    log_cb(f"No se generó CSV para pestaña '{pestana}'.")
                    continue

                log_cb(f"Extrayendo facturas de '{pestana}' ({os.path.basename(csv_path)})...")

                try:
                    with open(csv_path, mode="r", encoding="latin-1", errors="replace") as f:
                        lector = csv.DictReader(f, delimiter=";")
                        docs_en_pestana = 0
                        for r in lector:
                            codigo_tipo = str(r.get("Tipo Doc", "")).strip()
                            tipo_nombre = MAPA_TIPOS_DOC.get(codigo_tipo, f"Doc {codigo_tipo}")

                            doc = {
                                "tipo_doc": codigo_tipo,
                                "tipo_doc_codigo": codigo_tipo,
                                "tipo_doc_nombre": tipo_nombre,
                                "folio": str(r.get("Folio", "")).strip(),
                                "rut_emisor": str(r.get("RUT Proveedor", "")).strip(),
                                "razon_social": str(r.get("Razon Social", "")).strip(),
                                "fecha_docto": str(r.get("Fecha Docto", "")).strip(),
                                "fecha_recepcion": str(r.get("Fecha Recepcion", "")).strip(),
                                "fecha_acuse": str(r.get("Fecha Acuse", "")).strip(),
                                "monto_neto": limpiar_monto_int(r.get("Monto Neto", 0)),
                                "monto_exento": limpiar_monto_int(r.get("Monto Exento", 0)),
                                "monto_iva": limpiar_monto_int(r.get("Monto IVA Recuperable", 0)),
                                "monto_total": limpiar_monto_int(r.get("Monto Total", 0)),
                                "estado_rcv": pestana,
                            }
                            if doc["folio"] or doc["rut_emisor"]:
                                todos_documentos.append(doc)
                                docs_en_pestana += 1
                        log_cb(f"  -> {docs_en_pestana} facturas encontradas en '{pestana}'.")
                except Exception as e:
                    log_cb(f"Error procesando CSV de {pestana}: {e}")
                finally:
                    # Limpiar absolutamente todos los archivos temporales de scraping
                    for f_del in glob.glob(os.path.join(TEMP_RCV_DIR, "*")):
                        try:
                            os.remove(f_del)
                        except Exception:
                            pass

        # Ordenar por fecha desc
        def _sort_key_fecha(d):
            f_str = d.get("fecha_docto", "")
            try:
                partes = f_str.split(" ")[0].split("/")
                if len(partes) == 3:
                    return f"{partes[2]}-{partes[1].zfill(2)}-{partes[0].zfill(2)}"
            except Exception:
                pass
            return f_str

        todos_documentos.sort(key=_sort_key_fecha, reverse=True)

        conteo_33 = sum(1 for d in todos_documentos if str(d.get("tipo_doc_codigo")) == "33" or str(d.get("tipo_doc")) == "33")
        conteo_34 = sum(1 for d in todos_documentos if str(d.get("tipo_doc_codigo")) == "34" or str(d.get("tipo_doc")) == "34")
        conteo_61 = sum(1 for d in todos_documentos if str(d.get("tipo_doc_codigo")) == "61" or str(d.get("tipo_doc")) == "61")
        conteo_pendientes = sum(1 for d in todos_documentos if d.get("estado_rcv") == "Pendientes")
        conteo_reclamados = sum(1 for d in todos_documentos if d.get("estado_rcv") == "Reclamados")
        monto_total_sum = sum(d.get("monto_total", 0) for d in todos_documentos)
        monto_iva_sum = sum(d.get("monto_iva", 0) for d in todos_documentos)
        monto_neto_sum = sum(d.get("monto_neto", 0) for d in todos_documentos)

        totales = {
            "total_documentos": len(todos_documentos),
            "facturas_electronicas": conteo_33,
            "facturas_exentas": conteo_34,
            "notas_credito": conteo_61,
            "pendientes": conteo_pendientes,
            "reclamados": conteo_reclamados,
            "monto_neto_sum": monto_neto_sum,
            "monto_iva_sum": monto_iva_sum,
            "monto_total_sum": monto_total_sum,
        }

        log_cb(f"\n==========================================")
        log_cb(f"Consulta RCV Completada: {len(todos_documentos)} facturas cargadas.")
        log_cb(f"  - Facturas Electrónicas (33): {conteo_33}")
        log_cb(f"  - Facturas Exentas (34): {conteo_34}")
        log_cb(f"  - Pendientes: {conteo_pendientes}")
        log_cb(f"  - IVA Total Sumado: ${monto_iva_sum:,}".replace(",", "."))
        log_cb(f"  - Monto Total Sumado: ${monto_total_sum:,}".replace(",", "."))
        log_cb(f"==========================================\n")

        return {
            "exito": True,
            "mensaje": "Consulta completada exitosamente",
            "documentos": todos_documentos,
            "totales": totales,
            "mes": m,
            "anio": a,
            "empresa": RUT_EMPRESA,
        }

    except Exception as e:
        err_raw = str(e)
        if "element click intercepted" in err_raw.lower() or "modal-backdrop" in err_raw.lower():
            err_msg = (
                "El portal del SII mostró un aviso emergente o no hay facturas/movimientos "
                "registrados para este período en la empresa seleccionada."
            )
        elif "timeout" in err_raw.lower() or "timed out" in err_raw.lower():
            err_msg = "El servidor del SII tardó demasiado en responder. Por favor intenta nuevamente en unos momentos."
        elif "superado el máximo de sesiones" in err_raw.lower() or "01.01.203" in err_raw:
            err_msg = "Se ha superado el máximo de sesiones simultáneas en el SII. Espera unos minutos antes de reintentar."
        elif "nosuchelement" in err_raw.lower():
            err_msg = "No se encontraron los elementos esperados en el portal del SII para este período."
        else:
            err_lineas = [l.strip() for l in err_raw.split("\n") if l.strip() and not l.strip().startswith("Stacktrace:") and "chromedriver!" not in l and "GetHandleVerifier" not in l]
            err_msg = " ".join(err_lineas[:2]) if err_lineas else "Ocurrió un error inesperado al consultar el SII."
            if len(err_msg) > 200:
                err_msg = err_msg[:200] + "..."

        log_cb(f"[AVISO] {err_msg}")
        return {"exito": False, "mensaje": err_msg, "documentos": [], "totales": {}}


def generar_nombre_archivo_factura(doc_info, correlativo=None, contexto=""):
    """
    Genera el nombre de archivo según el formato requerido:
    Corr_numerocorrelativo_FE_numeroFactura, contextoFactura, NOMBREEMPRESA.pdf
    """
    folio = str(doc_info.get("folio", "")).strip()
    empresa = str(doc_info.get("razon_social", "")).upper().strip()
    empresa_limpia = re.sub(r'[\\/*?:"<>|]+', '', empresa).strip()
    if not empresa_limpia:
        empresa_limpia = str(doc_info.get("rut_emisor", doc_info.get("emisor", "PROVEEDOR"))).upper()

    tipo_cod = str(doc_info.get("tipo_doc_codigo", "")).strip()
    tipo_nombre = str(doc_info.get("tipo_doc", doc_info.get("tipo_doc_nombre", "Factura"))).strip()

    # Sigla de tipo de documento
    if tipo_cod == "33" or "electrónica" in tipo_nombre.lower() or tipo_nombre == "Factura":
        sigla = "FE"
    elif tipo_cod == "34" or "exenta" in tipo_nombre.lower():
        sigla = "FEE"
    elif tipo_cod == "61" or "crédito" in tipo_nombre.lower():
        sigla = "NC"
    elif tipo_cod == "56" or "débito" in tipo_nombre.lower():
        sigla = "ND"
    elif tipo_cod == "46":
        sigla = "FC"
    else:
        sigla = "FE"

    contexto_limpio = re.sub(r'[\\/*?:"<>|]+', '', str(contexto).strip()).strip()

    if correlativo is not None:
        if contexto_limpio:
            return f"Corr_{correlativo}_{sigla}_{folio}, {contexto_limpio}, {empresa_limpia}.pdf"
        else:
            return f"Corr_{correlativo}_{sigla}_{folio}, {empresa_limpia}.pdf"
    else:
        if contexto_limpio:
            return f"{tipo_nombre}_Folio_{folio}, {contexto_limpio}, {empresa_limpia}.pdf"
        else:
            return f"{tipo_nombre}_Folio_{folio}, {empresa_limpia}.pdf"


import ai_context


def descargar_pdf_individual(doc_info, mes_num=None, anio_num=None, correlativo=None, contexto="", usar_ia=False, api_key_gemini=None, api_key_openai=None, prompt_sistema=None, headless=True, log_cb=print):
    """
    Descarga el PDF de una factura individual de forma ultra-rápida.
    Si usar_ia es True, analiza la glosa del PDF para determinar automáticamente el contexto.
    """
    folio = str(doc_info.get("folio", "")).strip()
    if not folio:
        return False, "Folio no válido", None

    m = int(mes_num or _hoy.month)
    a = int(anio_num or _hoy.year)

    log_cb(f"Solicitando PDF para Folio #{folio} ({doc_info.get('razon_social', '')[:25]})...")

    # Asegurar catálogo MIPE indexado para este mes
    mapa = gestor_sesion.obtener_mapa_mipe(m, a, headless=headless, log_cb=log_cb)

    if folio not in mapa:
        # Intento 1: Búsqueda directa del folio en MIPE
        log_cb(f"Buscando Folio #{folio} directamente en el portal MIPE...")
        directo = gestor_sesion.buscar_folio_directo_mipe(
            folio, mes=m, anio=a, rut_emisor=doc_info.get("rut_emisor"), headless=headless, log_cb=log_cb
        )
        if directo:
            mapa[folio] = directo

    if folio not in mapa:
        # Intento 2: Refresco forzado de todo el catálogo
        mapa = gestor_sesion.obtener_mapa_mipe(m, a, headless=headless, forzar_recarga=True, log_cb=log_cb)

    if folio not in mapa:
        msg = f"El folio #{folio} no cuenta con archivo PDF disponible en el portal MIPE del SII (posiblemente emitida mediante sistema propio del emisor)."
        log_cb(f"[AVISO] {msg}")
        return False, msg, None

    info_mipe = mapa[folio]
    codigo = info_mipe["codigo"]
    s = gestor_sesion.session_req or requests.Session()

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    url_pdf = f"https://www1.sii.cl/cgi-bin/Portal001/mipeShowPdf.cgi?CODIGO={codigo}"

    try:
        resp = s.get(url_pdf, timeout=25)
        if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
            # Guardar temporalmente para análisis si se usa IA
            ctx_final = str(contexto).strip()
            if usar_ia:
                ruta_temp = os.path.join(DOWNLOAD_DIR, f"temp_analisis_{folio}.pdf")
                with open(ruta_temp, "wb") as f_tmp:
                    f_tmp.write(resp.content)
                ctx_ia = ai_context.obtener_contexto_factura(
                    ruta_temp,
                    doc_info=doc_info,
                    api_key_gemini=api_key_gemini,
                    api_key_openai=api_key_openai,
                    prompt_sistema=prompt_sistema,
                    log_cb=log_cb
                )
                try:
                    os.remove(ruta_temp)
                except Exception:
                    pass
                if ctx_ia:
                    ctx_final = ctx_ia

            nombre_archivo = generar_nombre_archivo_factura(doc_info, correlativo=correlativo, contexto=ctx_final)
            ruta_archivo = os.path.join(DOWNLOAD_DIR, nombre_archivo)

            with open(ruta_archivo, "wb") as f:
                f.write(resp.content)

            size_kb = len(resp.content) / 1024
            log_cb(f"   -> [OK] Guardado: {nombre_archivo} ({size_kb:.1f} KB)")
            return True, ruta_archivo, nombre_archivo
        else:
            msg = f"El portal del SII no entregó un PDF válido para el folio #{folio} (status {resp.status_code})"
            log_cb(f"   -> [AVISO] {msg}")
            return False, msg, None
    except Exception as e:
        msg = f"Error de conexión al descargar folio #{folio}: {e}"
        log_cb(f"   -> [AVISO] {msg}")
        return False, msg, None


def descargar_facturas_pdf_mes(mes_num=None, anio_num=None, folios_especificos=None, correlativo_inicial=None, contexto="", usar_ia=False, api_key_gemini=None, api_key_openai=None, prompt_sistema=None, headless=True, log_cb=print):
    """
    Descarga todos los PDFs del mes (o folios seleccionados) usando la sesión activa.
    Si usar_ia es True, genera el contexto automáticamente para cada factura desde su glosa.
    """
    m = int(mes_num or _hoy.month)
    a = int(anio_num or _hoy.year)
    nombre_mes = NOMBRES_MESES[m] if 1 <= m <= 12 else str(m)

    log_cb(f"\n==========================================")
    log_cb(f"Iniciando descarga de PDFs para {nombre_mes} {a} (IA Glosa: {usar_ia})...")
    log_cb(f"==========================================\n")

    mapa = gestor_sesion.obtener_mapa_mipe(m, a, headless=headless, log_cb=log_cb)

    if not mapa:
        msg = f"No se encontraron facturas con PDF en el portal MIPE del SII para {nombre_mes} {a}."
        log_cb(f"[AVISO] {msg}")
        return True, 0, msg, [], correlativo_inicial

    folios_set = set(str(f).strip() for f in folios_especificos) if folios_especificos else None
    items_a_descargar = [doc for f, doc in mapa.items() if (not folios_set or str(f) in folios_set)]

    if not items_a_descargar:
        msg = "Ninguno de los folios solicitados cuenta con PDF habilitado en el portal MIPE del SII."
        log_cb(f"[AVISO] {msg}")
        return True, 0, msg, [], correlativo_inicial

    log_cb(f"Descargando {len(items_a_descargar)} PDFs disponibles...")

    s = gestor_sesion.session_req or requests.Session()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    descargados_ok = 0
    archivos_guardados = []
    curr_corr = correlativo_inicial

    for idx, doc in enumerate(items_a_descargar, 1):
        url_pdf = f"https://www1.sii.cl/cgi-bin/Portal001/mipeShowPdf.cgi?CODIGO={doc['codigo']}"
        log_cb(f"[{idx}/{len(items_a_descargar)}] Descargando Folio #{doc['folio']} ({doc['razon_social'][:24]})...")

        try:
            resp = s.get(url_pdf, timeout=25)
            if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                ctx_final = str(contexto).strip()
                if usar_ia:
                    ruta_temp = os.path.join(DOWNLOAD_DIR, f"temp_analisis_{doc['folio']}.pdf")
                    with open(ruta_temp, "wb") as f_tmp:
                        f_tmp.write(resp.content)
                    ctx_ia = ai_context.obtener_contexto_factura(
                        ruta_temp,
                        doc_info=doc,
                        api_key_gemini=api_key_gemini,
                        api_key_openai=api_key_openai,
                        prompt_sistema=prompt_sistema,
                        log_cb=log_cb
                    )
                    try:
                        os.remove(ruta_temp)
                    except Exception:
                        pass
                    if ctx_ia:
                        ctx_final = ctx_ia

                nombre_archivo = generar_nombre_archivo_factura(doc, correlativo=curr_corr, contexto=ctx_final)
                ruta_archivo = os.path.join(DOWNLOAD_DIR, nombre_archivo)

                with open(ruta_archivo, "wb") as f:
                    f.write(resp.content)

                size_kb = len(resp.content) / 1024
                log_cb(f"   -> [OK] Guardado: {nombre_archivo} ({size_kb:.1f} KB)")
                descargados_ok += 1
                archivos_guardados.append(ruta_archivo)
                if curr_corr is not None:
                    curr_corr += 1
            else:
                log_cb(f"   -> [AVISO] Respuesta status {resp.status_code} para folio #{doc['folio']}")
        except Exception as err:
            log_cb(f"   -> [AVISO] Omitiendo folio #{doc['folio']}: {err}")

    log_cb(f"\n==========================================")
    log_cb(f"Descarga finalizada: {descargados_ok}/{len(items_a_descargar)} PDFs guardados en {DOWNLOAD_DIR}")
    log_cb(f"==========================================\n")
    return True, descargados_ok, "Descarga completada", archivos_guardados, curr_corr


# ==========================================================
# FUNCIONES WRAPPER / ADAPTADORAS REQUERIDAS POR APP.PY
# ==========================================================
def consultar_resumen_rcv_mes(mes_num=None, anio_num=None, pestanas=None, rut_empresa=None, headless=True, log_cb=print):
    """
    Función requerida por app.py. Consulta el RCV del mes y retorna la lista de documentos.
    Lanza una excepción si la consulta falla para que la interfaz muestre el diálogo de error.
    """
    res = consultar_facturas_rcv(
        mes_num=mes_num,
        anio_num=anio_num,
        pestanas=pestanas,
        rut_empresa=rut_empresa,
        headless=headless,
        log_cb=log_cb
    )
    if not res.get("exito"):
        raise Exception(res.get("mensaje", "Error desconocido al consultar el RCV"))
    return res.get("documentos", [])


def ejecutar_descarga_completa_rcv(mes_num=None, anio_num=None, pestanas=None, correlativo_inicial=None, contexto_usuario="", usar_ia=False, gemini_api_key=None, openai_api_key=None, prompt_sistema=None, headless=True, log_cb=print):
    """
    Función requerida por app.py para descarga masiva de facturas PDF del mes.
    Retorna (total_descargados, correlativo_final).
    """
    exito, total_desc, msg, archivos, corr_final = descargar_facturas_pdf_mes(
        mes_num=mes_num,
        anio_num=anio_num,
        correlativo_inicial=correlativo_inicial,
        contexto=contexto_usuario,
        usar_ia=usar_ia,
        api_key_gemini=gemini_api_key,
        api_key_openai=openai_api_key,
        prompt_sistema=prompt_sistema,
        headless=headless,
        log_cb=log_cb
    )
    if not exito:
        raise Exception(msg)
    return total_desc, (corr_final if corr_final is not None else correlativo_inicial)


def descargar_factura_individual(doc=None, correlativo_actual=None, contexto_usuario="", usar_ia=False, gemini_api_key=None, openai_api_key=None, prompt_sistema=None, headless=True, log_cb=print):
    """
    Función requerida por app.py para descarga de una factura individual en PDF.
    Retorna (ruta_archivo_guardado, nuevo_correlativo).
    """
    doc_info = doc or {}
    mes_num = _hoy.month
    anio_num = _hoy.year
    f_str = doc_info.get("fecha_docto", "")
    if f_str:
        try:
            partes = f_str.split(" ")[0].split("/")
            if len(partes) == 3:
                mes_num = int(partes[1])
                anio_num = int(partes[2])
            else:
                partes_iso = f_str.split(" ")[0].split("-")
                if len(partes_iso) == 3:
                    mes_num = int(partes_iso[1])
                    anio_num = int(partes_iso[0])
        except Exception:
            pass

    exito, ruta_o_msg, nombre_archivo = descargar_pdf_individual(
        doc_info=doc_info,
        mes_num=mes_num,
        anio_num=anio_num,
        correlativo=correlativo_actual,
        contexto=contexto_usuario,
        usar_ia=usar_ia,
        api_key_gemini=gemini_api_key,
        api_key_openai=openai_api_key,
        prompt_sistema=prompt_sistema,
        headless=headless,
        log_cb=log_cb
    )
    if not exito:
        raise Exception(ruta_o_msg)

    corr_final = (correlativo_actual + 1) if (correlativo_actual is not None) else correlativo_actual
    return ruta_o_msg, corr_final


def cerrar_sesion_global(log_cb=print):
    """Cierra la sesión persistente en el SII y finaliza el navegador."""
    gestor_sesion.cerrar(log_cb=log_cb)


if __name__ == "__main__":
    res = consultar_facturas_rcv(mes_num=8, anio_num=2026, headless=True)
    print("Documentos obtenidos:", len(res["documentos"]))
    cerrar_sesion_global()

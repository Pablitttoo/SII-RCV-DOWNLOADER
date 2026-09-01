"""
Módulo para interacción y descarga automatizada de Boletas de Honorarios Electrónicas (BHE) desde el SII.
Permite consultar boletas recibidas y emitidas autenticándose directamente con las credenciales
de la empresa objetivo (RUT y Clave Tributaria de la Empresa).
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
import glob
from datetime import datetime
from dotenv import load_dotenv
import ai_context

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
)
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

from ..utils import obtener_ruta_base, cargar_variables_entorno

DIRECTORIO_ACTUAL = obtener_ruta_base()
cargar_variables_entorno()

# ---------- Configuración de URLs Oficiales del SII ----------
URL_LOGIN_BASE = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"
URL_LOGIN_FALLBACK = "https://zeus.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"
URL_BHE_RECIBIDAS_MENU = "https://loa.sii.cl/cgi_IMT/TMBCOC_MenuConsultasContribRec.cgi"
URL_BHE_EMITIDAS_MENU  = "https://loa.sii.cl/cgi_IMT/TMBCOC_MenuConsultasContrib.cgi"

NOMBRES_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

_hoy = datetime.now()


def limpiar_monto_int(val_str):
    """Convierte un string de monto chileno ($1.234.567 o 1234567) a entero."""
    if not val_str:
        return 0
    if isinstance(val_str, (int, float)):
        return int(val_str)
    limpio = re.sub(r"[^\d\-]", "", str(val_str))
    try:
        return int(limpio) if limpio else 0
    except Exception:
        return 0


def formatear_monto_clp(val):
    """Formatea un número a string con formato moneda chilena ($ 1.234.567)."""
    val_int = limpiar_monto_int(val)
    return f"${val_int:,}".replace(",", ".")


def crear_driver_honorarios(download_dir=None, headless=True):
    """Crea un WebDriver optimizado para consultas de honorarios con soporte de impresión a PDF."""
    dir_descarga = download_dir or os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        os.makedirs(dir_descarga, exist_ok=True)
    except (FileNotFoundError, OSError, Exception):
        dir_descarga = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(dir_descarga, exist_ok=True)
        except Exception:
            pass

    options = Options()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-proxy-server")
    options.add_argument("--dns-prefetch-disable")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "download.default_directory": dir_descarga,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
        "printing.print_to_pdf": True
    }
    options.add_experimental_option("prefs", prefs)

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
            {"behavior": "allow", "downloadPath": dir_descarga}
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

    if not headless:
        driver.maximize_window()
    return driver


def generar_nombre_archivo_honorarios(boleta, correlativo=None, glosa="", mes_num=None):
    """
    Genera el nombre de archivo con el formato oficial estándar:
    Formato: {correlativo}_{mes:02d} Bol.Hon. #{folio}, {glosa} - {emisor}.pdf
    Ejemplo: 300_07 Bol.Hon. #100, Filmación Contenido MP - Alejandro Maldonado.pdf
    """
    folio = str(boleta.get("folio", "0")).strip()
    
    # 1. Mes a 2 dígitos (ej: 07)
    m = mes_num if mes_num is not None else boleta.get("mes", datetime.now().month)
    try:
        m_int = int(m)
    except Exception:
        m_int = datetime.now().month
    mes_str = f"{m_int:02d}"

    # 2. Correlativo (ej: 300)
    corr_str = str(correlativo).strip() if correlativo is not None and str(correlativo).strip() else ""

    # 3. Emisor limpio con formato natural (Title Case)
    emisor_raw = boleta.get("razon_social") or boleta.get("nombre_emisor") or "Emisor"
    emisor_limpio = re.sub(r'[\\/*?:"<>|]+', ' ', str(emisor_raw)).strip()
    emisor_formateado = ai_context.formatear_glosa_natural(emisor_limpio) if emisor_limpio else "Emisor"

    # 4. Glosa limpia (garantizando que nunca duplique el nombre del emisor)
    glosa_limpia = ai_context.limpiar_glosa_sin_emisor(glosa, doc_info=boleta)

    # 5. Prefijo correlativo y mes
    if corr_str:
        prefijo = f"{corr_str}_{mes_str}"
    else:
        prefijo = f"{mes_str}"

    # 6. Ensamblado final
    if glosa_limpia:
        nombre = f"{prefijo} Bol.Hon. #{folio}, {glosa_limpia} - {emisor_formateado}.pdf"
    else:
        nombre = f"{prefijo} Bol.Hon. #{folio} - {emisor_formateado}.pdf"

    return nombre


def es_pagina_login_o_expirada(driver):
    """
    Detecta si el navegador se encuentra en la pantalla de login del SII
    o si la sesión ha expirado por inactividad.
    """
    if not driver:
        return True
    try:
        url_actual = (driver.current_url or "").lower()
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

        if driver.find_elements(By.ID, "rutcntr") or driver.find_elements(By.ID, "bt_ingresar"):
            return True
        if driver.find_elements(By.ID, "clave") and driver.find_elements(By.NAME, "RUTCtr"):
            return True

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


class GestorSesionHonorarios:
    """
    Gestor singleton de sesión persistente con las credenciales de la empresa
    para consulta y descarga de Boletas de Honorarios en el SII.
    """
    _instancia = None

    @classmethod
    def get_instancia(cls):
        if cls._instancia is None:
            cls._instancia = cls()
        return cls._instancia

    def __init__(self):
        self.driver = None
        self.wait = None
        self.rut_actual = None
        self.clave_actual = None
        self.lock = threading.RLock()
        self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")

    def esta_activo(self):
        if self.driver is None:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def set_download_dir(self, nueva_ruta):
        if nueva_ruta:
            try:
                ruta_abs = os.path.abspath(nueva_ruta)
                os.makedirs(ruta_abs, exist_ok=True)
                self.download_dir = ruta_abs
            except (FileNotFoundError, OSError, Exception):
                self.download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                try:
                    os.makedirs(self.download_dir, exist_ok=True)
                except Exception:
                    pass
            if self.driver:
                try:
                    self.driver.execute_cdp_cmd(
                        "Page.setDownloadBehavior",
                        {"behavior": "allow", "downloadPath": self.download_dir}
                    )
                except Exception:
                    pass

    def cerrar_sesion(self, log_cb=print):
        with self.lock:
            if self.driver:
                try:
                    log_cb("Cerrando sesión de Honorarios en el SII...")
                    self.driver.get("https://zeusr.sii.cl/cgi_AUT2000/autLogout.cgi")
                    time.sleep(1.5)
                    self.driver.quit()
                except Exception:
                    pass
                finally:
                    self.driver = None
                    self.wait = None
                    self.rut_actual = None
                    self.clave_actual = None
                    log_cb("Sesión de Honorarios cerrada.")

    def asegurar_sesion(self, rut_empresa, clave_empresa, tipo='recibidas', headless=True, log_cb=print):
        """
        Inicia sesión en el SII con las credenciales específicas de la empresa
        o reutiliza la sesión si ya está activa con el mismo RUT, validando que no haya expirado.
        """
        rut_limpio = str(rut_empresa or "").strip()
        clave_limpia = str(clave_empresa or "").strip()

        if not rut_limpio or not clave_limpia:
            raise ValueError("Debes ingresar el RUT y la Clave de la empresa para consultar Boletas de Honorarios.")

        target_menu = URL_BHE_RECIBIDAS_MENU if str(tipo).strip().lower() == 'recibidas' else URL_BHE_EMITIDAS_MENU

        with self.lock:
            # Si ya tenemos sesión abierta con el mismo RUT, verificamos que no haya expirado
            if self.esta_activo() and self.rut_actual == rut_limpio:
                try:
                    self.driver.get(target_menu)
                    time.sleep(1.5)
                    if not es_pagina_login_o_expirada(self.driver):
                        log_cb(f"✓ Reutilizando sesión activa de Honorarios para RUT {rut_limpio}...")
                        return self.driver, self.wait
                    else:
                        log_cb(f"⚠️ Sesión de Honorarios caducada para RUT {rut_limpio}. Reautenticando...")
                except Exception:
                    pass

            # Si había otra sesión con otro RUT o expirada, cerrarla primero
            if self.esta_activo():
                try:
                    self.driver.get("https://zeusr.sii.cl/cgi_AUT2000/autLogout.cgi")
                    time.sleep(2.5)
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

            log_cb(f"Iniciando sesión en el SII con credenciales de empresa (RUT: {rut_limpio})...")
            self.driver = crear_driver_honorarios(download_dir=self.download_dir, headless=headless)
            self.wait = WebDriverWait(self.driver, 25)

            # Intentar cargar URL de autenticación con redirección directa al menú BHE
            urls_login = [
                f"https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?{target_menu}",
                f"https://zeus.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html?{target_menu}",
                URL_LOGIN_BASE,
                URL_LOGIN_FALLBACK
            ]
            cargada = False
            for u in urls_login:
                try:
                    self.driver.get(u)
                    time.sleep(1.0)
                    cargada = True
                    break
                except Exception as ex_u:
                    log_cb(f"Reintentando conexión con servidor de autenticación ({u})...")
                    time.sleep(1.5)

            if not cargada:
                raise RuntimeError("No fue posible conectar con los servidores del SII (error de red o DNS temporal). Verifica tu conexión a internet.")

            try:
                campo_rut = self.wait.until(EC.element_to_be_clickable((By.ID, "rutcntr")))
                campo_rut.clear()
                campo_rut.send_keys(rut_limpio)

                campo_clave = self.driver.find_element(By.ID, "clave")
                campo_clave.clear()
                campo_clave.send_keys(clave_limpia)

                boton = self.driver.find_element(By.ID, "bt_ingresar")
                boton.click()

                log_cb("Validando credenciales en el SII...")
                time.sleep(2.5)

                try:
                    self.wait.until(lambda d: "IngresoRutClave" not in d.current_url)
                except TimeoutException:
                    raise RuntimeError("Tiempo de espera agotado o credenciales inválidas al autenticar en el SII.")

                # Verificar si hay mensaje de error en pantalla
                body_text = ""
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                except Exception:
                    pass

                if "superado el máximo de sesiones" in body_text or "01.01.203" in body_text:
                    raise RuntimeError("El SII indica que se ha superado el máximo de sesiones simultáneas. Espera unos minutos.")
                if "clave o rut incorrecto" in body_text or "no coinciden" in body_text:
                    raise RuntimeError("El RUT o la Clave ingresada para la empresa son incorrectos.")

                self.rut_actual = rut_limpio
                self.clave_actual = clave_limpia
                log_cb(f"¡Sesión de Honorarios iniciada con éxito para RUT {rut_limpio}!")
                return self.driver, self.wait

            except Exception as e:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                self.wait = None
                raise e

    def consultar_boletas(self, rut_empresa, clave_empresa, mes_num, anio_num, tipo='recibidas', headless=True, log_cb=print):
        """
        Navega en el portal de honorarios del SII, consulta el periodo mensual especificado
        y retorna la lista de boletas con su información estructurada.
        """
        driver, wait = self.asegurar_sesion(rut_empresa, clave_empresa, tipo=tipo, headless=headless, log_cb=log_cb)

        m = int(mes_num)
        a = int(anio_num)
        mes_val = f"{m:02d}"
        anio_val = str(a)
        nombre_mes = NOMBRES_MESES[m] if 1 <= m <= 12 else str(m)

        log_cb(f"Accediendo a Boletas de Honorarios {tipo.capitalize()} - Periodo: {nombre_mes} {anio_val}...")

        target_menu = URL_BHE_RECIBIDAS_MENU if tipo == 'recibidas' else URL_BHE_EMITIDAS_MENU
        menu_cargado = False
        for intento in range(3):
            try:
                driver.get(target_menu)
                time.sleep(2.0)
                menu_cargado = True
                break
            except Exception:
                log_cb(f"Reintentando acceso al menú de honorarios ({intento + 1}/3)...")
                time.sleep(2.0)

        if not menu_cargado:
            driver.get(target_menu)
        time.sleep(2.5)

        # Configurar formulario mensual
        try:
            # 1. Seleccionar Mes
            sel_mes_elem = wait.until(EC.presence_of_element_located((By.NAME, "cbmesinformemensual")))
            sel_mes_obj = Select(sel_mes_elem)
            opciones_mes = [op.get_attribute("value") for op in sel_mes_obj.options if op.get_attribute("value")]
            if mes_val in opciones_mes:
                sel_mes_obj.select_by_value(mes_val)
            elif str(m) in opciones_mes:
                sel_mes_obj.select_by_value(str(m))
            else:
                try:
                    sel_mes_obj.select_by_index(m)
                except Exception:
                    try:
                        sel_mes_obj.select_by_visible_text(nombre_mes)
                    except Exception:
                        pass
            log_cb(f"Mes configurado: {nombre_mes}")

            # 2. Seleccionar Año
            sel_anio_elem = wait.until(EC.presence_of_element_located((By.NAME, "cbanoinformemensual")))
            sel_anio_obj = Select(sel_anio_elem)
            opciones_anio = [op.get_attribute("value") for op in sel_anio_obj.options if op.get_attribute("value")]
            if anio_val in opciones_anio:
                sel_anio_obj.select_by_value(anio_val)
            elif opciones_anio:
                sel_anio_obj.select_by_value(opciones_anio[-1])
            log_cb(f"Año configurado: {anio_val}")

            # 3. Enviar consulta mensual mediante la función nativa del SII o clic en Consultar
            fn_js = "presionaBoton('validar_mensual_rec');" if str(tipo).strip().lower() == 'recibidas' else "presionaBoton('validar_mensual_emi');"
            log_cb("Consultando datos en servidor de honorarios del SII...")
            enviado = False
            try:
                driver.execute_script(fn_js)
                enviado = True
            except Exception:
                pass

            if not enviado:
                btns = driver.find_elements(By.XPATH, "//input[@type='button' and (@value='Consultar' or @value='CONSULTAR')] | //input[@type='submit']")
                if btns:
                    btn_target = btns[1] if len(btns) > 1 else btns[0]
                    driver.execute_script("arguments[0].click();", btn_target)

            time.sleep(2.5)

            # Manejar posibles alertas emergentes del SII (ej: 'No existen boletas...')
            try:
                alert = driver.switch_to.alert
                al_text = alert.text
                alert.accept()
                log_cb(f"Aviso del SII: {al_text}")
                if "no existen" in al_text.lower() or "sin datos" in al_text.lower():
                    return []
            except Exception:
                pass

        except Exception as e:
            log_cb(f"Aviso al configurar formulario de honorarios: {e}")
            try:
                btns = driver.find_elements(By.XPATH, "//input[@type='button' and (@value='Consultar' or @value='CONSULTAR')]")
                if btns:
                    btn_target = btns[1] if len(btns) > 1 else btns[0]
                    driver.execute_script("arguments[0].click();", btn_target)
                    time.sleep(2.5)
            except Exception:
                pass

        # Parsear tabla de resultados del informe mensual
        boletas = []
        try:
            time.sleep(2.0)
            tablas = driver.find_elements(By.XPATH, "//table")
            if not tablas:
                log_cb(f"No se encontraron tablas de honorarios para {nombre_mes} {anio_val}.")
                return []

            tabla_datos = None
            for t in tablas:
                txt = t.text.upper()
                if "BRUTOS" in txt or "RETENIDO" in txt or "PAGADO" in txt or "ESTADO" in txt:
                    tabla_datos = t
                    break

            if not tabla_datos:
                body_text = driver.find_element(By.TAG_NAME, "body").text.upper()
                if "SIN DATOS" in body_text or "NO EXISTEN BOLETAS" in body_text:
                    log_cb(f"ℹ️ El SII informa que no hay Boletas de Honorarios en {nombre_mes} {anio_val} (Sin Datos).")
                    return []
                tabla_datos = tablas[-1]

            filas = tabla_datos.find_elements(By.XPATH, ".//tr")
            
            for idx_fila, f in enumerate(filas):
                celdas = f.find_elements(By.XPATH, ".//td")
                if len(celdas) < 6:
                    continue

                textos_celdas = [c.text.strip() for c in celdas]
                fila_str = " ".join(textos_celdas).upper()

                # Ignorar encabezados y totales
                if "SIN DATOS" in fila_str or "TOTALES" in fila_str or ("RUT" in fila_str and "ESTADO" in fila_str):
                    continue

                # Extraer enlace o llamada JS para ver el PDF
                link_elem = f.find_elements(By.TAG_NAME, "a")
                link_pdf = ""
                onclick_code = ""
                if link_elem:
                    link_pdf = link_elem[0].get_attribute("href") or ""
                    onclick_code = link_elem[0].get_attribute("onclick") or ""
                else:
                    inputs = f.find_elements(By.XPATH, ".//input[@type='button' or @type='image' or @type='submit']")
                    if inputs:
                        onclick_code = inputs[0].get_attribute("onclick") or ""
                        link_pdf = inputs[0].get_attribute("src") or ""

                folio = ""
                estado = "Vigente"
                fecha = ""
                rut_emisor = ""
                nombre_emisor = ""
                monto_bruto = 0
                monto_retencion = 0
                monto_liquido = 0

                # Asignación precisa según la estructura oficial del SII
                if len(celdas) >= 10:
                    folio = textos_celdas[1]
                    estado = textos_celdas[2]
                    fecha = textos_celdas[3]
                    rut_emisor = textos_celdas[4]
                    nombre_emisor = textos_celdas[5]
                    monto_bruto = limpiar_monto_int(textos_celdas[7])
                    monto_retencion = limpiar_monto_int(textos_celdas[8])
                    monto_liquido = limpiar_monto_int(textos_celdas[9])
                else:
                    for t in textos_celdas:
                        if re.match(r"^\d{1,2}\.?\d{3}\.?\d{3}\-[\dkK]$", t):
                            rut_emisor = t
                        elif re.match(r"^\d{2}/\d{2}/\d{4}$", t):
                            fecha = t
                        elif t.upper() in ["VIGENTE", "ANULADA", "OBSERVADA"]:
                            estado = t.capitalize()
                        elif t.isdigit() and len(t) <= 8 and not folio:
                            folio = t

                    montos = [limpiar_monto_int(t) for t in textos_celdas if limpiar_monto_int(t) > 0 and str(limpiar_monto_int(t)) != folio]
                    if len(montos) >= 3:
                        monto_bruto = montos[0]
                        monto_retencion = montos[1]
                        monto_liquido = montos[2]

                if not folio:
                    continue

                emisor_final = nombre_emisor.strip() or "Emisor Honorarios"
                boleta_obj = {
                    "folio": str(folio),
                    "fecha": fecha or f"01/{mes_val}/{anio_val}",
                    "rut": rut_emisor,
                    "rut_emisor": rut_emisor,
                    "emisor": emisor_final,
                    "razon_social": emisor_final,
                    "glosa": "Servicios Profesionales / Honorarios",
                    "monto_bruto": monto_bruto,
                    "retencion": monto_retencion,
                    "monto_retencion": monto_retencion,
                    "monto_liquido": monto_liquido,
                    "estado": estado,
                    "link_pdf": link_pdf,
                    "onclick_code": onclick_code,
                    "tipo": tipo,
                    "mes": m,
                    "anio": a,
                    "pdf_descargado": False,
                    "ruta_pdf": "",
                    "pdf_ruta": ""
                }
                boletas.append(boleta_obj)

            log_cb(f"✓ Consulta completada: Se encontraron {len(boletas)} Boletas de Honorarios para {nombre_mes} {anio_val}.")
            return boletas

        except Exception as e:
            log_cb(f"Error extrayendo datos de boletas de honorarios: {e}")
            return boletas

    def descargar_boleta_pdf(self, boleta, download_dir=None, correlativo=None, contexto_usuario="",
                            usar_ia=False, gemini_api_key="", openai_api_key="", prompt_sistema=None,
                            mes_num=None, log_cb=print):
        """
        Descarga o genera el archivo PDF oficial de una boleta de honorarios específica
        utilizando impresión de alta fidelidad CDP de Chrome, extrayendo la glosa con IA
        o asignando la glosa manual del usuario con nomenclatura estándar.
        """
        dir_dest = download_dir or self.download_dir
        os.makedirs(dir_dest, exist_ok=True)

        folio = str(boleta.get("folio", "0")).strip()
        emisor = re.sub(r'[\\/*?:"<>|]', "", str(boleta.get("razon_social", "EMPRESA"))).strip()

        log_cb(f"Generando PDF de Boleta de Honorarios #{folio} ({emisor})...")

        with self.lock:
            if not self.esta_activo():
                raise RuntimeError("No hay sesión activa para descargar el PDF.")

            main_window = self.driver.current_window_handle
            table_url = self.driver.current_url
            opened_new_window = False
            link_pdf = boleta.get("link_pdf", "")
            onclick_code = boleta.get("onclick_code", "")

            # 1. Asegurar que no hay ventanas emergentes huérfanas antes de empezar
            try:
                for h in list(self.driver.window_handles):
                    if h != main_window:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                self.driver.switch_to.window(main_window)
            except Exception:
                pass

            # 2. Localizar y accionar la apertura de la boleta
            encontrado = False
            try:
                candidatos = self.driver.find_elements(
                    By.XPATH,
                    f"//tr[td[normalize-space()='{folio}' or contains(text(), '{folio}')]]//a | "
                    f"//tr[td[normalize-space()='{folio}' or contains(text(), '{folio}')]]//input | "
                    f"//a[contains(@href, '{folio}') or contains(@onclick, '{folio}')]"
                )
                if candidatos:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", candidatos[0])
                    encontrado = True
            except Exception as ex_elem:
                log_cb(f"Aviso buscando elemento para folio #{folio}: {ex_elem}")

            if not encontrado:
                js_to_run = onclick_code or link_pdf
                if js_to_run:
                    if js_to_run.startswith("javascript:"):
                        js_to_run = js_to_run.replace("javascript:", "").strip()
                    try:
                        self.driver.execute_script(js_to_run)
                        encontrado = True
                    except Exception as ex_js:
                        log_cb(f"Aviso ejecutando JS #{folio}: {ex_js}")

            # 3. Esperar de forma reactiva a que se abra la ventana o cambie la página
            ventana_boleta = None
            for _ in range(25): # hasta 12.5 segundos
                handles = self.driver.window_handles
                if len(handles) > 1:
                    for h in handles:
                        if h != main_window:
                            try:
                                self.driver.switch_to.window(h)
                                b_text = self.driver.find_element(By.TAG_NAME, "body").text.upper()
                                url_now = self.driver.current_url.lower()
                                if "verboleta" in url_now or "boleta" in b_text or "atención" in b_text or "honorarios" in b_text:
                                    ventana_boleta = h
                                    opened_new_window = True
                                    break
                            except Exception:
                                pass
                    if opened_new_window:
                        break
                else:
                    self.driver.switch_to.window(main_window)
                    try:
                        b_text = self.driver.find_element(By.TAG_NAME, "body").text.upper()
                        url_now = self.driver.current_url.lower()
                        if ("verboleta" in url_now or "atención" in b_text) and "informe mensual" not in b_text:
                            ventana_boleta = main_window
                            break
                    except Exception:
                        pass
                time.sleep(0.5)

            # 4. Limpieza de botones de interfaz (Volver, Imprimir, Cerrar) en la vista de la boleta
            try:
                self.driver.execute_script("""
                    document.querySelectorAll('input[type="button"], input[type="submit"], button, .no-print, a[href*="javascript:"]').forEach(function(el) {
                        var val = (el.value || el.innerText || '').toLowerCase();
                        if (val.includes('volver') || val.includes('imprimir') || val.includes('cerrar') || val.includes('guardar')) {
                            el.style.display = 'none';
                        }
                    });
                    document.body.style.backgroundColor = '#ffffff';
                    document.body.style.margin = '0 auto';
                    document.body.style.padding = '10px';
                """)
                time.sleep(1.0)
            except Exception:
                pass

            # 5. Capturar PDF de alta fidelidad vía CDP
            try:
                pdf_data = self.driver.execute_cdp_cmd(
                    "Page.printToPDF",
                    {
                        "printBackground": True,
                        "paperWidth": 8.27,  # A4
                        "paperHeight": 11.69, # A4
                        "marginTop": 0.25,
                        "marginBottom": 0.25,
                        "marginLeft": 0.25,
                        "marginRight": 0.25,
                        "scale": 1.0,
                        "preferCSSPageSize": True
                    }
                )
                pdf_bytes = base64.b64decode(pdf_data["data"])
            finally:
                # 6. Volver a la tabla principal
                if opened_new_window:
                    try:
                        self.driver.close()
                    except Exception:
                        pass
                    try:
                        self.driver.switch_to.window(main_window)
                    except Exception:
                        if self.driver.window_handles:
                            self.driver.switch_to.window(self.driver.window_handles[0])
                else:
                    if self.driver.current_url != table_url:
                        try:
                            self.driver.back()
                            time.sleep(2.0)
                        except Exception:
                            try:
                                self.driver.get(table_url)
                                time.sleep(2.0)
                            except Exception:
                                pass

        # 5. Limpieza preventiva de posibles archivos .cgi descargados automáticamente por Chrome
        for ext_pattern in ["*.cgi", "*.CGI"]:
            for f_cgi in glob.glob(os.path.join(dir_dest, ext_pattern)):
                try:
                    os.remove(f_cgi)
                except Exception:
                    pass
            for f_cgi in glob.glob(os.path.join(self.download_dir, ext_pattern)):
                try:
                    os.remove(f_cgi)
                except Exception:
                    pass

        # 6. Determinar Glosa (IA o Manual)
        glosa_final = str(contexto_usuario).strip()
        if usar_ia:
            ruta_temp = os.path.join(dir_dest, f"temp_bhe_ia_{folio}.pdf")
            try:
                with open(ruta_temp, "wb") as f_tmp:
                    f_tmp.write(pdf_bytes)
                glosa_ia = ai_context.obtener_contexto_factura(
                    ruta_pdf=ruta_temp,
                    doc_info=boleta,
                    api_key_gemini=gemini_api_key,
                    api_key_openai=openai_api_key,
                    prompt_sistema=prompt_sistema,
                    log_cb=log_cb
                )
                if glosa_ia and glosa_ia.strip():
                    glosa_final = glosa_ia.strip()
            except Exception as e_ia:
                log_cb(f"Aviso IA Honorarios: {e_ia}")
            finally:
                if os.path.exists(ruta_temp):
                    try:
                        os.remove(ruta_temp)
                    except Exception:
                        pass

        # Si no hay glosa manual ni IA generó una, usar extracción heurística del PDF
        if not glosa_final:
            ruta_temp = os.path.join(dir_dest, f"temp_bhe_loc_{folio}.pdf")
            try:
                with open(ruta_temp, "wb") as f_tmp:
                    f_tmp.write(pdf_bytes)
                texto_pdf = ai_context.extraer_texto_pdf(ruta_temp)
                glosa_local = ai_context.extraer_glosa_heuristica(texto_pdf, doc_info=boleta)
                if glosa_local:
                    glosa_final = glosa_local
            except Exception:
                pass
            finally:
                if os.path.exists(ruta_temp):
                    try:
                        os.remove(ruta_temp)
                    except Exception:
                        pass

        # 7. Construir nombre oficial
        nombre_archivo = generar_nombre_archivo_honorarios(
            boleta=boleta,
            correlativo=correlativo,
            glosa=glosa_final,
            mes_num=mes_num
        )

        ruta_final = os.path.join(dir_dest, nombre_archivo)
        with open(ruta_final, "wb") as f:
            f.write(pdf_bytes)

        boleta["glosa"] = glosa_final or boleta.get("glosa", "Honorarios")
        boleta["pdf_descargado"] = True
        boleta["ruta_pdf"] = ruta_final
        boleta["pdf_status"] = "✓ Descargado"

        log_cb(f"✓ Boleta #{folio} guardada exitosamente: {nombre_archivo}")
        return ruta_final


# Instancia global exportada
gestor_honorarios = GestorSesionHonorarios.get_instancia()


def set_download_dir(nueva_ruta):
    """Configura la carpeta de descarga para Boletas de Honorarios."""
    gestor_honorarios.set_download_dir(nueva_ruta)


def consultar_resumen_honorarios_mes(rut_empresa, clave_empresa, mes_num, anio_num, tipo='recibidas', headless=True, log_cb=print):
    """
    Función de alto nivel para consultar boletas de honorarios de un mes específico.
    """
    return gestor_honorarios.consultar_boletas(
        rut_empresa=rut_empresa,
        clave_empresa=clave_empresa,
        mes_num=mes_num,
        anio_num=anio_num,
        tipo=tipo,
        headless=headless,
        log_cb=log_cb
    )


def descargar_boleta_individual(boleta, rut_empresa, clave_empresa, tipo='recibidas', correlativo_actual=None,
                                contexto_usuario="", usar_ia=False, gemini_api_key="", openai_api_key="",
                                headless=True, log_cb=print):
    """
    Descarga una boleta de honorarios individual y devuelve (ruta_archivo_pdf, nuevo_correlativo).
    """
    gestor_honorarios.asegurar_sesion(rut_empresa, clave_empresa, tipo=tipo, headless=headless, log_cb=log_cb)

    corr_num = None
    if correlativo_actual is not None:
        try:
            corr_num = int(correlativo_actual)
        except Exception:
            corr_num = None

    ruta = gestor_honorarios.descargar_boleta_pdf(
        boleta=boleta,
        download_dir=gestor_honorarios.download_dir,
        correlativo=corr_num,
        contexto_usuario=contexto_usuario,
        usar_ia=usar_ia,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        mes_num=boleta.get("mes"),
        log_cb=log_cb
    )
    nuevo_correlativo = corr_num + 1 if corr_num is not None else correlativo_actual
    return ruta, nuevo_correlativo


def ejecutar_descarga_completa_honorarios(rut_empresa, clave_empresa, mes_num, anio_num, tipo='recibidas',
                                          folios_especificos=None, correlativo_inicial=None, contexto_usuario="",
                                          usar_ia=False, gemini_api_key="", openai_api_key="",
                                          headless=True, log_cb=print):
    """
    Descarga en lote todas las boletas de honorarios del mes o las especificadas en folios_especificos.
    Retorna (total_descargadas, correlativo_final).
    """
    boletas = gestor_honorarios.consultar_boletas(
        rut_empresa=rut_empresa,
        clave_empresa=clave_empresa,
        mes_num=mes_num,
        anio_num=anio_num,
        tipo=tipo,
        headless=headless,
        log_cb=log_cb
    )

    if not boletas:
        log_cb(f"No hay boletas de honorarios para descargar en {mes_num}/{anio_num}.")
        return 0, correlativo_inicial

    if folios_especificos:
        folios_str = [str(f).strip() for f in folios_especificos]
        boletas_a_descargar = [b for b in boletas if str(b.get("folio", "")).strip() in folios_str]
    else:
        boletas_a_descargar = boletas

    total_descargadas = 0
    corr_actual = None
    if correlativo_inicial is not None:
        try:
            corr_actual = int(correlativo_inicial)
        except Exception:
            corr_actual = None

    log_cb(f"Iniciando descarga de {len(boletas_a_descargar)} boletas de honorarios...")

    for idx, b in enumerate(boletas_a_descargar, start=1):
        folio = b.get("folio", "0")
        log_cb(f"[{idx}/{len(boletas_a_descargar)}] Procesando Boleta #{folio}...")
        try:
            gestor_honorarios.descargar_boleta_pdf(
                boleta=b,
                download_dir=gestor_honorarios.download_dir,
                correlativo=corr_actual,
                contexto_usuario=contexto_usuario,
                usar_ia=usar_ia,
                gemini_api_key=gemini_api_key,
                openai_api_key=openai_api_key,
                mes_num=mes_num,
                log_cb=log_cb
            )
            total_descargadas += 1
            if corr_actual is not None:
                corr_actual += 1
        except Exception as e:
            log_cb(f"❌ Error descargando Boleta #{folio}: {e}")

    log_cb(f"✓ Descarga finalizada: {total_descargadas} boletas guardadas exitosamente.")
    return total_descargadas, corr_actual


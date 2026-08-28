"""
Módulo de Auto-Actualización automática desde GitHub Releases.
Verifica si existe una versión más reciente, solicita confirmación al usuario
y actualiza el archivo ejecutable en segundo plano sin intervención manual.
"""

import os
import sys
import time
import subprocess
import tempfile
import threading
import webbrowser
import requests
from tkinter import messagebox, ttk
import tkinter as tk

from .. import __version__ as VERSION_LOCAL

REPO_GITHUB = "Pablitttoo/SII-RCV-DOWNLOADER"
GITHUB_API_LATEST = f"https://api.github.com/repos/{REPO_GITHUB}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{REPO_GITHUB}/releases"


def limpiar_version_str(version_str):
    """Extrae una tupla de enteros (major, minor, patch) de un string como 'v2.1.0' o '2.1.0'."""
    if not version_str:
        return (0, 0, 0)
    v_clean = str(version_str).strip().lstrip("vV")
    partes = []
    for p in v_clean.split("."):
        num_str = "".join(ch for ch in p if ch.isdigit())
        if num_str:
            partes.append(int(num_str))
        else:
            partes.append(0)
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes[:3])


def es_version_mas_reciente(v_local_str, v_remota_str):
    """Retorna True si la versión remota es estrictamente mayor que la versión local."""
    try:
        t_local = limpiar_version_str(v_local_str)
        t_remota = limpiar_version_str(v_remota_str)
        return t_remota > t_local
    except Exception:
        return False


def consultar_version_github(repo=REPO_GITHUB, timeout=7):
    """
    Consulta la API de GitHub para obtener información del último release publicado.
    Retorna un diccionario con: { 'tag': 'v2.1.1', 'nombre': '...', 'body': '...', 'url_exe': '...', 'html_url': '...' } o None si falla.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SII-GestorFacturas-AutoUpdater"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            tag = data.get("tag_name", "").strip()
            nombre = data.get("name", tag)
            body = data.get("body", "")
            html_url = data.get("html_url", GITHUB_RELEASES_URL)
            
            # Buscar el archivo .exe en los assets
            url_exe = None
            for asset in data.get("assets", []):
                nombre_asset = asset.get("name", "").lower()
                if nombre_asset.endswith(".exe") or "gestorfacturas" in nombre_asset:
                    url_exe = asset.get("browser_download_url")
                    break
            
            return {
                "tag": tag,
                "nombre": nombre,
                "body": body,
                "url_exe": url_exe,
                "html_url": html_url
            }
    except Exception:
        pass
    return None


def aplicar_actualizacion_windows(url_descarga, ventana_padre=None, log_cb=print):
    """
    Descarga el nuevo ejecutable, lanza un script PowerShell de reemplazo y reinicia la app.
    """
    es_frozen = getattr(sys, 'frozen', False)
    if not es_frozen:
        # En modo código fuente (.py), redirigir al navegador
        if messagebox.askyesno(
            "Actualización en Modo Desarrollador",
            "Estás ejecutando el proyecto en modo código fuente (Python).\n\n"
            "¿Deseas abrir la página de GitHub Releases para ver los cambios o descargar el .exe?",
            parent=ventana_padre
        ):
            webbrowser.open(GITHUB_RELEASES_URL)
        return

    exe_actual = os.path.abspath(sys.executable)
    carpeta_exe = os.path.dirname(exe_actual)
    temp_download_path = os.path.join(carpeta_exe, "SII_GestorFacturas_update.tmp")

    # Ventana de progreso modal
    modal_progreso = None
    if ventana_padre:
        modal_progreso = tk.Toplevel(ventana_padre)
        modal_progreso.title("Descargando actualización...")
        modal_progreso.geometry("420x150")
        modal_progreso.resizable(False, False)
        modal_progreso.configure(bg="#0d1424")
        modal_progreso.transient(ventana_padre)
        modal_progreso.grab_set()

        # Centrar
        try:
            x = ventana_padre.winfo_x() + (ventana_padre.winfo_width() // 2) - 210
            y = ventana_padre.winfo_y() + (ventana_padre.winfo_height() // 2) - 75
            modal_progreso.geometry(f"+{x}+{y}")
        except Exception:
            pass

        lbl = tk.Label(
            modal_progreso,
            text="Descargando nueva versión desde GitHub...",
            fg="#f8fafc",
            bg="#0d1424",
            font=("Segoe UI", 10, "bold")
        )
        lbl.pack(pady=(20, 10))

        pb = ttk.Progressbar(modal_progreso, mode="determinate", length=340)
        pb.pack(pady=5)

        lbl_mb = tk.Label(
            modal_progreso,
            text="Conectando...",
            fg="#94a3b8",
            bg="#0d1424",
            font=("Segoe UI", 8)
        )
        lbl_mb.pack(pady=5)

    def _hilo_descarga():
        try:
            if log_cb:
                log_cb("Iniciando descarga de actualización desde GitHub...")
            resp = requests.get(url_descarga, stream=True, timeout=30)
            resp.raise_for_status()

            total_len = resp.headers.get("content-length")
            total_bytes = int(total_len) if total_len else 0
            descargados = 0

            with open(temp_download_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        descargados += len(chunk)
                        if modal_progreso and total_bytes > 0:
                            pct = (descargados / total_bytes) * 100
                            mb_act = descargados / (1024 * 1024)
                            mb_tot = total_bytes / (1024 * 1024)
                            def _upd(p=pct, m1=mb_act, m2=mb_tot):
                                try:
                                    pb["value"] = p
                                    lbl_mb.config(text=f"{m1:.1f} MB / {m2:.1f} MB ({int(p)}%)")
                                except Exception:
                                    pass
                            modal_progreso.after(0, _upd)

            if log_cb:
                log_cb("✓ Descarga completada. Aplicando actualización y reiniciando...")

            # Preparar comando PowerShell para reemplazo atómico y reinicio
            pid_actual = os.getpid()
            ps_script = (
                f"$pidApp = {pid_actual}; "
                f"$tempExe = '{temp_download_path}'; "
                f"$destExe = '{exe_actual}'; "
                f"Start-Sleep -Milliseconds 800; "
                f"while (Get-Process -Id $pidApp -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 300 }}; "
                f"Move-Item -Path $tempExe -Destination $destExe -Force; "
                f"Start-Process -FilePath $destExe; "
            )

            # Lanzar PowerShell desacoplado en segundo plano
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Cerrar la aplicación actual limpiamente
            if modal_progreso:
                modal_progreso.after(0, modal_progreso.destroy)
            if ventana_padre:
                ventana_padre.after(100, lambda: os._exit(0))
            else:
                os._exit(0)

        except Exception as e:
            if log_cb:
                log_cb(f"[ERROR] Error al descargar actualización: {e}")
            if modal_progreso:
                modal_progreso.after(0, modal_progreso.destroy)
            def _show_err(err_text=str(e)):
                messagebox.showerror(
                    "Error de Actualización",
                    f"No se pudo completar la actualización automática:\n{err_text}\n\nPuedes descargarla manualmente desde GitHub.",
                    parent=ventana_padre
                )
            if ventana_padre:
                ventana_padre.after(0, _show_err)

    threading.Thread(target=_hilo_descarga, daemon=True).start()


def verificar_actualizaciones_inicio(ventana_padre, version_actual=VERSION_LOCAL, log_cb=None):
    """
    Ejecuta la comprobación de actualización en un hilo en segundo plano al iniciar el programa.
    Si encuentra una nueva versión, muestra el diálogo de confirmación en el hilo principal de Tkinter.
    """
    def _tarea_verificacion():
        try:
            info = consultar_version_github(REPO_GITHUB)
            if not info:
                return

            tag_remoto = info.get("tag", "")
            if not tag_remoto:
                return

            if es_version_mas_reciente(version_actual, tag_remoto):
                if log_cb:
                    log_cb(f"[AVISO] ¡Nueva versión disponible en GitHub! {version_actual} -> {tag_remoto}")

                url_exe = info.get("url_exe")
                detalles = info.get("body", "").strip()
                resumen_notas = f"\n\nNovedades de la versión:\n{detalles[:200]}..." if detalles else ""

                def _mostrar_alerta():
                    mensaje = (
                        f"¡Hay una nueva actualización disponible en GitHub!\n\n"
                        f"• Versión actual: {version_actual}\n"
                        f"• Nueva versión: {tag_remoto}{resumen_notas}\n\n"
                        f"¿Deseas actualizar el programa ahora?"
                    )
                    respuesta = messagebox.askyesno(
                        "Actualización Disponible • SII Gestor Facturas",
                        mensaje,
                        parent=ventana_padre
                    )
                    if respuesta:
                        if url_exe:
                            aplicar_actualizacion_windows(url_exe, ventana_padre=ventana_padre, log_cb=log_cb)
                        else:
                            # Si no hay asset binario directo, abrir release en navegador
                            webbrowser.open(info.get("html_url", GITHUB_RELEASES_URL))

                ventana_padre.after(0, _mostrar_alerta)
        except Exception:
            pass

    threading.Thread(target=_tarea_verificacion, daemon=True).start()

# 📋 Contexto y Memoria del Proyecto: Gestor de Facturas y RCV - SII

> **Documento de Transferencia de Contexto para Antigravity / Asistente IA**
> Este archivo resume todas las decisiones de diseño, requerimientos de usuario, arquitectura de código y el historial de desarrollo para retomar el trabajo en cualquier equipo (Laptop / Notebook / Linux / Windows) sin perder contexto.

---

## 🎯 1. Objetivo General del Sistema
Aplicación de escritorio en Python / Tkinter para automatizar la consulta y descarga masiva de Facturas Electrónicas (DTE) desde el portal del **Servicio de Impuestos Internos de Chile (SII)** y del **Registro de Compras y Ventas (RCV)**, con soporte para gestión de múltiples empresas.

---

## 🔑 2. Requerimientos Clave Implementados

1. **Gestión Multi-Empresa con Menú Desplegable (`empresas.json` y `app.py`):**
   * Selector `Combobox` estilizado en la cabecera del programa con las 22 empresas predeterminadas (Nombre y RUT).
   * Cambio dinámico de empresa en tiempo de ejecución: el usuario puede seleccionar una empresa distinta y consultar el RCV o MIPE sin reconectar.
   * Ventana modal de gestión para agregar nuevas empresas, editar nombres/RUTs, eliminar y restaurar las 22 originales.
   * Persistencia de la última empresa consultada en `config_app.json`.

2. **Sesión Persistente Única (`GestorSesionSII` en `script.py`):**
   * Se inicia sesión una sola vez vía Selenium Stealth.
   * Se exportan las cookies de sesión a `requests.Session()`.
   * Las descargas y consultas posteriores se hacen en milisegundos sin re-autenticación (evita bloqueos por límite de sesiones simultáneas del SII).
   * Cierre de sesión limpio con `autLogout.cgi` al salir del programa.

3. **Formato y Nomenclatura Exacta de Archivos:**
   * Estructura:
     $$\text{Corr\_\textbf{correlativo}\_FE\_\textbf{folio}, \textbf{ContextoFactura}, \textbf{NOMBREEMPRESA}.pdf}$$
   * La empresa proveedora se guarda siempre en **MAYÚSCULAS**.
   * El correlativo se autoincrementa secuencialmente en cada factura descargada (`2000` $\rightarrow$ `2001` $\rightarrow$ `2002`).
   * El estado del correlativo se guarda en `config_app.json`.

4. **Inteligencia Artificial para Glosas Específicas (`ai_context.py`):**
   * Lee la glosa y los ítems del PDF eliminando totalmente metadatos técnicos y códigos de sistema (ej: `CH1688@`, `@NOMBRE DE LA CAMPAÑA:`, `PRO@`, `ITEM 1:`, `COD. 1234`).
   * **Filtrado estricto de textos basura / errores ERP:** Descarta automáticamente textos genéricos de error como `PEPB FACTURACION NULL`, `null`, `undefined`, `sin descripción`.
   * **Deducción Inteligente si la glosa es nula / vacía:** Si el PDF no tiene descripción o viene con error (ej: `JETSMART AIRLINES SPA`, `UBER`, `ENEL`, `COPEC`), la IA deduce automáticamente el concepto real (ej: `Venta Pasaje Aereo Vuelo JetSMART`, `Servicio Transporte Traslado Uber`).
   * Formato **natural / capitalizado** (no mayúsculas sostenidas), ej: `Envios Comerciales a Canales TV Julio`, `Arriendo Oficina Comercial Agosto 2026`.
   * Límite ampliado a un **máximo de 65 palabras** con descripciones fluidas, humanas y sin cortes.
   * **Reglas específicas para Banco de Chile (4 tipos de facturas):**
     1. `Comision servicio de transferencias envio garantizado numero de operacion` $\rightarrow$ `Comisión operaciones de cambio`.
     2. `Comision mensaje swift operaciones de cambios internacionales` $\rightarrow$ `Comisión operaciones de cambio - Mensaje Swift`.
     3. `comision por orden de pago emitida y/o recibida` $\rightarrow$ `Comisión ordenes de pago`.
     4. `comision mensaul plan cuenta corriente pyme` $\rightarrow$ `Comisión Mantención Cuenta Corriente`.
   * **Regla estricta de mes:** El mes solo se extrae si está **explícitamente escrito dentro de la descripción o detalle del servicio** (NUNCA de la fecha de emisión del documento ni de los timbres).
   * Soporta **Google Gemini API**, **OpenAI API** y un **extractor local inteligente offline**.

5. **Interfaz Moderna, Limpia y Dashboard Bento (`app.py`):**
   * **Diseño Deep Slate / Obsidian Pro:** Paleta moderna y elegante de alto contraste (`#0b0f19`, `#131b2e`, `#1a243b`, `#263554`) con acentos vibrantes en Indigo (`#6366f1`), Esmeralda (`#10b981`), Ámbar (`#f59e0b`) y Coral (`#f43f5e`).
   * **Tarjetas Métricas KPI Estilo Bento:** Desglose en vivo de documentos, montos netos, IVA, retenciones y totales con tipografía grande y nítida.
   * **Botones de Acción con Jerarquía Clara:** Botones primarios en esmeralda e índigo de alto contraste y botones secundarios con estilo dark slate.
   * **Pestañas Modernas (`ttk.Notebook`):** Navegación fluida entre **Facturas y RCV** y **Boletas de Honorarios (BHE)**.
   * **Terminal de Registro Desplegable:** Ubicada en la parte inferior, oculta por defecto para mantener la vista limpia, con resaltado de colores en logs (`[INFO]`, `[OK]`, `[ERROR]`, `[AVISO]`).
   * **Soporte Multiplataforma y DPI Nítido:** Centrado automático a `1600x920` con icono en barra de tareas e integración para Windows y Linux.

5. **Módulo Dedicado de Boletas de Honorarios Electrónicas (`script_honorarios.py` y Pestaña BHE en `app.py`):**
   * **Acceso Directo con Credenciales de la Empresa:** El portal de Boletas de Honorarios del SII requiere autenticación directa con el RUT (`RUT_EMPRESA_HN`) y Clave Tributaria (`SII_CLAVE_HN`) de la empresa receptora.
   * **Consulta de Boletas Recibidas y Emitidas:** Mapea el informe anual y mensual de boletas de honorarios en `loa.sii.cl`, extrayendo Folio, Fecha, Emisor, Razón Social, Glosa de servicios, Monto Bruto, Retención (Impuesto) y Monto Líquido.
   * **KPIs de Honorarios:** Desglose automático de Total Boletas, Monto Bruto Total, Retención Total acumulada y Monto Líquido.
   * **Descarga de PDF de Alta Fidelidad:** Generación y descarga directa de documentos PDF mediante CDP `Page.printToPDF` y almacenamiento con nomenclatura organizada (`BHE_Folio_X_EMISOR_Mes_Ano.pdf`).
   * **Exportación CSV/Excel:** Generación del libro auxiliar de boletas de honorarios con detalle de retenciones.

6. **Módulo Dedicado de Facturación.cl - Desis (`script_facturacion_cl.py` y Pestaña Facturación.cl en `app.py`):**
   * **Autenticación AJAX & Sesión Dedicada:** Login automatizado en `https://www.facturacion.cl/` (Desis) enviando `empresa`, `usuario`, `password` al endpoint `accesoFE3.php` y redirigiendo al portal corporativo de la empresa (ej: `https://www.facturacion.cl/miempresa/`).
   * **Panel DTE Recibidos (Compras):** Consulta directa en `form/compra/paneldte2/index.php` con filtros dinámicos por rango de fechas mensual (`FechaDesdeEmitido`, `FechaHastaEmitido`) y recarga AJAX con `grdOC.reload()`.
   * **Extracción Completa de Datos:** Mapeo de Folio, Tipo de Documento (Factura 33, Exenta 34, Nota de Crédito 61, Nota de Débito 56, Guía 52, etc.), RUT Emisor, Razón Social / Proveedor, Fecha Docto, Monto Neto, Monto IVA, Monto Total, Fecha de Recepción SII y Estado de Acuse.
   * **Descarga Directa de PDFs Oficiales:** Decodificación de enlaces Base64 embebidos en el botón `vistaPrevia` y descarga autenticada en formato PDF estándar.
   * **Nomenclatura e Integración IA:** Soporte para correlativo secuencial, contexto manual y análisis de glosa comercial con Inteligencia Artificial (`ai_context.py`).
   * **Exportación CSV:** Exportación rápida de todos los DTEs consultados en formato delimitado por punto y coma.

7. **Visor Integrado de PDF de Alta Resolución (`src/ui/pdf_viewer.py`):**
   * Previsualización instantánea al hacer doble clic en cualquier factura, boleta de honorarios o DTE descargado.
   * Renderizado vectorial nítido con `pypdfium2` y PIL, soporte para zoom interactivo (50% a 300%), paginación, navegación con rueda del ratón y accesos directos para abrir en el visor del sistema o abrir la carpeta contenedora.

8. **Compilación a Ejecutable `.exe` y Auto-Updater Automático:**
   * Archivo autónomo: `SII_GestorFacturas.exe` (compilado con PyInstaller `--onefile --windowed`).
   * **Auto-Updater (`src/utils/updater.py`):** Consulta a GitHub Releases al iniciar y ofrece actualización en 1 clic con reemplazo atómico en Windows y reinicio automático.
   * Compilación estándar: `pyinstaller SII_GestorFacturas.spec --noconfirm`.

---

## 📂 3. Estructura Modular del Proyecto (`src/` Layout)

* **[`main.py`](main.py):** Punto de entrada principal y configuración DPI/AppUserModelID en Windows.
* **[`src/ui/`](src/ui/):** Capa de Interfaz Gráfica (Tkinter).
  * **[`src/ui/app_window.py`](src/ui/app_window.py):** Clase principal `AppSII`, barra lateral, gestión de módulos y KPIs.
  * **[`src/ui/pdf_viewer.py`](src/ui/pdf_viewer.py):** Visor modal de PDF con zoom, scroll y paginación.
  * **[`src/ui/theme.py`](src/ui/theme.py):** Paleta de colores Deep Slate / Obsidian y estilos ttk.
* **[`src/core/`](src/core/):** Motores de automatización y scraping.
  * **[`src/core/rcv_engine.py`](src/core/rcv_engine.py):** Sesión persistente y consultas/descargas de Facturas RCV / MIPE del SII.
  * **[`src/core/bhe_engine.py`](src/core/bhe_engine.py):** Consultas y descargas de Boletas de Honorarios Electrónicas (BHE).
  * **[`src/core/desis_engine.py`](src/core/desis_engine.py):** Consultas y descargas de Facturación.cl (Desis).
* **[`src/ai/`](src/ai/):** Capa de Inteligencia Artificial.
  * **[`src/ai/glosa_extractor.py`](src/ai/glosa_extractor.py):** Extracción y refinamiento de glosas con Gemini, OpenAI y fallback local.
* **[`src/utils/`](src/utils/):** Capa de utilidades y configuración.
  * **[`src/utils/config.py`](src/utils/config.py):** Persistencia de `config_app.json` y `empresas.json`.
  * **[`src/utils/helpers.py`](src/utils/helpers.py):** Manejo de rutas, fechas y apertura de archivos.
* **[`assets/`](assets/):** Recursos estáticos e iconos (`app_icon.ico`, `app_icon.png`).
* **[`empresas.json`](empresas.json):** Base de datos local con las 22 empresas registradas.
* **[`config_app.json`](config_app.json):** Almacenamiento local de preferencias de usuario.
* **[`requirements.txt`](requirements.txt):** Dependencias del proyecto.
* **[`.github/workflows/build_exe.yml`](.github/workflows/build_exe.yml):** Pipeline CI/CD para compilación automática de `.exe` en GitHub Actions.
* **[`SII_GestorFacturas.spec`](SII_GestorFacturas.spec):** Receta de compilación PyInstaller.

---

## 🏢 4. Lista de Empresas Integradas (22 Empresas)

1. `BEALICE SPA` - `76505297-1`
2. `PEDRO ANTONIO CONTRERAS CALDERON` - `9696421-8`
3. `AUDIFONOS CHILE SPA` - `77099672-4`
4. `COMUNICACIONES DIRECTAS CHILE SPA` - `76299996-K`
5. `OKSALUD SPA` - `76458359-0`
6. `V-ACTION SPA` - `76360435-7`
7. `PUBLICIDAD CARLOS CORNEJO MORENO E.I.R.L.` - `76696247-5`
8. `ASTRA COMS SPA` - `77956457-6`
9. `WE-PROSPECT SPA` - `77313675-0`
10. `DI PAOLA & ASOCIADOS CHILE S A` - `96994760-9`
11. `PRODUCTORA DE EVENTOS YULIA SAVCHENKO EIRL` - `76212375-4`
12. `COMUNICATIO SPA` - `76941483-5`
13. `FRANCISCO DI PAOLA PUBLICIDAD E.I.R.L` - `76493217-K`
14. `MEET SUPER CHILE SPA` - `76410455-2`
15. `CARLOS ENRIQUE KULM CABELLO` - `9323099-K`
16. `EIGHT MARKETING LAB SPA` - `76231321-9`
17. `RODRIGO ALEJANDRO RETAMALES VIVANCO SERVICIOS TECNOLOGIA Y COMERCIO E.` - `76234411-4`
18. `SYNAPTICA COACHING SPA` - `78052127-9`
19. `SOCIEDAD DISTRIBUIDORA Y COMERCIALIZADORA LTI LIMITADA` - `76510430-0`
20. `SERVICIOS DE COMUNICACIONES LATINOAMERICA SPA` - `78019373-5`
21. `PORTONES AUTOMÁTICOS SPA` - `78023923-9`
22. `COMERCIALIZADORA MORALES, MONTANER Y PÉREZ LIMITADA` - `77872358-1`

---

## 💻 5. Cómo Continuar en tu Notebook / Laptop

1. Clona el repositorio desde GitHub:
   ```bash
   git clone https://github.com/Pablitttoo/SII-RCV-DOWNLOADER.git
   ```
2. En Linux ejecuta `./iniciar_linux.sh` o en Windows `python app.py`.
3. Al iniciar una conversación con el asistente IA en el nuevo equipo, indícale:
   > *"Por favor lee `RESUMEN_PROYECTO_Y_CONTEXTO.md` para continuar desarrollando el proyecto con todo el contexto anterior."*

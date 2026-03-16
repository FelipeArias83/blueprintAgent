"""Text constants and templates for the Streamlit app UI and agent prompt."""

# UI: app shell and sidebar
APP_PAGE_TITLE = "Agente de Estructura de Proyecto"
APP_PAGE_ICON = ":building_construction:"
APP_TITLE = "Agente de Estructura de Proyecto"
APP_CAPTION = "Streamlit + LangGraph + Gemini + ChromaDB local"

SIDEBAR_GUIDE_HEADER = "Guia de uso"
SIDEBAR_CONFIG_SUBHEADER = "Configuracion"
GOOGLE_API_KEY_LABEL = "GOOGLE_API_KEY"
GOOGLE_API_KEY_HELP = "Ingresa tu API key de Google para usar Gemini."
GOOGLE_API_KEY_REQUIRED_ERROR = "Ingresa GOOGLE_API_KEY en la barra lateral para continuar"
ZIP_UPLOAD_LABEL = "Subir proyecto (.zip)"
ZIP_UPLOAD_HELP = "Sube un .zip con el codigo para analizarlo sin rutas locales."
ZIP_CLEAR_BUTTON = "Quitar proyecto subido"
ZIP_ACTIVE_PROJECT_TEMPLATE = "Proyecto activo desde ZIP: {path}"
ZIP_UPLOAD_ERROR_TEMPLATE = "No se pudo procesar el ZIP: {error}"
ZIP_UPLOAD_SUCCESS_TEMPLATE = "ZIP cargado correctamente: {name}"

# UI: README download panel
README_DOWNLOAD_LABEL = "Descargar README.md"
README_READY_CAPTION_TEMPLATE = "Archivo listo para descarga: {rel_path}"
README_DOWNLOAD_WARN_TEMPLATE = "No se pudo preparar la descarga de README.md: {error}"

# Backend: file reading
READ_SNIPPET_BINARY_PLACEHOLDER = "<binary-or-non-utf8-file>"
READ_SNIPPET_ERROR_TEMPLATE = "<error-reading-file: {error}>"

# Backend: Chroma retrieval
CHROMA_NO_CONTEXT_MESSAGE = "No hay contexto relevante en Chroma todavia."
CHROMA_QUERY_ERROR_TEMPLATE = "No se pudo consultar Chroma: {error}"

# Tool responses and validation errors
TOOL_ERROR_EMPTY_FILENAME = "filename vacio"
TOOL_ERROR_INVALID_OUTPUT_PATH = "ruta invalida: solo se permite escribir dentro de /output"
TOOL_ERROR_INVALID_TARGET_DIR = "target_dir no existe o no es directorio"
TOOL_ERROR_INVALID_REGEX_TEMPLATE = "regex invalida: {error}"
TOOL_SEARCH_TOO_MANY_RESULTS = "... (demasiados resultados)"

# UI: chat input and tutorial
CHAT_INPUT_PLACEHOLDER = (
	"Ejemplo: Analiza el proyecto .zip que subi y genera un README.md detallado en /output"
)

TUTORIAL_MARKDOWN = """
Esta app analiza la estructura de un proyecto y te ayuda a generar documentacion automaticamente.

**Que hace la app**
1. Detecta la carpeta objetivo desde tu prompt o usa la carpeta actual.
2. Indexa archivos en ChromaDB local para recuperar contexto relevante.
3. Usa Gemini para analizar y proponer documentacion.
4. Si pides un archivo, lo crea en `output/`.

**Capacidades principales**
- Analizar estructura de carpetas y archivos de un proyecto.
- Resumir modulos, responsabilidades y flujo general de la aplicacion.
- Buscar texto o patrones dentro de archivos del proyecto.
- Generar documentacion tecnica en formato Markdown.
- Crear artefactos en `output/` (por ejemplo `README.md`, guias, reportes).

**Tipos de ayuda que puedes pedir**
- README de proyecto.
- Arquitectura propuesta por capas/modulos.
- Inventario de componentes y dependencias.
- Checklist de mejoras tecnicas y deuda tecnica.
- Sugerencias de estructura para escalar el proyecto.

**Como usarla**
1. Sube un archivo `.zip` del proyecto (recomendado para servidor).
2. Escribe en el chat que quieres analizar.
3. Si no subes `.zip`, puedes indicar una ruta local en el prompt.
4. Pide el archivo final (ejemplo: `README.md`).
5. Descarga el README con el boton cuando aparezca.

**Plantillas utiles (copiar y pegar)**
- `Analiza mi proyecto y genera un README.md profesional en /output con secciones: descripcion, arquitectura, instalacion, uso y roadmap.`
- `Analiza C:\\ruta\\mi-proyecto y crea una guia tecnica en /output/GUIA_TECNICA.md.`
- `Busca en el proyecto referencias a autenticacion, jwt o token y resume hallazgos.`
- `Propon una arquitectura objetivo y una ruta de migracion por fases.`
- `Genera un informe de riesgos tecnicos y recomendaciones priorizadas en /output/REPORTE.md.`

**Ejemplos de prompts**
- `Analiza mi estructura actual y genera un README.md detallado en /output`
- `Analiza C:\\proyectos\\Udemy\\Voley\\staticsVoley y genera un README.md en /output`
- `Lista los modulos principales y propon una arquitectura recomendada`

**Como obtener mejores resultados**
- Se especifico con claridad el entregable: archivo, formato y nivel de detalle.
- Indica el stack (Python, Java, Node, etc.) y el tipo de audiencia (dev, negocio, onboarding).
- Pide estructura explicita: "incluye tabla de contenidos, pasos de instalacion y comandos".
- Si quieres una ruta concreta, incluyela textual en el prompt.

**Notas importantes**
- La app solo escribe dentro de `output/`.
- La base `chroma_db/` es local y acelera el contexto entre consultas.
- Debes ingresar `GOOGLE_API_KEY` en la barra lateral para usar el chat.
- Si cambias muchos archivos, vuelve a pedir el analisis para refrescar contexto.
- Si la ruta objetivo no existe, la herramienta reportara error de validacion.
"""

# LLM system prompt template
SYSTEM_PROMPT_TEMPLATE = (
	"Eres un Ingeniero de Software Senior y Agente de Estructura de Proyecto. "
	"Analiza la estructura local, propone documentacion clara y genera archivos cuando se te pida. "
	"Usa herramientas cuando necesites contexto o cuando debas crear archivos. "
	"Ruta objetivo actual para analizar: {target_dir}. "
	"Reglas: 1) Para crear archivos siempre usa write_output_file. "
	"2) Solo escribe dentro de /output. "
	"3) Luego de crear un archivo, confirma explicitamente si fue creado y verificado. "
	"4) Despues de confirmar, SIEMPRE muestra un resumen del contenido generado en el chat: "
	"incluye secciones principales y al menos 5 puntos clave concretos. "
	"5) Si el archivo es README.md, muestra adicionalmente una mini tabla de contenido en el chat. "
	"6) Si falla, explica el error y propone correccion.\n\n"
	"Snapshot de archivos (rapido):\n{file_snapshot}\n\n"
	"Contexto recuperado desde Chroma:\n{chroma_context}"
)

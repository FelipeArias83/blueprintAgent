# Blueprint Agent

Aplicacion Streamlit para analizar la estructura de proyectos y generar documentacion (por ejemplo, `README.md`) usando un agente con LangGraph + Gemini y recuperacion de contexto local con ChromaDB.

## Caracteristicas

- Chat asistido por LLM para analizar codigo y estructura de carpetas.
- Indexacion local de archivos en ChromaDB con embeddings deterministas (sin servicio externo de embeddings).
- Soporte para subir proyectos en `.zip` y analizarlos de forma aislada.
- Sesiones aisladas por usuario:
  - salida en `output/session_<id>/`
  - colecciones de Chroma separadas
  - eventos en `logs/multisession.log`
- Herramientas internas del agente para:
  - listar archivos
  - buscar texto o regex en archivos
  - escribir artefactos dentro de `output/`
- Limpieza automatica de artefactos y colecciones expiradas (24 horas por defecto).

## Stack

- Python
- Streamlit
- LangGraph / LangChain
- Gemini (`langchain-google-genai`)
- ChromaDB

## Estructura del proyecto

```text
blueprintAgent/
  app_texts.py
  main.py
  requirements.txt
  chroma_db/
  logs/
  output/
```

## Requisitos

- Python 3.10 o superior recomendado
- API Key de Google AI (Gemini)

## Instalacion

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux/macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuracion

El proyecto usa `python-dotenv`, por lo que puedes definir variables en un archivo `.env` en la raiz.

Variables soportadas:

- `GOOGLE_API_KEY`: requerida para invocar Gemini (tambien se puede ingresar desde la UI).
- `GEMINI_MODEL`: opcional, modelo principal (default: `gemini-2.5-flash`).
- `GEMINI_FALLBACK_MODEL`: opcional, modelo de respaldo si falla el principal (default: `gemini-2.5-pro`).

Ejemplo de `.env`:

```env
GOOGLE_API_KEY=tu_api_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-2.5-pro
```

## Ejecucion

```bash
streamlit run main.py
```

Luego abre la URL local que muestra Streamlit (por defecto `http://localhost:8501`).

## Flujo de uso

1. Ingresa un **Nombre de sesion** en la barra lateral (obligatorio).
2. Ingresa `GOOGLE_API_KEY` en la barra lateral.
3. Opcional: sube un archivo `.zip` del proyecto a analizar.
4. Escribe un prompt en el chat, por ejemplo:
   - `Analiza el proyecto y genera un README.md en /output`
5. Descarga el `README.md` cuando aparezca el boton de descarga.

## Como funciona internamente

1. La app resuelve una carpeta objetivo (ZIP subido, ruta indicada en prompt o carpeta base).
2. Indexa los archivos de esa carpeta en ChromaDB por chunks.
3. Recupera contexto relevante para la pregunta del usuario.
4. Ejecuta un grafo de LangGraph con:
   - nodo de razonamiento (LLM)
   - nodo de herramientas (`write_output_file`, `list_current_files`, `search_in_files`)
5. Si se solicita un archivo, lo escribe y verifica dentro de `output/session_<id>/`.

## Archivos y carpetas generados

- `output/session_<id>/...`: artefactos creados por el agente.
- `logs/multisession.log`: eventos en formato JSONL por sesion.
- `chroma_db/`: base local de Chroma y registro de colecciones.

## Seguridad y limites

- La escritura de archivos esta restringida a `output/session_<id>/`.
- Se validan rutas al extraer ZIP para mitigar path traversal.
- Se limita el ZIP a 700 MB descomprimido.
- El sistema omite rutas como `.git`, `.venv`, `__pycache__`, `chroma_db`, `output` durante analisis.

## Troubleshooting

- Error de API Key:
  - Verifica `GOOGLE_API_KEY` en sidebar o `.env`.
- El modelo no responde:
  - Revisa conectividad y cuota de Google AI.
  - El sistema intenta fallback automatico a `GEMINI_FALLBACK_MODEL` si el principal no existe.
- No se crea el archivo esperado:
  - Pide explicitamente nombre y ruta dentro de `/output`.
  - Revisa eventos con el boton **Ver ultimos logs**.
- Error al cargar ZIP:
  - Confirma que el ZIP contiene archivos validos y no excede el limite.

## Dependencias

Se instalan desde `requirements.txt`:

- `streamlit>=1.42.0`
- `langgraph>=0.2.56`
- `langchain-core>=0.3.31`
- `langchain-google-genai>=2.0.7`
- `chromadb>=0.5.23`
- `python-dotenv>=1.0.1`
- `langchain-text-splitters>=0.1.0`

## Licencia

Sin licencia definida actualmente en el repositorio.

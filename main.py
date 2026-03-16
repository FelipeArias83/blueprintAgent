import json
import hashlib
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from time import perf_counter
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app_texts import (
	APP_CAPTION,
	APP_PAGE_ICON,
	APP_PAGE_TITLE,
	APP_TITLE,
	CHAT_INPUT_PLACEHOLDER,
	CHROMA_NO_CONTEXT_MESSAGE,
	CHROMA_QUERY_ERROR_TEMPLATE,
	GOOGLE_API_KEY_HELP,
	GOOGLE_API_KEY_LABEL,
	GOOGLE_API_KEY_REQUIRED_ERROR,
	READ_SNIPPET_BINARY_PLACEHOLDER,
	READ_SNIPPET_ERROR_TEMPLATE,
	README_DOWNLOAD_LABEL,
	README_DOWNLOAD_WARN_TEMPLATE,
	README_READY_CAPTION_TEMPLATE,
	SIDEBAR_CONFIG_SUBHEADER,
	SIDEBAR_GUIDE_HEADER,
	SYSTEM_PROMPT_TEMPLATE,
	TOOL_ERROR_EMPTY_FILENAME,
	TOOL_ERROR_INVALID_OUTPUT_PATH,
	TOOL_ERROR_INVALID_REGEX_TEMPLATE,
	TOOL_ERROR_INVALID_TARGET_DIR,
	TOOL_SEARCH_TOO_MANY_RESULTS,
	TUTORIAL_MARKDOWN,
	ZIP_ACTIVE_PROJECT_TEMPLATE,
	ZIP_CLEAR_BUTTON,
	ZIP_UPLOAD_ERROR_TEMPLATE,
	ZIP_UPLOAD_HELP,
	ZIP_UPLOAD_LABEL,
	ZIP_UPLOAD_SUCCESS_TEMPLATE,
)


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHROMA_DIR = BASE_DIR / "chroma_db"
LOG_DIR = BASE_DIR / "logs"
COLLECTION_NAME = "project_structure"
SESSION_OUTPUT_PREFIX = "session_"
CHROMA_REGISTRY_PATH = CHROMA_DIR / "collection_registry.json"
MULTISESSION_LOG_PATH = LOG_DIR / "multisession.log"
ARTIFACT_MAX_AGE_SECONDS = 24 * 60 * 60


class SimpleEmbeddingFunction(EmbeddingFunction[Documents]):
	"""Local deterministic embeddings to avoid external embedding services."""

	def __call__(self, input: Documents) -> Embeddings:
		vectors: Embeddings = []
		for text in input:
			bins = [0.0] * 64
			for ch in text.lower():
				bins[ord(ch) % 64] += 1.0
			norm = sum(v * v for v in bins) ** 0.5 or 1.0
			vectors.append([v / norm for v in bins])
		return vectors


def log_multisession_event(
	event: str,
	status: str = "ok",
	target_dir: Path | None = None,
	resource: str = "",
	message: str = "",
	extra: dict[str, Any] | None = None,
	session_id: str = "",
	session_name: str = "",
) -> None:
	"""Write structured JSONL logs for session-aware operations."""
	try:
		LOG_DIR.mkdir(parents=True, exist_ok=True)
		record = {
			"timestamp": datetime.now(timezone.utc).isoformat(),
			"event": event,
			"status": status,
			"session_id": session_id or st.session_state.get("session_id", ""),
			"session_name": session_name or st.session_state.get("session_name", ""),
			"target_dir": str(target_dir.resolve()) if target_dir else "",
			"resource": resource,
			"message": message,
			"extra": extra or {},
		}
		with MULTISESSION_LOG_PATH.open("a", encoding="utf-8") as log_file:
			log_file.write(json.dumps(record, ensure_ascii=True) + "\n")
	except Exception:
		# Logging must never break app flow.
		pass


def get_last_n_log_events(n: int = 20) -> list[dict[str, Any]]:
	"""Read the last n events from the multisession log, filtering by current session."""
	if not MULTISESSION_LOG_PATH.exists():
		return []
	try:
		current_session_id = st.session_state.get("session_id", "")
		all_events = []
		with MULTISESSION_LOG_PATH.open("r", encoding="utf-8") as log_file:
			for line in log_file:
				if not line.strip():
					continue
				try:
					event = json.loads(line)
					if event.get("session_id") == current_session_id:
						all_events.append(event)
				except json.JSONDecodeError:
					continue
		return all_events[-n:] if all_events else []
	except Exception:
		return []


def get_session_id() -> str:
	session_id = st.session_state.get("session_id", "")
	if not session_id:
		session_id = uuid.uuid4().hex[:12]
		st.session_state.session_id = session_id
		log_multisession_event(
			event="session_created",
			session_id=session_id,
			session_name=st.session_state.get("session_name", ""),
		)
	return session_id


def get_session_output_dir() -> Path:
	session_output_dir = OUTPUT_DIR / f"{SESSION_OUTPUT_PREFIX}{get_session_id()}"
	session_output_dir.mkdir(parents=True, exist_ok=True)
	return session_output_dir


def get_collection_registry() -> dict[str, float]:
	if not CHROMA_REGISTRY_PATH.exists():
		return {}
	try:
		content = json.loads(CHROMA_REGISTRY_PATH.read_text(encoding="utf-8"))
		return content if isinstance(content, dict) else {}
	except Exception:
		return {}


def save_collection_registry(registry: dict[str, float]) -> None:
	CHROMA_DIR.mkdir(parents=True, exist_ok=True)
	CHROMA_REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=True), encoding="utf-8")


def get_chroma_collection_name(target_dir: Path) -> str:
	project_hash = hashlib.sha1(str(target_dir.resolve()).encode("utf-8")).hexdigest()[:12]
	return f"{COLLECTION_NAME}_{get_session_id()}_{project_hash}"


def touch_collection_usage(collection_name: str) -> None:
	registry = get_collection_registry()
	registry[collection_name] = time.time()
	save_collection_registry(registry)
	log_multisession_event(
		event="chroma_collection_used",
		resource=collection_name,
	)


def get_chroma_collection(target_dir: Path):
	client = chromadb.PersistentClient(path=str(CHROMA_DIR))
	collection_name = get_chroma_collection_name(target_dir)
	collection = client.get_or_create_collection(
		name=collection_name,
		embedding_function=SimpleEmbeddingFunction(),
	)
	touch_collection_usage(collection_name)
	return collection


def cleanup_expired_artifacts(max_age_seconds: int = ARTIFACT_MAX_AGE_SECONDS) -> None:
	now = time.time()
	if OUTPUT_DIR.exists():
		for path in OUTPUT_DIR.glob(f"{SESSION_OUTPUT_PREFIX}*"):
			if not path.is_dir():
				continue
			try:
				if now - path.stat().st_mtime > max_age_seconds:
					shutil.rmtree(path, ignore_errors=True)
					log_multisession_event(
						event="cleanup_deleted",
						resource=str(path),
						message="expired session output directory removed",
					)
			except Exception:
				continue

	temp_root = Path(tempfile.gettempdir())
	for path in temp_root.glob("asist_proj_*"):
		if not path.is_dir():
			continue
		try:
			if now - path.stat().st_mtime > max_age_seconds:
				shutil.rmtree(path, ignore_errors=True)
				log_multisession_event(
					event="cleanup_deleted",
					resource=str(path),
					message="expired uploaded temp directory removed",
				)
		except Exception:
			continue


def cleanup_expired_chroma_collections(max_age_seconds: int = ARTIFACT_MAX_AGE_SECONDS) -> None:
	registry = get_collection_registry()
	if not registry:
		return

	now = time.time()
	client = chromadb.PersistentClient(path=str(CHROMA_DIR))
	changed = False

	for collection_name, last_used in list(registry.items()):
		if now - float(last_used) <= max_age_seconds:
			continue
		try:
			client.delete_collection(name=collection_name)
		except Exception:
			pass
		registry.pop(collection_name, None)
		changed = True
		log_multisession_event(
			event="cleanup_deleted",
			resource=collection_name,
			message="expired chroma collection removed",
		)

	if changed:
		save_collection_registry(registry)


def clean_candidate_path(raw: str) -> str:
	return raw.strip().strip('"\'`.,;:)]}')


def cleanup_uploaded_project() -> None:
	temp_dir = st.session_state.get("uploaded_temp_dir", "")
	if temp_dir:
		shutil.rmtree(temp_dir, ignore_errors=True)

	st.session_state.pop("uploaded_target_dir", None)
	st.session_state.pop("uploaded_temp_dir", None)
	st.session_state.pop("uploaded_zip_signature", None)


def get_default_target_dir() -> Path:
	uploaded_target = st.session_state.get("uploaded_target_dir", "")
	if uploaded_target:
		candidate = Path(uploaded_target)
		if candidate.exists() and candidate.is_dir():
			return candidate
	return BASE_DIR


def extract_uploaded_zip(uploaded_file: Any) -> tuple[bool, str, Path | None, Path | None]:
	try:
		temp_dir = Path(tempfile.mkdtemp(prefix="asist_proj_"))
		resolved_temp = temp_dir.resolve()

		with zipfile.ZipFile(uploaded_file) as zip_ref:
			file_entries = [entry for entry in zip_ref.infolist() if not entry.is_dir()]
			if not file_entries:
				raise ValueError("el ZIP no contiene archivos")

			total_uncompressed = 0
			for entry in file_entries:
				total_uncompressed += entry.file_size
				if total_uncompressed > 700 * 1024 * 1024:
					raise ValueError("el ZIP supera 700 MB descomprimido")

				entry_target = (temp_dir / entry.filename).resolve()
				if not str(entry_target).startswith(str(resolved_temp)):
					raise ValueError("el ZIP contiene rutas invalidas")

			zip_ref.extractall(temp_dir)

		root_items = [item for item in temp_dir.iterdir() if item.name != "__MACOSX"]
		project_root = root_items[0] if len(root_items) == 1 and root_items[0].is_dir() else temp_dir
		return True, "", temp_dir, project_root
	except Exception as exc:
		if "temp_dir" in locals():
			shutil.rmtree(temp_dir, ignore_errors=True)
		return False, str(exc), None, None


def resolve_target_dir(user_text: str) -> Path:
	"""Resolve the directory to analyze from user text or current uploaded project."""
	candidates: list[str] = []

	# Explicit formats such as: ruta objetivo: C:\\repo\\project or target_dir=folder
	for pattern in [
		r"(?i)(?:ruta\s+objetivo|target(?:_dir)?|path)\s*[:=]\s*(.+)",
		r"(?i)(?:de|en)\s+([A-Za-z]:\\[^\s\"']+)",
		r"([A-Za-z]:\\[^\s\"']+)",
	]:
		for match in re.finditer(pattern, user_text):
			candidate = clean_candidate_path(match.group(1))
			if candidate:
				candidates.append(candidate)

	for candidate in candidates:
		path = Path(candidate).expanduser()
		if not path.is_absolute():
			path = (BASE_DIR / path).resolve()
		if path.exists() and path.is_dir():
			return path

	return get_default_target_dir()


def should_skip(path: Path) -> bool:
	skip_parts = {".git", ".venv", "__pycache__", "chroma_db", "output"}
	return any(part in skip_parts for part in path.parts)


def read_file_snippet(path: Path, max_chars: int = 3000) -> str:
	try:
		content = path.read_text(encoding="utf-8")
		return content[:max_chars]
	except UnicodeDecodeError:
		return READ_SNIPPET_BINARY_PLACEHOLDER
	except Exception as exc:
		return READ_SNIPPET_ERROR_TEMPLATE.format(error=exc)


def sync_project_to_chroma(target_dir: Path) -> None:
	collection = get_chroma_collection(target_dir)
	target_dir = target_dir.resolve()
	target_root = str(target_dir)

	# Configuramos el divisor de texto para indexar archivos largos en chunks.
	text_splitter = RecursiveCharacterTextSplitter(
		chunk_size=2000,
		chunk_overlap=200,
		length_function=len,
	)

	all_docs: list[str] = []
	all_ids: list[str] = []
	all_metas: list[dict[str, Any]] = []

	for path in target_dir.rglob("*"):
		if not path.is_file() or should_skip(path):
			continue

		content = read_file_snippet(path, max_chars=100000)
		if "<error" in content or "<binary" in content:
			continue

		relative_path = path.relative_to(target_dir).as_posix()
		chunks = text_splitter.split_text(content)

		for i, chunk_text in enumerate(chunks):
			chunk_id = f"{target_root}::{relative_path}::chunk_{i}"
			all_docs.append(f"FILE: {relative_path}\n\n{chunk_text}")
			all_ids.append(chunk_id)
			all_metas.append(
				{
					"path": relative_path,
					"target_root": target_root,
					"chunk_index": i,
				}
			)

	if all_ids:
		collection.upsert(ids=all_ids, documents=all_docs, metadatas=all_metas)

	# Eliminamos chunks obsoletos del target actual para evitar contexto viejo.
	existing_ids = set(collection.get(where={"target_root": target_root}, include=[]).get("ids", []))
	current_ids = set(all_ids)
	stale_ids = list(existing_ids - current_ids)
	if stale_ids:
		collection.delete(ids=stale_ids)


def list_files_internal(base_path: Path, max_items: int = 200) -> list[str]:
	base_path = base_path.resolve()
	results: list[str] = []
	for path in sorted(base_path.rglob("*")):
		if should_skip(path):
			continue
		rel = path.relative_to(base_path).as_posix()
		if path.is_dir():
			results.append(f"{rel}/")
		else:
			results.append(rel)
		if len(results) >= max_items:
			results.append("... (truncated)")
			break
	return results


def get_retrieved_context(query: str, target_dir: Path, n_results: int = 6) -> str:
	try:
		collection = get_chroma_collection(target_dir)
		results = collection.query(
			query_texts=[query],
			n_results=n_results,
			where={"target_root": str(target_dir.resolve())},
		)
		docs = results.get("documents", [[]])
		flat_docs = docs[0] if docs else []
		if not flat_docs:
			return CHROMA_NO_CONTEXT_MESSAGE
		return "\n\n---\n\n".join(flat_docs)
	except Exception as exc:
		return CHROMA_QUERY_ERROR_TEMPLATE.format(error=exc)


@tool
def write_output_file(filename: str, content: str) -> str:
	"""Create a file inside /output and verify it was written correctly."""
	session_output_dir = get_session_output_dir()
	try:
		if not filename.strip():
			log_multisession_event(
				event="file_written",
				status="error",
				resource=filename,
				message=TOOL_ERROR_EMPTY_FILENAME,
			)
			return json.dumps({"ok": False, "error": TOOL_ERROR_EMPTY_FILENAME}, ensure_ascii=True)

		target = (session_output_dir / filename).resolve()
		output_root = session_output_dir.resolve()
		if not str(target).startswith(str(output_root)):
			log_multisession_event(
				event="file_written",
				status="error",
				resource=filename,
				message=TOOL_ERROR_INVALID_OUTPUT_PATH,
			)
			return json.dumps(
				{
					"ok": False,
					"error": TOOL_ERROR_INVALID_OUTPUT_PATH,
				},
				ensure_ascii=True,
			)

		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_text(content, encoding="utf-8")

		exists = target.exists()
		written = target.read_text(encoding="utf-8") if exists else ""
		verified = exists and (written == content)
		log_multisession_event(
			event="file_written",
			status="ok" if verified else "error",
			resource=str(target.relative_to(BASE_DIR).as_posix()),
			extra={"bytes": len(content.encode("utf-8"))},
		)
		return json.dumps(
			{
				"ok": verified,
				"verified": verified,
				"path": str(target.relative_to(BASE_DIR).as_posix()),
				"bytes": len(content.encode("utf-8")),
			},
			ensure_ascii=True,
		)
	except Exception as exc:
		log_multisession_event(
			event="file_written",
			status="error",
			resource=filename,
			message=str(exc),
		)
		return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)


@tool
def list_current_files(target_dir: str = "") -> str:
	"""List files and folders from BASE_DIR or from a provided target directory."""
	try:
		base_path = get_default_target_dir()
		if target_dir.strip():
			candidate = Path(target_dir).expanduser()
			if not candidate.is_absolute():
				candidate = (BASE_DIR / candidate).resolve()
			if not candidate.exists() or not candidate.is_dir():
				return json.dumps(
					{"ok": False, "error": TOOL_ERROR_INVALID_TARGET_DIR},
					ensure_ascii=True,
				)
			base_path = candidate

		files = list_files_internal(base_path=base_path, max_items=300)
		return json.dumps({"ok": True, "cwd": str(base_path), "items": files}, ensure_ascii=True)
	except Exception as exc:
		return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)


@tool
def search_in_files(query: str, target_dir: str = "") -> str:
	"""Busca una palabra clave o regex de forma exacta en todos los archivos del proyecto."""
	start_time = perf_counter()
	try:
		base_path = get_default_target_dir()
		if target_dir.strip():
			candidate = Path(target_dir).expanduser()
			if not candidate.is_absolute():
				candidate = (BASE_DIR / candidate).resolve()
			if not candidate.exists() or not candidate.is_dir():
				return json.dumps(
					{"ok": False, "error": TOOL_ERROR_INVALID_TARGET_DIR},
					ensure_ascii=True,
				)
			base_path = candidate

		try:
			pattern = re.compile(query, re.IGNORECASE)
		except re.error as exc:
			return json.dumps(
				{"ok": False, "error": TOOL_ERROR_INVALID_REGEX_TEMPLATE.format(error=exc)},
				ensure_ascii=True,
			)

		results: list[str] = []
		files_scanned = 0
		matched_files = 0
		for path in base_path.rglob("*"):
			if not path.is_file() or should_skip(path):
				continue
			files_scanned += 1

			try:
				content = path.read_text(encoding="utf-8")
				if pattern.search(content):
					matched_files += 1
					for i, line in enumerate(content.splitlines()):
						if pattern.search(line):
							results.append(f"{path.relative_to(base_path)} [L{i+1}]: {line.strip()}")
			except Exception:
				continue

			if len(results) > 50:
				results.append(TOOL_SEARCH_TOO_MANY_RESULTS)
				break

		elapsed_ms = int((perf_counter() - start_time) * 1000)
		return json.dumps(
			{
				"ok": True,
				"matches": results,
				"matches_count": len(results),
				"matched_files": matched_files,
				"files_scanned": files_scanned,
				"elapsed_ms": elapsed_ms,
			},
			ensure_ascii=True,
		)
	except Exception as exc:
		elapsed_ms = int((perf_counter() - start_time) * 1000)
		return json.dumps({"ok": False, "error": str(exc), "elapsed_ms": elapsed_ms}, ensure_ascii=True)


TOOLS = [write_output_file, list_current_files, search_in_files]


def build_graph():
	model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
	fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

	llm_holder = {
		"model": model_name,
		"client": ChatGoogleGenerativeAI(model=model_name, temperature=0.2).bind_tools(TOOLS),
	}

	def reasoning_node(state: MessagesState):
		latest_user_text = ""
		for message in reversed(state["messages"]):
			if isinstance(message, HumanMessage):
				latest_user_text = str(message.content)
				break

		target_dir = resolve_target_dir(latest_user_text)

		sync_project_to_chroma(target_dir)
		chroma_context = get_retrieved_context(
			latest_user_text or "estructura del proyecto", target_dir=target_dir
		)
		file_snapshot = "\n".join(list_files_internal(base_path=target_dir, max_items=120))

		system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
			target_dir=target_dir,
			file_snapshot=file_snapshot,
			chroma_context=chroma_context,
		)

		try:
			response = llm_holder["client"].invoke([SystemMessage(content=system_prompt), *state["messages"]])
		except Exception as exc:
			message = str(exc)
			if ("NOT_FOUND" in message or "is not found" in message) and llm_holder["model"] != fallback_model:
				llm_holder["model"] = fallback_model
				llm_holder["client"] = ChatGoogleGenerativeAI(
					model=fallback_model,
					temperature=0.2,
				).bind_tools(TOOLS)
				response = llm_holder["client"].invoke(
					[SystemMessage(content=system_prompt), *state["messages"]]
				)
			else:
				raise
		return {"messages": [response]}

	graph_builder = StateGraph(MessagesState)
	graph_builder.add_node("reason", reasoning_node)
	graph_builder.add_node("tools", ToolNode(TOOLS))

	graph_builder.add_edge(START, "reason")
	graph_builder.add_conditional_edges("reason", tools_condition, {"tools": "tools", END: END})
	graph_builder.add_edge("tools", "reason")

	return graph_builder.compile()

def _extract_text(content: Any) -> str:
    """Return only the text from an AIMessage content (str or list of parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


def render_chat(messages: list[Any]) -> None:
    for message in messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(str(message.content))
        elif isinstance(message, AIMessage):
            text = _extract_text(message.content)
            if text:
                with st.chat_message("assistant"):
                    st.markdown(text)


def get_latest_readme_in_output() -> Path | None:
	session_output_dir = get_session_output_dir()
	if not session_output_dir.exists():
		return None

	readme_files = [
		path
		for path in session_output_dir.rglob("*")
		if path.is_file() and path.name.lower() == "readme.md"
	]
	if not readme_files:
		return None

	return max(readme_files, key=lambda p: p.stat().st_mtime)


def render_readme_download() -> None:
	readme_path = get_latest_readme_in_output()
	if not readme_path:
		return

	try:
		content = readme_path.read_text(encoding="utf-8")
		rel_path = readme_path.relative_to(BASE_DIR).as_posix()
		st.download_button(
			label=README_DOWNLOAD_LABEL,
			data=content,
			file_name="README.md",
			mime="text/markdown",
			key=f"download-readme-{readme_path.stat().st_mtime_ns}",
		)
		st.caption(README_READY_CAPTION_TEMPLATE.format(rel_path=rel_path))
	except Exception as exc:
		st.warning(README_DOWNLOAD_WARN_TEMPLATE.format(error=exc))


def render_sidebar_tutorial() -> None:
	with st.sidebar:
		st.header(SIDEBAR_GUIDE_HEADER)
		st.markdown(TUTORIAL_MARKDOWN)


def main() -> None:
	load_dotenv()
	if not st.session_state.get("cleanup_done"):
		cleanup_expired_artifacts()
		cleanup_expired_chroma_collections()
		st.session_state.cleanup_done = True

	st.set_page_config(page_title=APP_PAGE_TITLE, page_icon=APP_PAGE_ICON)
	st.title(APP_TITLE)
	st.caption(APP_CAPTION)

	with st.sidebar:
		st.subheader(SIDEBAR_CONFIG_SUBHEADER)
		session_name = st.text_input(
			"Nombre de sesion",
			value=st.session_state.get("session_name", ""),
			help="Identificador amigable para logs y aislamiento de sesion.",
		)
		normalized_session_name = session_name.strip()
		if normalized_session_name != st.session_state.get("session_name", ""):
			st.session_state.session_name = normalized_session_name
			log_multisession_event(
				event="session_name_updated",
				status="ok" if normalized_session_name else "error",
				message="session name updated" if normalized_session_name else "empty session name",
			)

		if not normalized_session_name:
			st.warning("Debes ingresar un nombre de sesion para continuar.")
			st.stop()

		# Button to view last 20 log events
		if st.button("📋 Ver ultimos logs", use_container_width=True):
			log_events = get_last_n_log_events(n=20)
			if log_events:
				with st.expander(f"Ultimos {len(log_events)} eventos de tu sesion", expanded=True):
					for idx, event in enumerate(reversed(log_events), 1):
						ts = event.get("timestamp", "?")[:19]
						evt = event.get("event", "?")
						status_icon = "✅" if event.get("status") == "ok" else "❌"
						resource = event.get("resource", "")
						msg = event.get("message", "")
						detail = f"{resource}" + (f" - {msg}" if msg else "")
						st.write(f"{status_icon} **{ts}** | `{evt}` | {detail}")
			else:
				st.info("No hay eventos en esta sesion todavia.")

		default_key = st.session_state.get("google_api_key", os.getenv("GOOGLE_API_KEY", ""))
		api_key = st.text_input(
			GOOGLE_API_KEY_LABEL,
			value=default_key,	
			type="password",
			help=GOOGLE_API_KEY_HELP,
		)

		uploaded_zip = st.file_uploader(
			ZIP_UPLOAD_LABEL,
			type=["zip"],
			help=ZIP_UPLOAD_HELP,
			key="project_zip_file",
		)

		if st.button(ZIP_CLEAR_BUTTON, use_container_width=True):
			cleanup_uploaded_project()
			st.rerun()

		if uploaded_zip is not None:
			zip_signature = f"{uploaded_zip.name}:{uploaded_zip.size}"
			if zip_signature != st.session_state.get("uploaded_zip_signature"):
				cleanup_uploaded_project()
				ok, err, temp_dir, project_root = extract_uploaded_zip(uploaded_zip)
				if ok and temp_dir and project_root:
					st.session_state.uploaded_zip_signature = zip_signature
					st.session_state.uploaded_temp_dir = str(temp_dir)
					st.session_state.uploaded_target_dir = str(project_root)
					log_multisession_event(
						event="zip_uploaded",
						target_dir=project_root,
						resource=uploaded_zip.name,
						extra={"size": uploaded_zip.size},
					)
					st.success(ZIP_UPLOAD_SUCCESS_TEMPLATE.format(name=uploaded_zip.name))
				else:
					log_multisession_event(
						event="zip_uploaded",
						status="error",
						resource=uploaded_zip.name,
						message=err,
					)
					st.error(ZIP_UPLOAD_ERROR_TEMPLATE.format(error=err))

		active_target = st.session_state.get("uploaded_target_dir", "")
		if active_target:
			st.caption(ZIP_ACTIVE_PROJECT_TEMPLATE.format(path=active_target))

	if not api_key:
		st.error(GOOGLE_API_KEY_REQUIRED_ERROR)
		st.stop()

	st.session_state.google_api_key = api_key
	os.environ["GOOGLE_API_KEY"] = api_key

	if st.session_state.get("active_api_key") != api_key:
		st.session_state.active_api_key = api_key
		st.session_state.graph = build_graph()
	elif "graph" not in st.session_state:
		st.session_state.graph = build_graph()
	if "messages" not in st.session_state:
		st.session_state.messages = []

	render_sidebar_tutorial()
	render_chat(st.session_state.messages)
	render_readme_download()

	prompt = st.chat_input(CHAT_INPUT_PLACEHOLDER)
	if not prompt:
		return

	new_state = {"messages": [*st.session_state.messages, HumanMessage(content=prompt)]}
	result = st.session_state.graph.invoke(new_state)
	st.session_state.messages = result["messages"]

	st.rerun()


if __name__ == "__main__":
	main()

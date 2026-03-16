"""Utility and helper functions: session management, ChromaDB, filesystem, ZIP handling."""

import hashlib
import json
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
import streamlit as st
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app_texts import (
    CHROMA_NO_CONTEXT_MESSAGE,
    CHROMA_QUERY_ERROR_TEMPLATE,
    READ_SNIPPET_BINARY_PLACEHOLDER,
    READ_SNIPPET_ERROR_TEMPLATE,
)
from config import (
    ARTIFACT_MAX_AGE_SECONDS,
    BASE_DIR,
    CHROMA_DIR,
    CHROMA_REGISTRY_PATH,
    COLLECTION_NAME,
    LOG_DIR,
    MULTISESSION_LOG_PATH,
    OUTPUT_DIR,
    SESSION_OUTPUT_PREFIX,
)
from embeddings import SimpleEmbeddingFunction


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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
    """Read the last n events from the multisession log, filtered by current session."""
    if not MULTISESSION_LOG_PATH.exists():
        return []
    try:
        current_session_id = st.session_state.get("session_id", "")
        all_events: list[dict[str, Any]] = []
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


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ChromaDB registry
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ChromaDB indexing and retrieval
# ---------------------------------------------------------------------------

def sync_project_to_chroma(target_dir: Path) -> None:
    collection = get_chroma_collection(target_dir)
    target_dir = target_dir.resolve()
    target_root = str(target_dir)

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

    # Remove stale chunks from previous indexing runs for this target.
    existing_ids = set(collection.get(where={"target_root": target_root}, include=[]).get("ids", []))
    current_ids = set(all_ids)
    stale_ids = list(existing_ids - current_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)


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


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

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

"""LangChain tools exposed to the LangGraph agent."""

import json
import re
from pathlib import Path
from time import perf_counter

from langchain_core.tools import tool

from app_texts import (
    TOOL_ERROR_EMPTY_FILENAME,
    TOOL_ERROR_INVALID_OUTPUT_PATH,
    TOOL_ERROR_INVALID_TARGET_DIR,
    TOOL_ERROR_INVALID_REGEX_TEMPLATE,
    TOOL_SEARCH_TOO_MANY_RESULTS,
)
from config import BASE_DIR
from utils import (
    get_default_target_dir,
    get_session_output_dir,
    list_files_internal,
    log_multisession_event,
    should_skip,
)


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
                {"ok": False, "error": TOOL_ERROR_INVALID_OUTPUT_PATH},
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

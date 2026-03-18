import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from app_texts import (
	APP_CAPTION,
	APP_PAGE_ICON,
	APP_PAGE_TITLE,
	APP_TITLE,
	CHAT_INPUT_PLACEHOLDER,
	GOOGLE_API_KEY_HELP,
	GOOGLE_API_KEY_LABEL,
	GOOGLE_API_KEY_REQUIRED_ERROR,
	README_DOWNLOAD_LABEL,
	README_DOWNLOAD_WARN_TEMPLATE,
	README_READY_CAPTION_TEMPLATE,
	SIDEBAR_CONFIG_SUBHEADER,
	SIDEBAR_GUIDE_HEADER,
	TUTORIAL_MARKDOWN,
	ZIP_ACTIVE_PROJECT_TEMPLATE,
	ZIP_CLEAR_BUTTON,
	ZIP_UPLOAD_ERROR_TEMPLATE,
	ZIP_UPLOAD_HELP,
	ZIP_UPLOAD_LABEL,
	ZIP_UPLOAD_SUCCESS_TEMPLATE,
)
from config import BASE_DIR, CHROMA_DIR, OUTPUT_DIR
from graph import build_graph
from utils import (
	_extract_text,
	cleanup_expired_artifacts,
	cleanup_expired_chroma_collections,
	cleanup_uploaded_project,
	extract_uploaded_zip,
	get_chroma_collection_rows,
	get_last_n_log_events,
	inspect_chroma_db,
	log_multisession_event,
)


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
	if not OUTPUT_DIR.exists():
		return None

	readme_files = [
		path
		for path in OUTPUT_DIR.rglob("*")
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


def render_chroma_console_tab() -> None:
	st.subheader("Consola rapida Chroma")
	st.caption("Inspecciona una base local usando chromadb.PersistentClient(path=...).")

	default_path = st.session_state.get("chroma_console_path", str(CHROMA_DIR))
	db_path = st.text_input(
		"Ruta local de ChromaDB",
		value=default_path,
		help="Ejemplo: ./chroma_db o C:\\ruta\\a\\chroma_db",
		key="chroma-console-path-input",
	)
	include_samples = st.checkbox("Mostrar IDs de ejemplo", value=False)

	if st.button("Inspeccionar Chroma", use_container_width=True):
		st.session_state.chroma_console_path = db_path
		result = inspect_chroma_db(db_path=db_path, include_samples=include_samples, sample_size=5)
		st.session_state.chroma_console_result = result

	result = st.session_state.get("chroma_console_result")
	if not result:
		return

	if not result.get("ok"):
		st.error(f"Error: {result.get('error', 'error desconocido')}")
		return

	st.success(f"Ruta: {result.get('path')}")
	st.write(f"Colecciones encontradas: {result.get('collections_count', 0)}")
	st.write(f"Archivo sqlite detectado: {'si' if result.get('sqlite_exists') else 'no'}")

	collections = result.get("collections", [])
	if collections:
		st.dataframe(collections, use_container_width=True)
		collection_names = [item.get("name", "") for item in collections if item.get("name")]
		selected_collection = st.selectbox(
			"Coleccion",
			options=collection_names,
			key="chroma-console-selected-collection",
		)
		rows_limit = st.number_input(
			"Filas a mostrar",
			min_value=1,
			max_value=200,
			value=10,
			step=1,
			key="chroma-console-rows-limit",
		)
		if st.button("Ver datos guardados", use_container_width=True):
			rows_result = get_chroma_collection_rows(
				db_path=result.get("path", db_path),
				collection_name=selected_collection,
				limit=int(rows_limit),
			)
			st.session_state.chroma_console_rows_result = rows_result
	else:
		st.info("No se encontraron colecciones en la ruta indicada.")

	rows_result = st.session_state.get("chroma_console_rows_result")
	if rows_result:
		if not rows_result.get("ok"):
			st.error(f"Error leyendo filas: {rows_result.get('error', 'error desconocido')}")
		else:
			st.write(
				f"Coleccion `{rows_result.get('collection')}`: {rows_result.get('rows_count', 0)} filas"
			)
			rows = rows_result.get("rows", [])
			if rows:
				st.dataframe(rows, use_container_width=True)
			else:
				st.info("No hay filas para mostrar en esa coleccion.")

	code_path = result.get("path", db_path)
	st.code(
		"# Conexion a tu base local\n"
		f"client = chromadb.PersistentClient(path=r\"{code_path}\")\n"
		"collections = client.list_collections()\n"
		"for col in collections:\n"
		"    print(col.name, col.count())",
		language="python",
	)


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

		api_key = st.text_input(
			GOOGLE_API_KEY_LABEL,
			value="",	
			type="password",
			help=GOOGLE_API_KEY_HELP,
		)
		
		if st.button("🗑️ Limpiar API Key", use_container_width=True):
			st.session_state.pop("active_api_key", None)
			if "GOOGLE_API_KEY" in os.environ:
				del os.environ["GOOGLE_API_KEY"]
			st.rerun()

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

	render_sidebar_tutorial()
	tab_chat, tab_chroma = st.tabs(["Chat", "Consola Chroma"])

	with tab_chroma:
		render_chroma_console_tab()

	with tab_chat:
		if not api_key:
			st.error(GOOGLE_API_KEY_REQUIRED_ERROR)
			st.info("Puedes usar la pestaña 'Consola Chroma' sin API key.")
			return

		os.environ["GOOGLE_API_KEY"] = api_key

		if st.session_state.get("active_api_key") != api_key:
			st.session_state.active_api_key = api_key
			st.session_state.graph = build_graph()
		elif "graph" not in st.session_state:
			st.session_state.graph = build_graph()
		if "messages" not in st.session_state:
			st.session_state.messages = []

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

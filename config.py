"""Centralized configuration: paths and global constants."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHROMA_DIR = BASE_DIR / "chroma_db"
LOG_DIR = BASE_DIR / "logs"

COLLECTION_NAME = "project_structure"
SESSION_OUTPUT_PREFIX = "session_"
CHROMA_REGISTRY_PATH = CHROMA_DIR / "collection_registry.json"
MULTISESSION_LOG_PATH = LOG_DIR / "multisession.log"
ARTIFACT_MAX_AGE_SECONDS = 24 * 60 * 60

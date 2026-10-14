"""Filesystem paths, resolved relative to the repository root (never the working directory)."""

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]

RAW_DIR: Path = REPO_ROOT / "raw"
DATA_DIR: Path = REPO_ROOT / "data"
FIXTURES_DIR: Path = REPO_ROOT / "tests" / "fixtures"

# Raw inputs (not committed; see raw/README.md)
RAW_RULES_JSON: Path = RAW_DIR / "strauss-rules.json"
RAW_VALUE_OF_USE_CSV: Path = RAW_DIR / "value_of_use_2026.csv"
RAW_CHALLENGE_XLSX: Path = RAW_DIR / "strauss_challenge_data.xlsx"

# Generated / curated data
VEHICLES_DB: Path = DATA_DIR / "vehicles.db"
CATALOG_JSON: Path = DATA_DIR / "catalog.json"
OCCUPATIONS_JSON: Path = DATA_DIR / "occupations.json"
RULES_YAML: Path = DATA_DIR / "rules.yaml"

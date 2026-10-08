"""Settings and file paths in one place.

Keys are read from `Portfolio Projects/.env` (two folders above this repo) when it exists,
then from a local `.env`, then from normal environment variables. Keys are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # the downloaded event log lives here and is NOT committed (licence + size)
EVALS_DIR = REPO_ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"
DOCS_DIR = REPO_ROOT / "docs"
CHARTS_DIR = DOCS_DIR / "charts"

# override=False: real environment variables (e.g. Hugging Face Space secrets) win over .env files.
load_dotenv(REPO_ROOT.parent.parent / ".env", override=False)
load_dotenv(REPO_ROOT / ".env", override=False)

CLIENT_NAME = "Falcon Bay Services LLC (fictional)"
RUN_DATE = "2026-10-08"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def model_id(role: str) -> str:
    """role is 'main', 'cheap' or 'judge' -> the model ID from MODEL_MAIN / MODEL_CHEAP / MODEL_JUDGE."""
    return env(f"MODEL_{role.upper()}")


def max_cost_per_run() -> float:
    """Budget guard for one evaluation command (US$). The runner stops when the running total passes it."""
    return float(env("MAX_COST_PER_RUN_USD", "2") or 2)

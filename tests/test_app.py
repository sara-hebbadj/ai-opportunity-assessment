"""The dashboard builds without a key (demo mode) and its helper functions work offline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app" / "app.py"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os

    saved = {k: os.environ.pop(k, None) for k in ("OPENROUTER_API_KEY", "MODEL_CHEAP")}
    spec = importlib.util.spec_from_file_location("dashboard", APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    for key, value in saved.items():
        if value is not None:
            os.environ[key] = value


def test_demo_mode_banner(app):
    if app.LIVE:
        pytest.skip("a key is set in this environment")
    assert "Demo mode" in app.BANNER


def test_rules_check_runs_without_a_model(app):
    claim_text, rules, model, gold = app.run_check("FB-C001")
    assert "FB-C001" in claim_text and rules.startswith("**Rules only")
    assert "Planted problems" in gold


def test_reranking_with_custom_weights(app):
    if not app.SUMMARY:
        pytest.skip("no summary.json yet")
    rows, note = app.rerank(100, 0, 0, 0, 0)
    values = [row[2] for row in rows]
    assert values == sorted(values, reverse=True)
    assert "value 100%" in note


def test_builds_the_blocks(app):
    assert app.build() is not None

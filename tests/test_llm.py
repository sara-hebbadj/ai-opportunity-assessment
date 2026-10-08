"""The model client: JSON parsing, traces and the budget guard (no network)."""

from __future__ import annotations

import json

import pytest

from opportunity_assessment.llm import BudgetExceeded, FakeLLM, OpenRouterClient, Tracer, parse_json


def test_parse_json_handles_fences_and_words():
    assert parse_json('Here you go:\n```json\n{"theme": "T2"}\n```') == {"theme": "T2"}
    with pytest.raises(ValueError):
        parse_json("no json")


def test_fake_llm_writes_a_trace(tmp_path):
    tracer = Tracer(path=tmp_path / "traces.jsonl", context={"run": "test"})
    FakeLLM(tracer).complete([{"role": "user", "content": "hi"}], purpose="precheck")
    record = json.loads((tmp_path / "traces.jsonl").read_text().splitlines()[0])
    assert record["model"] == "fake-offline" and record["run"] == "test" and record["cost_usd"] == 0


def test_budget_guard_stops_before_calling(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MODEL_CHEAP", "some/model")
    client = OpenRouterClient(Tracer(path=tmp_path / "t.jsonl"), budget_usd=1.0)
    client.tracer.total_cost = 1.5
    with pytest.raises(BudgetExceeded):
        client.complete([{"role": "user", "content": "hi"}])  # would need the network if the guard failed

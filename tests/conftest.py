"""Shared test fixtures. Tests never use the network or a real model."""

from __future__ import annotations

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path):
    """Fail loudly if any test tries to open a network connection; keep traces in tmp."""
    def blocked(*args, **kwargs):
        raise RuntimeError("network access is not allowed in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setenv("TRACES_PATH", str(tmp_path / "traces.jsonl"))


class ScriptedLLM:
    """A tiny fake model that returns the given texts in order (to test parsing and error handling)."""

    def __init__(self, *texts: str):
        self.texts = list(texts)
        self.calls = []

    def complete(self, messages, role="cheap", purpose="", json_mode=False, max_tokens=800, temperature=0.0,
                 model=None):
        from opportunity_assessment.llm import LLMResult

        self.calls.append({"messages": messages, "role": role, "purpose": purpose, "model": model})
        return LLMResult(text=self.texts.pop(0), model="scripted")


@pytest.fixture
def scripted():
    return ScriptedLLM

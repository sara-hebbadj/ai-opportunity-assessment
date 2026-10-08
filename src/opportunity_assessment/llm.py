"""The only module that talks to a language model.

- OpenRouterClient: real calls through the OpenAI-compatible SDK (OpenRouter).
- FakeLLM: a deterministic stand-in for tests, --dry-run and the offline demo. It is NOT a model:
  it returns fixed, simple answers so the pipeline can run end to end without a key.

Every call is written to a traces file (JSON lines) with model, tokens, cost (from OpenRouter's
`usage`), latency and outcome, so cost per item can be reported.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .config import EVALS_DIR, env, model_id


class LLMNotConfigured(RuntimeError):
    """Raised when OPENROUTER_API_KEY or a model ID is missing."""


class BudgetExceeded(RuntimeError):
    """Raised before a call when the run has already spent its budget (MAX_COST_PER_RUN_USD)."""


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""


@dataclass
class Tracer:
    """Appends one JSON line per model call and keeps the running cost of the run."""

    path: Path = field(default_factory=lambda: Path(env("TRACES_PATH") or EVALS_DIR / "traces.jsonl"))
    context: dict = field(default_factory=dict)  # e.g. {"run_id": ..., "item_id": ...}
    total_cost: float = 0.0
    calls: int = 0

    def log(self, purpose: str, result: LLMResult | None, outcome: str, model: str = "") -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            **self.context,
            "purpose": purpose,
            "model": result.model if result else model,
            "prompt_tokens": result.prompt_tokens if result else 0,
            "completion_tokens": result.completion_tokens if result else 0,
            "cost_usd": result.cost_usd if result else 0.0,
            "latency_ms": result.latency_ms if result else 0,
            "outcome": outcome,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.total_cost += record["cost_usd"]
        self.calls += 1


class OpenRouterClient:
    def __init__(self, tracer: Tracer | None = None, budget_usd: float | None = None):
        from openai import OpenAI  # imported here so tests never need network setup

        key = env("OPENROUTER_API_KEY")
        if not key:
            raise LLMNotConfigured("OPENROUTER_API_KEY is not set (see .env.example)")
        self.client = OpenAI(api_key=key, base_url=env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
        self.tracer = tracer or Tracer()
        self.budget_usd = budget_usd
        self.offline = False

    def complete(self, messages: list[dict], role: str = "cheap", purpose: str = "", json_mode: bool = False,
                 max_tokens: int = 800, temperature: float = 0.0, model: str | None = None) -> LLMResult:
        model = model or model_id(role)
        if not model:
            raise LLMNotConfigured(f"MODEL_{role.upper()} is not set")
        if self.budget_usd is not None and self.tracer.total_cost >= self.budget_usd:
            raise BudgetExceeded(f"run budget of US${self.budget_usd:.2f} reached")
        extra_body = {"usage": {"include": True}}  # OpenRouter returns the cost in usage
        # Reasoning models spend max_tokens on hidden "thinking" before the answer; earlier projects lost
        # JSON answers that way. These tasks are short, so ask for low effort (REASONING_EFFORT=default to skip).
        effort = env("REASONING_EFFORT", "low")
        if effort != "default":
            extra_body["reasoning"] = {"effort": effort}
        kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                  "extra_body": extra_body}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as error:  # log failed calls too, then let the caller decide
            self.tracer.log(purpose, None, f"error: {type(error).__name__}", model)
            raise
        usage = response.usage
        extra = getattr(usage, "model_extra", None) or {}
        result = LLMResult(
            text=response.choices[0].message.content or "",
            model=response.model or model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=float(extra.get("cost") or getattr(usage, "cost", 0) or 0),
            latency_ms=int((time.perf_counter() - start) * 1000),
            finish_reason=response.choices[0].finish_reason or "",
        )
        # "length" means the answer was cut off at max_tokens: say so in the trace instead of hiding it.
        self.tracer.log(purpose, result, "truncated" if result.finish_reason == "length" else "ok")
        return result


class FakeLLM:
    """Deterministic offline stand-in. Its outputs are labelled model='fake-offline' in traces.

    It gives the same simple answer every time (first theme, all scores 3, no problems found),
    so dry runs prove the plumbing works, never the quality.
    """

    def __init__(self, tracer: Tracer | None = None):
        self.tracer = tracer or Tracer()
        self.offline = True
        self.budget_usd = None

    def complete(self, messages: list[dict], role: str = "cheap", purpose: str = "", json_mode: bool = False,
                 max_tokens: int = 800, temperature: float = 0.0, model: str | None = None) -> LLMResult:
        prompt = "\n".join(m["content"] for m in messages)
        if purpose == "theme":
            text = json.dumps({"theme": "T1", "reason": "fake model"})
        elif purpose == "rubric":
            text = json.dumps({key: {"score": 3, "reason": "fake model"} for key in
                               ("value", "feasibility", "data_readiness", "risk", "time_to_value")})
        elif purpose == "precheck":
            text = json.dumps({"problems": []})
        else:
            text = "(offline placeholder)"
        result = LLMResult(text=text, model="fake-offline", prompt_tokens=len(prompt) // 4,
                           completion_tokens=len(text) // 4)
        self.tracer.log(purpose, result, "ok")
        return result


def make_client(offline: bool | None = None, tracer: Tracer | None = None, budget_usd: float | None = None):
    """Real client when a key exists (or offline=False), otherwise the FakeLLM."""
    if offline is None:
        offline = not env("OPENROUTER_API_KEY")
    return FakeLLM(tracer) if offline else OpenRouterClient(tracer, budget_usd)


def parse_json(text: str) -> dict:
    """Parse a JSON object even if the model wrapped it in ```json fences or added words around it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in model output")
    return json.loads(match.group(0))

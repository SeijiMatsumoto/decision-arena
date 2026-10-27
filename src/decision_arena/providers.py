from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx
import yaml
from pydantic import BaseModel

from .datasets import Example, Question

OPENROUTER = "https://openrouter.ai/api"
RETRY_STATUS = {429, 500, 502, 503, 524, 529}
MAX_ATTEMPTS = 8


class RateLimiter:
    """Spaces request starts so a model never exceeds `rpm` requests per minute."""

    def __init__(self, rpm: float):
        self.interval = 60 / rpm
        self.next_slot = 0.0
        self.lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self.lock:
            now = asyncio.get_running_loop().time()
            delay = max(0.0, self.next_slot - now)
            self.next_slot = max(now, self.next_slot) + self.interval
        await asyncio.sleep(delay)


_limiters: dict[str, RateLimiter] = {}


def retry_delay(response: httpx.Response, attempt: int) -> float:
    """Honor Retry-After when the server sends it; otherwise exponential backoff, capped."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header) + random.random()
        except ValueError:
            pass
    return min(2**attempt, 30) + random.random()


class ModelSpec(BaseModel):
    name: str
    provider: Literal["decisions", "llm", "mock"]
    model: str
    enabled: bool = True
    base_url: str | None = None
    api_key_env: str | None = "OPENROUTER_API_KEY"
    kind: Literal["decision", "llm"] | None = None  # derived from provider when unset
    accuracy: float = 0.85  # mock only
    mock_latency_ms: float = 100  # mock only
    mock_cost: float = 0.0  # mock only, USD per call
    price_in: float | None = None  # USD / 1M tokens; fallback when the API reports no cost
    price_out: float | None = None
    extra: dict[str, Any] = {}  # merged into the request body
    rpm: float | None = None  # client-side cap on requests per minute

    def model_post_init(self, _context: Any) -> None:
        if self.kind is None:
            self.kind = "llm" if self.provider == "llm" else "decision"

    def estimate_cost(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if self.price_in is None or input_tokens is None:
            return None
        return (input_tokens * self.price_in + (output_tokens or 0) * (self.price_out or 0)) / 1e6


class Decision(BaseModel):
    """A provider answer normalized across question types.

    label: predicted label ("true"/"false", a choice option, or a score level index).
    p_true: noul probability of yes (also used as a ranking score).
    score: score-question position, possibly between levels.
    """

    label: str | None = None
    p_true: float | None = None
    score: float | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None
    latency_ms: float = 0.0
    cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached: bool = False
    error: str | None = None


def load_models(
    path: Path, names: list[str] | None = None, all_models: bool = False
) -> list[ModelSpec]:
    specs = [ModelSpec.model_validate(m) for m in yaml.safe_load(path.read_text())["models"]]
    if all_models:
        return specs
    if not names:
        return [s for s in specs if s.enabled]
    by_name = {s.name: s for s in specs}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise SystemExit(f"Unknown model(s): {', '.join(unknown)}")
    return [by_name[n] for n in names]


def normalize_decision(question: Question, answer: dict[str, Any]) -> Decision:
    """Map a Decisions API answer onto the shared Decision shape."""
    if question.type == "noul":
        p = float(answer["noul"])
        return Decision(
            label="true" if p >= 0.5 else "false",
            p_true=p,
            confidence=max(p, 1 - p),
            probabilities={"true": p, "false": 1 - p},
        )
    if question.type == "choice":
        return Decision(
            label=str(answer["choice"]),
            confidence=answer.get("confidence"),
            probabilities=answer.get("probabilities"),
        )
    probabilities = answer.get("probabilities")
    score = float(answer["score"])
    if probabilities:
        label = max(probabilities, key=probabilities.get)
    else:
        label = str(min(max(round(score), 0), len(question.criteria) - 1))
    return Decision(
        label=label,
        score=score,
        confidence=answer.get("confidence"),
        probabilities=probabilities,
    )


class Provider:
    def __init__(self, spec: ModelSpec, cache_dir: Path, client: httpx.AsyncClient):
        self.spec = spec
        self.cache_dir = cache_dir
        self.client = client

    async def decide(self, question: Question, example: Example) -> Decision:
        raise NotImplementedError

    # Shared HTTP plumbing: disk cache keyed by the exact request, plus retry on transient errors.
    async def _post_cached(self, url: str, body: dict[str, Any]) -> tuple[dict, float, bool]:
        key = hashlib.sha256(json.dumps([url, body], sort_keys=True).encode()).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            hit = json.loads(path.read_text())
            return hit["response"], hit["latency_ms"], True

        headers = {"Content-Type": "application/json"}
        if self.spec.api_key_env:
            api_key = os.environ.get(self.spec.api_key_env)
            if not api_key:
                raise RuntimeError(f"{self.spec.api_key_env} is not set")
            headers["Authorization"] = f"Bearer {api_key}"

        limiter = None
        if self.spec.rpm:
            limiter = _limiters.setdefault(self.spec.name, RateLimiter(self.spec.rpm))

        for attempt in range(MAX_ATTEMPTS):
            if limiter:
                await limiter.wait()
            started = perf_counter()
            response = await self.client.post(url, json=body, headers=headers)
            latency_ms = (perf_counter() - started) * 1000
            if response.status_code in RETRY_STATUS and attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(retry_delay(response, attempt))
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:300]}")
            payload = response.json()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"response": payload, "latency_ms": latency_ms}))
            return payload, latency_ms, False
        raise AssertionError("unreachable")


class DecisionsProvider(Provider):
    """Any model behind OpenRouter's Decisions API, or a Jev-compatible server via base_url."""

    async def decide(self, question: Question, example: Example) -> Decision:
        url = self.spec.base_url or f"{OPENROUTER}/alpha/decisions"
        body = {
            "model": self.spec.model,
            "state": example.state,
            "questions": {"q": question.to_api()},
            **self.spec.extra,
        }
        payload, latency_ms, cached = await self._post_cached(url, body)
        decision = normalize_decision(question, payload["answers"]["q"])
        usage = payload.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = self.spec.estimate_cost(usage.get("input_tokens"), usage.get("output_tokens"))
        return decision.model_copy(
            update={
                "latency_ms": latency_ms,
                "cached": cached,
                "cost": cost,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
        )


def llm_answer_schema(question: Question) -> dict[str, Any]:
    if question.type == "noul":
        properties = {"probability_true": {"type": "number", "minimum": 0, "maximum": 1}}
    elif question.type == "choice":
        properties = {
            "choice": {"type": "string", "enum": question.labels},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        }
    else:
        properties = {"level": {"type": "integer", "enum": list(range(len(question.criteria)))}}
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def llm_prompt(question: Question, example: Example) -> str:
    if question.type == "score":
        criteria = "\n".join(f"{i}: {text}" for i, text in enumerate(question.criteria))
    else:
        criteria = "\n".join(f"{key}: {text}" for key, text in question.criteria.items())
    state = example.state if isinstance(example.state, str) else json.dumps(example.state, indent=2)
    return (
        f"Instructions: {question.instructions}\n\nCriteria:\n{criteria}\n\n"
        f"Input:\n{state}\n\nAnswer only with the JSON object."
    )


class LLMProvider(Provider):
    """Generative baseline: a chat model forced into the same answer space via JSON schema."""

    async def decide(self, question: Question, example: Example) -> Decision:
        body = {
            "model": self.spec.model,
            "messages": [
                {"role": "system", "content": "You are a precise classifier."},
                {"role": "user", "content": llm_prompt(question, example)},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "decision",
                    "strict": True,
                    "schema": llm_answer_schema(question),
                },
            },
            **self.spec.extra,
        }
        payload, latency_ms, cached = await self._post_cached(
            self.spec.base_url or f"{OPENROUTER}/v1/chat/completions", body
        )
        parsed = json.loads(payload["choices"][0]["message"]["content"])
        if question.type == "noul":
            answer = {"noul": parsed["probability_true"]}
        elif question.type == "choice":
            answer = {"choice": parsed["choice"], "confidence": parsed.get("confidence")}
        else:
            answer = {"score": parsed["level"]}
        decision = normalize_decision(question, answer)
        usage = payload.get("usage") or {}
        cost = usage.get("cost")
        if cost is None:
            cost = self.spec.estimate_cost(usage.get("prompt_tokens"), usage.get("completion_tokens"))
        return decision.model_copy(
            update={
                "latency_ms": latency_ms,
                "cached": cached,
                "cost": cost,
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            }
        )


class MockProvider(Provider):
    """Deterministic noisy oracle: right with probability `accuracy`, for offline pipeline runs."""

    async def decide(self, question: Question, example: Example) -> Decision:
        rng = random.Random(f"{self.spec.name}:{example.id}")
        correct = rng.random() < self.spec.accuracy
        labels = question.labels
        label = (
            example.expected_label
            if correct
            else rng.choice([lbl for lbl in labels if lbl != example.expected_label])
        )
        confidence = rng.uniform(0.55, 0.99) if correct else rng.uniform(0.5, 0.8)
        if question.type == "noul":
            answer: dict[str, Any] = {"noul": confidence if label == "true" else 1 - confidence}
        elif question.type == "choice":
            rest = (1 - confidence) / (len(labels) - 1)
            probabilities = {lbl: confidence if lbl == label else rest for lbl in labels}
            answer = {"choice": label, "confidence": confidence, "probabilities": probabilities}
        else:
            answer = {"score": float(label)}
        latency_ms = self.spec.mock_latency_ms * rng.uniform(0.6, 1.6)
        await asyncio.sleep(latency_ms / 10_000)
        decision = normalize_decision(question, answer)
        return decision.model_copy(update={"latency_ms": latency_ms, "cost": self.spec.mock_cost})


PROVIDERS: dict[str, type[Provider]] = {
    "decisions": DecisionsProvider,
    "llm": LLMProvider,
    "mock": MockProvider,
}


def build_provider(spec: ModelSpec, cache_dir: Path, client: httpx.AsyncClient) -> Provider:
    return PROVIDERS[spec.provider](spec, cache_dir, client)

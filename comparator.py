"""Provider wrappers that return a uniform result shape."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class CallResult:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    response_text: str
    error: Optional[str] = None


def _cost(prices: dict, provider: str, model: str, inp: int, out: int) -> float:
    rates = prices.get(provider, {}).get(model)
    if not rates:
        return 0.0
    return (inp * rates["input"] + out * rates["output"]) / 1_000_000.0


def call_anthropic(api_key: str, model: str, prompt: str, max_tokens: int, prices: dict) -> CallResult:
    try:
        from anthropic import Anthropic
    except ImportError as e:
        return CallResult("anthropic", model, 0, 0, 0.0, 0.0, "", f"anthropic SDK not installed: {e}")

    client = Anthropic(api_key=api_key)
    t0 = time.perf_counter()
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return CallResult("anthropic", model, 0, 0, 0.0, time.perf_counter() - t0, "", str(e))
    latency = time.perf_counter() - t0

    text = "".join(getattr(b, "text", "") for b in msg.content)
    inp = msg.usage.input_tokens
    out = msg.usage.output_tokens
    return CallResult(
        provider="anthropic",
        model=model,
        input_tokens=inp,
        output_tokens=out,
        cost_usd=_cost(prices, "anthropic", model, inp, out),
        latency_s=latency,
        response_text=text,
    )


def call_openai(api_key: str, model: str, prompt: str, max_tokens: int, prices: dict) -> CallResult:
    try:
        from openai import OpenAI
    except ImportError as e:
        return CallResult("openai", model, 0, 0, 0.0, 0.0, "", f"openai SDK not installed: {e}")

    client = OpenAI(api_key=api_key)
    t0 = time.perf_counter()
    try:
        # o-series reasoning models use max_completion_tokens and don't accept temperature.
        kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        if model.startswith(("o1", "o3", "o4")):
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        return CallResult("openai", model, 0, 0, 0.0, time.perf_counter() - t0, "", str(e))
    latency = time.perf_counter() - t0

    text = resp.choices[0].message.content or ""
    inp = resp.usage.prompt_tokens
    out = resp.usage.completion_tokens
    return CallResult(
        provider="openai",
        model=model,
        input_tokens=inp,
        output_tokens=out,
        cost_usd=_cost(prices, "openai", model, inp, out),
        latency_s=latency,
        response_text=text,
    )

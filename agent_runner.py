"""Run a LangChain agent, print its tool calls as they happen, and count tokens and cost."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

ROOT = Path(__file__).parent
REQUIRED_MODEL = "claude-sonnet-5"
# USD per million tokens for claude-sonnet-5. Cache prices follow the usual multipliers.
PRICE_INPUT = 2.00
PRICE_OUTPUT = 10.00
PRICE_CACHE_READ = PRICE_INPUT * 0.1
PRICE_CACHE_WRITE = PRICE_INPUT * 1.25


def chat_model() -> ChatAnthropic:
    """The model from .env. Refuses to run with anything but claude-sonnet-5."""
    load_dotenv(ROOT / ".env")
    model = os.environ.get("ANTHROPIC_MODEL", "")
    if model != REQUIRED_MODEL:
        sys.exit(f"Refusing to run: ANTHROPIC_MODEL is {model!r}, it must be {REQUIRED_MODEL!r}.")
    return ChatAnthropic(model=model, max_tokens=16000)


def new_usage() -> dict:
    return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def add_usage(total: dict, more: dict) -> dict:
    return {k: total.get(k, 0) + more.get(k, 0) for k in new_usage()}


def cost(usage: dict) -> float:
    # usage_metadata input_tokens includes cached tokens; split them out for pricing.
    uncached = usage["input"] - usage["cache_read"] - usage["cache_write"]
    return (uncached * PRICE_INPUT + usage["output"] * PRICE_OUTPUT
            + usage["cache_read"] * PRICE_CACHE_READ
            + usage["cache_write"] * PRICE_CACHE_WRITE) / 1_000_000


def format_usage(usage: dict) -> str:
    return (f"Tokens: {usage['input']:,} input ({usage['cache_read']:,} cache read, "
            f"{usage['cache_write']:,} cache write), {usage['output']:,} output. "
            f"Estimated cost: ${cost(usage):.4f}")


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def run_agent(agent, message: str, echo: bool = True) -> tuple[str, dict]:
    """Stream an agent run. Returns (final reply, token usage)."""
    usage, final = new_usage(), ""
    for update in agent.stream({"messages": [{"role": "user", "content": message}]},
                               stream_mode="updates"):
        for node in update.values():
            for msg in (node or {}).get("messages", []):
                if msg.type == "ai":
                    meta = msg.usage_metadata or {}
                    details = meta.get("input_token_details") or {}
                    usage["cache_read"] += details.get("cache_read", 0) or 0
                    usage["cache_write"] += details.get("cache_creation", 0) or 0
                    usage["input"] += meta.get("input_tokens", 0) or 0
                    usage["output"] += meta.get("output_tokens", 0) or 0
                    if echo:
                        for call in msg.tool_calls:
                            print(f"→ {call['name']}({json.dumps(call['args'])[:200]})", flush=True)
                    if not msg.tool_calls:
                        final = msg.text
                elif msg.type == "tool" and echo:
                    print(f"  ← {_short(msg.content)}", flush=True)
    return final, usage

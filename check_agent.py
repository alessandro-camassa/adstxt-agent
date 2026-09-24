"""Check agent: checks ads.txt for our domains and writes a brief.

Usage: python check_agent.py "check the top 50 domains and tell me what you found"
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

from tools import check_domain, check_domains, query_results, summarise, write_brief

ROOT = Path(__file__).parent
REQUIRED_MODEL = "claude-sonnet-5"
# USD per million tokens for claude-sonnet-5. Cache prices follow the usual multipliers.
PRICE_INPUT = 2.00
PRICE_OUTPUT = 10.00
PRICE_CACHE_READ = PRICE_INPUT * 0.1
PRICE_CACHE_WRITE = PRICE_INPUT * 1.25


def build_agent():
    load_dotenv(ROOT / ".env")
    model = os.environ.get("ANTHROPIC_MODEL", "")
    if model != REQUIRED_MODEL:
        sys.exit(f"Refusing to run: ANTHROPIC_MODEL is {model!r}, it must be {REQUIRED_MODEL!r}.")
    return create_agent(
        ChatAnthropic(model=model, max_tokens=16000),
        tools=[check_domains, check_domain, query_results, summarise, write_brief],
        system_prompt=(ROOT / "prompts" / "check.md").read_text(),
    )


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    agent = build_agent()
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
    final = ""

    for update in agent.stream({"messages": [{"role": "user", "content": sys.argv[1]}]},
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
                    for call in msg.tool_calls:
                        print(f"→ {call['name']}({json.dumps(call['args'])[:200]})", flush=True)
                    if not msg.tool_calls:
                        final = msg.text
                elif msg.type == "tool":
                    print(f"  ← {_short(msg.content)}", flush=True)

    print("\n" + final)

    # usage_metadata input_tokens includes cached tokens; split them out for pricing.
    uncached = usage["input"] - usage["cache_read"] - usage["cache_write"]
    cost = (uncached * PRICE_INPUT + usage["output"] * PRICE_OUTPUT
            + usage["cache_read"] * PRICE_CACHE_READ
            + usage["cache_write"] * PRICE_CACHE_WRITE) / 1_000_000
    print(f"\nTokens: {usage['input']:,} input ({usage['cache_read']:,} cache read, "
          f"{usage['cache_write']:,} cache write), {usage['output']:,} output")
    print(f"Estimated cost: ${cost:.4f}")


if __name__ == "__main__":
    main()

"""Check agent: checks ads.txt for our domains and writes a brief.

Usage: python check_agent.py "check the top 50 domains and tell me what you found"
"""

import sys
from pathlib import Path

from langchain.agents import create_agent

from agent_runner import chat_model, format_usage, run_agent
from tools import check_domain, check_domains, query_results, summarise, write_brief

ROOT = Path(__file__).parent
ALL_TOOLS = [check_domains, check_domain, query_results, summarise, write_brief]


def build_agent(tools=None):
    """The checking agent. The graph passes a subset of tools for each node."""
    return create_agent(
        chat_model(),
        tools=tools or ALL_TOOLS,
        system_prompt=(ROOT / "prompts" / "check.md").read_text(),
    )


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    final, usage = run_agent(build_agent(), sys.argv[1])
    print("\n" + final)
    print("\n" + format_usage(usage))


if __name__ == "__main__":
    main()

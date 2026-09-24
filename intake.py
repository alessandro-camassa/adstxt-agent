"""Intake step: the agent inspects and stages an Excel file, then code commits it."""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

from tools import commit_import, import_summary, inspect_excel, latest_import_id, stage_import

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def build_agent():
    model = ChatAnthropic(model=os.environ["ANTHROPIC_MODEL"], max_tokens=4096)
    system_prompt = (ROOT / "prompts" / "intake.md").read_text()
    return create_agent(model, tools=[inspect_excel, stage_import], system_prompt=system_prompt)


def run_intake(path: str | Path) -> dict:
    """Let the agent stage the file, then commit in plain code if the numbers reconcile."""
    path = str(Path(path).resolve())
    before = latest_import_id() or 0

    result = build_agent().invoke(
        {"messages": [{"role": "user", "content": f"Import this Excel file: {path}"}]}
    )
    agent_reply = result["messages"][-1].text

    import_id = latest_import_id()
    if not import_id or import_id <= before:
        return {"staged": False, "agent_reply": agent_reply}

    return {
        "staged": True,
        "agent_reply": agent_reply,
        **import_summary(import_id),
        "commit": commit_import(import_id),
    }

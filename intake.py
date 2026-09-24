"""Intake step: the agent inspects and stages an Excel file, then code commits it."""

from pathlib import Path

from langchain.agents import create_agent

from agent_runner import chat_model, run_agent
from tools import commit_import, import_summary, inspect_excel, latest_import_id, stage_import

ROOT = Path(__file__).parent


def build_agent():
    system_prompt = (ROOT / "prompts" / "intake.md").read_text()
    return create_agent(chat_model(), tools=[inspect_excel, stage_import], system_prompt=system_prompt)


def stage_file(path: str | Path, echo: bool = False) -> dict:
    """Let the intake agent inspect and stage the file. Nothing is committed here."""
    path = str(Path(path).resolve())
    before = latest_import_id() or 0
    agent_reply, usage = run_agent(build_agent(), f"Import this Excel file: {path}", echo=echo)

    import_id = latest_import_id()
    if not import_id or import_id <= before:
        return {"staged": False, "agent_reply": agent_reply, "usage": usage}
    return {"staged": True, "agent_reply": agent_reply, "usage": usage, **import_summary(import_id)}


def run_intake(path: str | Path) -> dict:
    """Stage the file with the agent, then commit in plain code if the numbers reconcile."""
    result = stage_file(path)
    if result["staged"]:
        result["commit"] = commit_import(result["import_id"])
    return result

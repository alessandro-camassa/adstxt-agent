"""The whole workflow as one LangGraph: intake -> gate -> check -> report.

Usage: python graph.py <spreadsheet.xlsx> --top 50
"""

import argparse
import sys
import uuid
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent_runner import add_usage, format_usage, run_agent
from check_agent import build_agent as build_check_agent
from intake import stage_file
from tools import (brief_path, check_domain, check_domains, commit_import, query_results,
                   summarise, write_brief)

NODE_LABELS = {
    "intake": "Intake: the agent reads and stages the spreadsheet",
    "gate": "Gate: code checks the numbers reconcile before saving",
    "check": "Check: the agent checks ads.txt for the top domains",
    "report": "Report: the agent writes the brief",
}


class State(TypedDict, total=False):
    path: str                       # spreadsheet to import
    top_n: int                      # how many domains to check
    intake: dict                    # what the intake agent staged
    gate: dict                      # commit_import's verdict
    stopped: bool                   # True if the workflow stopped early
    stop_message: str               # why it stopped
    check_reply: str                # the checking agent's summary of the check
    brief: str                      # today's brief, as saved in results/
    brief_path: str
    usage: Annotated[dict, add_usage]  # tokens summed across every agent call


# ---------- nodes ----------

def intake_node(state: State) -> State:
    result = stage_file(state["path"], echo=True)
    usage = result.pop("usage")
    if not result["staged"]:
        return {"intake": result, "usage": usage, "stopped": True,
                "stop_message": "Stopped after intake: the intake agent did not stage the file.\n\n"
                                + result["agent_reply"]}
    return {"intake": result, "usage": usage}


def gate_node(state: State) -> State:
    """Plain code, no model: commit only if rows and bid requests reconcile."""
    verdict = commit_import(state["intake"]["import_id"])
    if not verdict["committed"]:
        return {"gate": verdict, "stopped": True,
                "stop_message": "Stopped at the gate: the numbers don't reconcile, so nothing was saved "
                                "and no domains were checked.\n\n"
                                + "\n".join(f"- {r}" for r in verdict["reasons"])}
    return {"gate": verdict}


def check_node(state: State) -> State:
    top_n = int(state.get("top_n") or 50)
    agent = build_check_agent(tools=[check_domains, check_domain])
    reply, usage = run_agent(agent, (
        f"Check the top {top_n} domains by bid requests: call check_domains with top_n={top_n} and "
        "offset=0, then re-check each error result once with check_domain. Do not write the brief; "
        "the next step does that. Reply with the counts by status."))
    return {"check_reply": reply, "usage": usage}


def report_node(state: State) -> State:
    path = brief_path()
    before = path.stat().st_mtime if path.exists() else None
    agent = build_check_agent(tools=[summarise, query_results, write_brief])
    _, usage = run_agent(agent, (
        "The check has finished and the results are in the database. Write today's brief from "
        "summarise and query_results, in the brief shape from your instructions, and save it with "
        "write_brief. Reply with the headline."))
    if not path.exists() or path.stat().st_mtime == before:
        return {"usage": usage, "stopped": True,
                "stop_message": "Stopped at report: the agent did not save a brief."}
    return {"usage": usage, "brief": path.read_text(encoding="utf-8"), "brief_path": str(path)}


def _after(node_name: str, next_node: str):
    def route(state: State) -> str:
        return END if state.get("stopped") else next_node
    route.__name__ = f"after_{node_name}"
    return route


def build_graph(pause_before_check: bool = False):
    """The page pauses before check (the button resumes it); the command line runs straight through."""
    g = StateGraph(State)
    g.add_node("intake", intake_node)
    g.add_node("gate", gate_node)
    g.add_node("check", check_node)
    g.add_node("report", report_node)
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _after("intake", "gate"), ["gate", END])
    g.add_conditional_edges("gate", _after("gate", "check"), ["check", END])
    g.add_edge("check", "report")
    g.add_edge("report", END)
    if pause_before_check:
        return g.compile(checkpointer=InMemorySaver(), interrupt_before=["check"])
    return g.compile(checkpointer=InMemorySaver())


def run_steps(graph, graph_input, config):
    """Run the graph, yielding ("start", node) and ("end", node) as each node runs."""
    for mode, chunk in graph.stream(graph_input, config, stream_mode=["tasks"]):
        if mode == "tasks" and chunk.get("name") in NODE_LABELS:
            yield ("end" if "result" in chunk or "error" in chunk else "start", chunk["name"])


def new_config() -> dict:
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spreadsheet")
    parser.add_argument("--top", type=int, default=50, help="how many domains to check (default 50)")
    args = parser.parse_args()

    graph, config = build_graph(), new_config()
    for event, node in run_steps(graph, {"path": args.spreadsheet, "top_n": args.top}, config):
        print(f"\n{'▶' if event == 'start' else '✓'} {NODE_LABELS[node]}", flush=True)

    state = graph.get_state(config).values
    print()
    if state.get("stopped"):
        print(state["stop_message"])
    else:
        print(state["brief"])
        print(f"\nSaved to {state['brief_path']}")
    print("\n" + format_usage(add_usage({}, state.get("usage") or {})))
    sys.exit(1 if state.get("stopped") else 0)


if __name__ == "__main__":
    main()

"""Upload page: dropping a .xlsx runs intake and the gate; a button runs check and report."""

import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from agent_runner import add_usage, format_usage
from graph import NODE_LABELS, build_graph, new_config, run_steps

UPLOADS = Path(__file__).parent / "data" / "uploads"

st.set_page_config(page_title="ads.txt intake", page_icon="📄")
st.title("Upload domains")


def run_with_progress(graph_input, title: str) -> None:
    """Run the graph until it pauses or ends, showing each node as it runs."""
    graph, config = st.session_state.graph, st.session_state.config
    with st.status(title, expanded=True) as status:
        for event, node in run_steps(graph, graph_input, config):
            if event == "start":
                status.update(label=f"Running: {NODE_LABELS[node]}…")
                st.write(f"▶ {NODE_LABELS[node]}")
            else:
                st.write(f"✓ {node} finished")
        state = graph.get_state(config).values
        status.update(label="Stopped" if state.get("stopped") else "Done",
                      state="error" if state.get("stopped") else "complete", expanded=False)


uploaded = st.file_uploader("Drop an Excel file", type=["xlsx"])

if uploaded is not None:
    # Streamlit reruns the script on every interaction; only run the workflow once per upload.
    if st.session_state.get("file_id") != uploaded.file_id:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(uploaded.name).name)
        path = UPLOADS / f"{datetime.now():%Y%m%d-%H%M%S}_{safe_name}"
        path.write_bytes(uploaded.getvalue())
        st.session_state.graph = build_graph(pause_before_check=True)
        st.session_state.config = new_config()
        st.session_state.file_id = uploaded.file_id
        run_with_progress({"path": str(path), "top_n": 50}, "Intake and gate")

    graph, config = st.session_state.graph, st.session_state.config
    state = graph.get_state(config).values
    intake = state.get("intake") or {}

    if intake.get("staged"):
        st.subheader("Column mapping")
        st.table({"Field": list(intake["mapping"]), "Column": list(intake["mapping"].values())})
        st.caption(intake["agent_reply"])

        rejected = intake["rejected_rows"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows read", f"{intake['rows_read']:,}")
        c2.metric("Accepted", f"{intake['accepted']:,}")
        c3.metric("Rejected", f"{len(rejected):,}")

    gate = state.get("gate") or {}
    if gate.get("committed"):
        checks = gate["checks"]
        st.success(
            f"Gate passed: {checks['rows_read']:,} rows read = accepted + rejected, and bid requests "
            f"match the file's total of {checks['bid_requests_file_total']:,.0f}. "
            f"{intake['accepted']:,} domains saved."
        )
    if state.get("stopped") and not state.get("brief"):
        st.error(state["stop_message"])

    if intake.get("staged") and intake["rejected_rows"]:
        with st.expander(f"Rejected rows ({len(intake['rejected_rows'])})"):
            st.dataframe(
                [{"Row": r["row_number"], "Domain": r["raw_domain"], "Bid requests": r["bid_requests"],
                  "Publisher": r["publisher"], "Reason": r["reason"]} for r in intake["rejected_rows"]],
                hide_index=True, use_container_width=True,
            )

    if gate.get("committed"):
        st.divider()
        top_n = st.number_input("N", min_value=1, max_value=2000, value=50, step=10)
        if st.button(f"Check the top {top_n} domains", type="primary"):
            # Resume from just after the gate, so the button can be pressed again with a new N.
            graph.update_state(config, {"top_n": int(top_n), "stopped": False, "brief": ""},
                               as_node="gate")
            run_with_progress(None, "Check and report")
            state = graph.get_state(config).values
            if state.get("stopped"):
                st.error(state["stop_message"])

        if state.get("brief"):
            st.caption(f"{format_usage(add_usage({}, state.get('usage') or {}))} · saved to "
                       f"{Path(state['brief_path']).name}")
            st.markdown(state["brief"])

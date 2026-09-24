"""Excel uploader: drop a .xlsx file, the intake step imports it."""

import re
from datetime import datetime
from pathlib import Path

import streamlit as st

from intake import run_intake

UPLOADS = Path(__file__).parent / "data" / "uploads"

st.set_page_config(page_title="ads.txt intake", page_icon="📄")
st.title("Upload domains")

uploaded = st.file_uploader("Drop an Excel file", type=["xlsx"])

if uploaded is not None:
    # Streamlit reruns the script on every interaction; only import each upload once.
    if st.session_state.get("file_id") != uploaded.file_id:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(uploaded.name).name)
        path = UPLOADS / f"{datetime.now():%Y%m%d-%H%M%S}_{safe_name}"
        path.write_bytes(uploaded.getvalue())
        with st.spinner("Reading the file…"):
            st.session_state.result = run_intake(path)
        st.session_state.file_id = uploaded.file_id

    result = st.session_state.result

    if not result["staged"]:
        st.error("The agent did not stage this file.")
        st.write(result["agent_reply"])
        st.stop()

    st.subheader("Column mapping")
    st.table({"Field": list(result["mapping"]), "Column": list(result["mapping"].values())})
    st.caption(result["agent_reply"])

    rejected = result["rejected_rows"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows read", f"{result['rows_read']:,}")
    c2.metric("Accepted", f"{result['accepted']:,}")
    c3.metric("Rejected", f"{len(rejected):,}")

    commit = result["commit"]
    checks = commit.get("checks", {})
    if commit["committed"]:
        st.success(
            f"Numbers reconciled: {checks['rows_read']:,} rows read = accepted + rejected, and "
            f"bid requests match the file's total of {checks['bid_requests_file_total']:,.0f}. "
            f"{result['accepted']:,} domains saved."
        )
    else:
        st.error("Numbers did not reconcile, so nothing was saved.\n\n"
                 + "\n\n".join(f"- {r}" for r in commit["reasons"]))

    if rejected:
        st.subheader("Rejected rows")
        st.dataframe(
            [{"Row": r["row_number"], "Domain": r["raw_domain"], "Bid requests": r["bid_requests"],
              "Publisher": r["publisher"], "Reason": r["reason"]} for r in rejected],
            hide_index=True, use_container_width=True,
        )

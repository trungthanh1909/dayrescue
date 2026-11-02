"""Concise conflict presentation with complete deterministic details."""

import streamlit as st

from core.models import DayContext, ValidationIssue


def show_conflicts(context: DayContext, conflicts: list[ValidationIssue]) -> None:
    names = {a.id: f"{a.title} ({a.id})" for a in context.activities}
    groups = {}
    for issue in conflicts:
        groups.setdefault(issue.code, []).append(issue)
    st.caption(f"{len(conflicts)} hard conflicts across {len(groups)} conflict types. All must be resolved.")
    for code, issues in groups.items():
        ids = dict.fromkeys(key for issue in issues for key in issue.activity_ids)
        st.write(f"**{code}**: {len(issues)} conflicts")
        st.caption("Affected activities: " + ", ".join(names.get(key, key) for key in ids))
    with st.expander("Full hard-conflict details", expanded=False):
        for issue in conflicts:
            st.write(f"**{issue.code}**: {issue.message}")
            st.caption("Activities: " + ", ".join(names.get(key, key) for key in issue.activity_ids))

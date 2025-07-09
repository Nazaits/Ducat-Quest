import streamlit as st
from db import query
import datetime

st.title("✅ Completed Tasks")

tasks = query(
    "SELECT name, description, type, last_completed, initial_ducat_value FROM tasks WHERE completed=1 ORDER BY last_completed DESC"
)

if not tasks:
    st.info("No completed tasks yet. Go complete some!")
else:
    for name, description, typ, last_completed, ducats in tasks:
        with st.expander(f"{name} [{typ.capitalize()}] — {ducats} 💰"):
            date, time = last_completed.split('T')
            print(date, time)
            st.write(f"**Completed on:** {last_completed[:-10].replace('T', ' ') or 'Unknown'}")
            st.write(f"**Description:**\n{description or '*No description*'}")

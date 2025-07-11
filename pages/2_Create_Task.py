# pages/2_Create_Task.py
import streamlit as st
from utils.util import add_task

st.header("Create a Task")

desc = st.text_area("Task Description", height=100)
typ = st.selectbox("Task Type", ["one-time", "daily", "weekly"], index=0)
if st.button("Create Task"):
    with st.spinner("Creating Task..."):
        add_task(desc, typ)
        st.success("Task created and valued by AI!")

# pages/2_Create_Task.py
import streamlit as st
import logic

st.header("Create a Task")

desc = st.text_area("Task Description", height=100)
typ = st.selectbox("Task Type", ["one-time", "daily", "weekly"], index=0)
if st.button("Create Task"):
    with st.spinner("Creating Task..."):
        logic.add_task(desc, typ)
        st.success("Task created and valued by AI!")

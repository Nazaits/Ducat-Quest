import streamlit as st, db
from utils.util import show_ducat_bar, show_timers, smart_ducat_str
from utils.llm import llm_evaluate_report_and_award
from datetime import datetime, timedelta

def get_last_8am(now=None):
    now = now or datetime.now()
    eight_am_today = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now < eight_am_today:
        return (eight_am_today - timedelta(days=1))
    return eight_am_today

def get_last_monday(now=None):
    now = now or datetime.now()
    last_monday = (now - timedelta(days=now.weekday())).replace(hour=8, minute=0, second=0, microsecond=0)
    if now < last_monday:
        last_monday -= timedelta(days=7)
    return last_monday

def reset_daily_and_weekly_tasks():
    now = datetime.now()
    last_8am = get_last_8am(now)
    last_monday = get_last_monday(now)
    
    # DAILY TASKS
    daily_tasks = db.query("SELECT id, last_completed FROM tasks WHERE type='daily'")
    for tid, last_completed in daily_tasks:
        if last_completed:
            last_dt = datetime.fromisoformat(last_completed)
        else:
            last_dt = datetime.min
        if last_dt < last_8am:
            db.query(
                "UPDATE tasks SET completed=0, current_ducat_value=initial_ducat_value, last_completed=? WHERE id=?",
                (now.isoformat(), tid), commit=True
            )
    
    # WEEKLY TASKS
    weekly_tasks = db.query("SELECT id, last_completed FROM tasks WHERE type='weekly'")
    for tid, last_completed in weekly_tasks:
        if last_completed:
            last_dt = datetime.fromisoformat(last_completed)
        else:
            last_dt = datetime.min
        if last_dt < last_monday:
            db.query(
                "UPDATE tasks SET completed=0, current_ducat_value=initial_ducat_value, last_completed=? WHERE id=?",
                (now.isoformat(), tid), commit=True
            )

# Call this at the top of your Task List page
reset_daily_and_weekly_tasks()
show_ducat_bar()
show_timers(page="tasks")

st.header("📝 Task List")

tasks = db.query(
    "SELECT id, name, type, completed, current_ducat_value, initial_ducat_value, last_completed, description FROM tasks WHERE completed = false ORDER BY type, created_at"
)

if not tasks:
    st.info("No tasks yet—add some!")
else:
    current_type = None
    for tid, name, typ, completed, curr_val, init_val, last_completed, description in tasks:
        if typ != current_type:
            st.subheader(f"{typ.capitalize()} Tasks")
            # logic.show_timers(page=typ)
            current_type = typ
        c_name, c_val, c_status, c_button = st.columns([4, 2, 1, 1])
        with c_name.expander(f"{name}"):
            st.write(description or "*No description*")
        c_val.write(f"{smart_ducat_str(init_val-curr_val)} / {smart_ducat_str(init_val)} 💰")
        c_status.write("✅" if completed else "⏳")
        if not completed:
            if c_button.button("✅ Done", key=f"done_{tid}"):
                now = datetime.now().isoformat()
                # Award all remaining ducats for this task
                db.query(
                    "UPDATE tasks SET completed=1, last_completed=?, current_ducat_value=0 WHERE id=?",
                    (now, tid), commit=True
                )
                db.query("UPDATE user_stats SET value=value+? WHERE key='ducats_earned'", (curr_val,), commit=True)
                st.session_state["show_ducat_award"] = {
                    "amount": curr_val,
                    "source": "button",
                    "details": [(name, curr_val)]
                }
                st.rerun()

if "show_ducat_award" in st.session_state:
    data = st.session_state["show_ducat_award"]
    amount = data["amount"]
    details = data["details"]
    source = data["source"]
    if source == "button":
        st.success(f"You were awarded {amount} ducats for completing a task! 🎉")
    elif source == "report":
        st.success(f"You were awarded {amount} ducats from your report! 🎉")
        if len(details) > 1:
            st.markdown(
                "\n".join([f"- **{n}**: {a} ducats" for n, a in details])
            )
    # Only show once
    del st.session_state["show_ducat_award"]

st.markdown("---")
st.subheader("📋 Daily Report")
report_text = st.text_area("What did you do today?", height=150)
if st.button("Submit Report"):
    with st.spinner("Processing Report..."):
        results, total = llm_evaluate_report_and_award(report_text)
        if total > 0:
            for tid, awarded, reason, completed in results:
                task_name = db.query("SELECT name FROM tasks WHERE id=?", (tid,))[0][0]
                # st.info(f"Task: {task_name} — Awarded: {awarded} ducats. {'Completed!' if completed else ''} Reason: {reason}")
            st.session_state["show_ducat_award"] = {
                "amount": total,
                "source": "report",
                "details": [
                    (db.query("SELECT name FROM tasks WHERE id=?", (tid,))[0][0], awarded)
                    for tid, awarded, reason, completed in results
                ]
            }
            st.rerun()
        else:
            st.warning("No ducats awarded for this report. Try to be more specific or work on your tasks!")
        
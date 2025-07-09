import streamlit as st
import db, logic

def update_conversion_rate(new_rate):
    old_rate = float(db.query("SELECT value FROM user_stats WHERE key='conversion_rate'")[0][0])
    if old_rate == new_rate:
        return
    # Update task values
    scale = new_rate / old_rate
    db.query("UPDATE tasks SET current_ducat_value = ROUND(current_ducat_value * ?, 2), initial_ducat_value = ROUND(initial_ducat_value * ?, 2)", (scale, scale), commit=True)
    # Update shop item values
    db.query("UPDATE shop_items SET ducat_value = ROUND(ducat_value * ?, 2)", (scale,), commit=True)
    # Update earned/spent values
    db.query("UPDATE user_stats SET value = ROUND(value * ?, 2) WHERE key='ducats_earned'", (scale,), commit=True)
    db.query("UPDATE user_stats SET value = ROUND(value * ?, 2) WHERE key='ducats_spent'", (scale,), commit=True)
    # Update the stored conversion rate
    db.query("UPDATE user_stats SET value=? WHERE key='conversion_rate'", (str(new_rate),), commit=True)

def smart_float_str(x):
    return f"{x:.2f}".rstrip('0').rstrip('.') if '.' in f"{x:.2f}" else f"{x:.2f}"

st.header("💸 Manage Your Budget")

logic.show_ducat_bar()
# Show current budget
budget = int(db.query("SELECT value FROM user_stats WHERE key='budget'")[0][0])
st.write(f"**Current budget:** {budget}")

# Add or subtract budget
adjust = st.number_input("Adjust budget by (+/-):", value=0, step=1)
if st.button("Apply Change"):
    with st.spinner("Adjusting Budget..."):
        new_budget = budget + adjust
        db.query(
            "UPDATE user_stats SET value=? WHERE key='budget'", 
            (str(new_budget),), commit=True
        )
        st.success(f"Budget updated to {new_budget}")
        st.rerun()

# Or set a specific budget directly
new_budget_val = st.number_input("Set new budget:", value=budget, step=1)
if st.button("Set Budget"):
    with st.spinner("Setting Budget..."):
        db.query(
            "UPDATE user_stats SET value=? WHERE key='budget'", 
            (str(new_budget_val),), commit=True
        )
        st.success(f"Budget set to {new_budget_val}")
        st.rerun()

# --- NEW: Conversion Rate ---
conversion_rate = float(db.query("SELECT value FROM user_stats WHERE key='conversion_rate'")[0][0])
st.write(f"**Current ducat-to-currency rate:** {smart_float_str(conversion_rate)} ducats per unit money")
new_rate = st.number_input("Set new conversion rate (ducats per unit money):", value=conversion_rate, step=1.0)
if st.button("Update Conversion Rate"):
    with st.spinner("Updating conversion rate and all ducat values..."):
        update_conversion_rate(new_rate)
        st.success(f"Conversion rate updated to {smart_float_str(new_rate)}. All task and shop ducat values adjusted.")
        st.rerun()
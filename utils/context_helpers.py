from datetime import datetime
import db


def smart_ducat_str(val):
    try:
        val = float(val)
        if val == int(val):
            return f"{int(val)}"
        else:
            return f"{val:.2f}".rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(val)


def get_budget_context():
    budget = int(db.query("SELECT value FROM user_stats WHERE key='budget'")[0][0])
    conversion_rate = float(db.query("SELECT value FROM user_stats WHERE key='conversion_rate'")[0][0])
    ducats_earned = float(db.query("SELECT value FROM user_stats WHERE key='ducats_earned'")[0][0])
    ducats_spent_row = db.query("SELECT value FROM user_stats WHERE key='ducats_spent'")
    ducats_spent = float(ducats_spent_row[0][0]) if ducats_spent_row else 0
    ducats_available = ducats_earned - ducats_spent
    # Sum of all task rewards (not just available, but all tasks)
    total_task_rewards = db.query("SELECT SUM(current_ducat_value) FROM tasks")[0][0]
    if total_task_rewards is None:
        total_task_rewards = 0
    return {
        "budget": budget,
        "conversion_rate": smart_ducat_str(conversion_rate),
        "ducats_available": smart_ducat_str(ducats_available),
        "total_task_rewards": smart_ducat_str(total_task_rewards),
    }


def get_shop_context():
    max_item_cost = db.query("SELECT MAX(ducat_value) FROM shop_items WHERE bought=0")[0][0] or 0
    avg_item_cost = db.query("SELECT AVG(ducat_value) FROM shop_items WHERE bought=0")[0][0] or 0
    sum_shop = db.query("SELECT SUM(ducat_value) FROM shop_items WHERE bought=0")[0][0] or 0
    sum_rotation = db.query("SELECT SUM(ducat_value) FROM shop_items WHERE in_rotation=1 AND bought=0")[0][0] or 0
    return {
        "max_item_cost": smart_ducat_str(float(max_item_cost)),
        "avg_item_cost": smart_ducat_str(float(avg_item_cost)),
        "sum_shop": smart_ducat_str(float(sum_shop)),
        "sum_rotation": smart_ducat_str(float(sum_rotation)),
    }

def save_report(text):
    db.query(
        "INSERT INTO reports (text, submitted_at) VALUES (?, ?)",
        (text, datetime.now().isoformat()), commit=True
    )
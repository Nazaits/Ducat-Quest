import random
from datetime import datetime, timedelta
import db
import requests
from bs4 import BeautifulSoup
import streamlit as st
from utils.context_helpers import smart_ducat_str
from utils.llm import llm_rate_task, llm_describe_shop


def add_task(desc, typ):
    name, val = llm_rate_task(desc, typ)
    db.query(
        "INSERT INTO tasks (name, description, type, completed, initial_ducat_value, current_ducat_value, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, desc, typ, 0, val, val, datetime.utcnow().isoformat()), commit=True
    )


def get_tasks():
    return db.query("SELECT * FROM tasks ORDER BY type, created_at")


def rotate_shop():
    BUDGET_FRACTION = 0.25  # 1/4 of budget
    SHOP_FRACTION = 0.33    # 1/3 of total shop value

    budget = float(db.query("SELECT value FROM user_stats WHERE key='budget'")[0][0])
    total_shop_value = db.query("SELECT SUM(ducat_value) FROM shop_items WHERE bought=0")[0][0] or 0
    cap = min(budget * BUDGET_FRACTION, total_shop_value * SHOP_FRACTION)

    items = db.query("SELECT id,real_value FROM shop_items WHERE bought=0")
    items = list(items)
    random.shuffle(items)
    total = 0
    db.query("UPDATE shop_items SET in_rotation=0", commit=True)
    for item_id, rv in items:
        if total <= cap:
            db.query("UPDATE shop_items SET in_rotation=1 WHERE id=?", (item_id,), commit=True)
            total += rv
        elif total > cap:
            break


def add_shop_item(link_or_img: str, real_value: float, image_path: str = "", instant_rotation: bool = False, ducat_premium: float = 0.0):
    # Gemini title/desc as before
    title, desc = llm_describe_shop(link_or_img, real_value, image_path)
    rate = float(db.query("SELECT value FROM user_stats WHERE key='conversion_rate'")[0][0])
    ducat_value = float(real_value * rate)
    if instant_rotation:
        ducat_value *= (1 + ducat_premium)
    db.query(
        "INSERT INTO shop_items (name, description, link, real_value, ducat_value, in_rotation, bought, added_at, image) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
        (title, desc, link_or_img, real_value, ducat_value, int(instant_rotation), datetime.utcnow().isoformat(), image_path),
        commit=True
    )


def buy_shop_item(rid, ducats):
    have = float(db.query("SELECT value FROM user_stats WHERE key='ducats_earned'")[0][0]) - \
           float(db.query("SELECT value FROM user_stats WHERE key='ducats_spent'")[0][0])
    if have >= ducats:
        # Mark item as bought
        db.query("UPDATE shop_items SET bought=1 WHERE id=?", (rid,), commit=True)
        # Add to ducats spent
        db.query("UPDATE user_stats SET value = value + ? WHERE key='ducats_spent'", (ducats,), commit=True)
        # Subtract real value from budget
        real_val = db.query("SELECT real_value FROM shop_items WHERE id=?", (rid,))[0][0]
        db.query("UPDATE user_stats SET value = value - ? WHERE key='budget'", (real_val,), commit=True)
        return True
    else:
        return False

    

def extract_image_from_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/115.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        imgs = [img['src'] for img in soup.find_all('img', src=True)]
        # Prefer image with 'product' or 'main'
        for src in imgs:
            if ("product" in src.lower() or "main" in src.lower()) and ('.jpg' in src or '.png' in src):
                return src if src.startswith("http") else url + src
        if imgs and ('.jpg' in imgs[0] or '.png' in imgs[0]):
            return imgs[0] if imgs[0].startswith("http") else url + imgs[0]
    except Exception as e:
        print(f"Error extracting image: {e}")
        return ""
    return ""


def show_ducat_bar():
    earned = float(db.query("SELECT value FROM user_stats WHERE key='ducats_earned'")[0][0])
    spent_row = db.query("SELECT value FROM user_stats WHERE key='ducats_spent'")
    spent = float(spent_row[0][0]) if spent_row else 0
    current = earned - spent
    st.markdown(
        f"<div style='background: #f0f0f0; border-radius: 1em; padding: 0.7em 1em; font-size: 1.3em; margin-bottom: 1.2em;'>"
        f"💰 <b>Your Ducats:</b> {smart_ducat_str(current)}"
        f"</div>", unsafe_allow_html=True
    )

def show_timers(page="tasks"):
    now = datetime.now()
    # Next daily reset at 8am
    next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= next_8am:
        next_8am += timedelta(days=1)
    daily_left = next_8am - now

    # Next weekly reset/shop rotation at Monday 8am or 12pm
    if now.weekday() == 0 and now.hour >= 12:
        days_ahead = 7
    else:
        days_ahead = (0 - now.weekday() + 7) % 7

    next_monday_8am = (now + timedelta(days=days_ahead)).replace(hour=8, minute=0, second=0, microsecond=0)
    next_monday_12pm = (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)

    # Special handling for Monday before 12 PM
    if now.weekday() == 0 and now.hour < 12:
        shop_left = next_monday_12pm - now
    else:
        # For all other cases, calculate from the upcoming Monday at 12 PM
        days_until_next_monday = (0 - now.weekday() + 7) % 7
        if days_until_next_monday == 0 and now.hour >= 12: # It's Monday after 12pm
            days_until_next_monday = 7
        next_monday_12pm_for_shop = (now + timedelta(days=days_until_next_monday)).replace(hour=12, minute=0, second=0, microsecond=0)
        shop_left = next_monday_12pm_for_shop - now


    weekly_left = next_monday_8am - now

    # Previous code
    # days_ahead = (7 - now.weekday()) % 7  # Days until next Monday
    # next_monday_8am = (now + timedelta(days=days_ahead)).replace(hour=8, minute=0, second=0, microsecond=0)
    # next_monday_12pm = (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
    # weekly_left = next_monday_8am - now
    # shop_left = next_monday_12pm - now

    # Helper for smart display
    def format_timedelta(delta):
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m"
        else:
            return f"Less than 1min"

    # Show the appropriate timer based on page
    if page == "tasks":
        st.markdown(
            f"<span style='font-size:1em'>⏳ <b>Next Daily Reset:</b> {format_timedelta(daily_left)} &nbsp;|&nbsp; "
            f"<b>Next Weekly Reset:</b> {format_timedelta(weekly_left)}</span>",
            unsafe_allow_html=True
        )
    elif page == "daily":
        st.markdown(
            f"<span style='font-size:1em'>⏳ <b>Next Daily Reset:</b> {format_timedelta(daily_left)}</span>",
            unsafe_allow_html=True
        )
    elif page == "weekly":
        st.markdown(
            f"<span style='font-size:1em'>⏳ <b>Next Weekly Reset:</b> {format_timedelta(weekly_left)}</span>",
            unsafe_allow_html=True
        )
    elif page == "shop":
        st.markdown(
            f"<span style='font-size:1em'>🛒 <b>Next Shop Rotation:</b> {format_timedelta(shop_left)}</span>",
            unsafe_allow_html=True
        )

# logic.py
import os, random, json
from datetime import datetime, timedelta
import db
import prompts
from pydantic import BaseModel
from google import genai
import requests
from bs4 import BeautifulSoup
from google.genai import types
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

load_dotenv()


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

class TaskValuation(BaseModel):
    title: str
    value: int

class ShopItem(BaseModel):
    title: str
    description: str

class TaskAward(BaseModel):
    id: int
    awarded: float
    reason: str = ""

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

def llm_rate_task(desc: str, typ: str) -> (str, int):
    budget_context = get_budget_context()
    shop_context = get_shop_context()
    prompt = prompts.task_valuation_prompt(desc, typ, budget_context, shop_context)
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": list[TaskValuation],  # list schema
        }
    )
    # Parse structured output
    data: list[TaskValuation] = resp.parsed  # uses structured Gemini flow :contentReference[oaicite:2]{index=2}
    if not data:
        return "Untitled Task", random.randint(1, 10)
    return data[0].title, data[0].value

def add_task(desc, typ):
    name, val = llm_rate_task(desc, typ)
    db.query(
        "INSERT INTO tasks (name, description, type, completed, initial_ducat_value, current_ducat_value, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, desc, typ, 0, val, val, datetime.utcnow().isoformat()), commit=True
    )

def get_tasks():
    return db.query("SELECT * FROM tasks ORDER BY type, created_at")

def award_ducats_for_completed():
    tasks = db.query("SELECT id,ducat_value FROM tasks WHERE status='completed'")
    total = sum(r[1] for r in tasks)
    if tasks:
        db.query("UPDATE user_stats SET value = value + ? WHERE key='ducats_earned'",
                 (total,), commit=True)
        db.query("UPDATE tasks SET status='processed' WHERE status='completed'", commit=True)
    return total

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
        if total + rv <= cap:
            db.query("UPDATE shop_items SET in_rotation=1 WHERE id=?", (item_id,), commit=True)
            total += rv

def llm_describe_shop(link_or_img, value, image_path=None):
    # If image_path provided, read image as bytes
    contents = []
    if image_path:
        try:
            with open(image_path, "rb") as img_file:
                image_bytes = img_file.read()
        except:
            image_bytes = requests.get(image_path).content
        finally:
            contents.append(types.Part.from_bytes(
                            data=image_bytes,
                            mime_type='image/jpeg',
                        ))  # adjust mime type as needed
    prompt = prompts.shop_item_prompt(link_or_img, value)
    contents.append(prompt)
    # Structured output config as before
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config={
            "response_mime_type": "application/json",
            "response_schema": list[ShopItem],
        }
    )
    items: list[ShopItem] = resp.parsed
    if not items:
        return "Unnamed Item", ""
    item = items[0]
    return item.title, item.description

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
        db.query("UPDATE shop_items SET bought=1 WHERE id=?", (rid,), commit=True)
        db.query("UPDATE user_stats SET value=value+? WHERE key='ducats_spent'", (ducats,), commit=True)
        return True
    else:
        return False

# logic.py or helpers.py

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

def save_report(text):
    db.query(
        "INSERT INTO reports (text, submitted_at) VALUES (?, ?)",
        (text, datetime.now().isoformat()), commit=True
    )

def llm_evaluate_report_and_award(report_text):
    # Get all non-completed tasks
    tasks = db.query("SELECT id, name, description, current_ducat_value, initial_ducat_value FROM tasks WHERE completed=0")
    if not tasks:
        return [], 0  # Nothing to process

    # Prepare input for Gemini
    tasks_data = [
        {
            "id": tid,
            "name": name,
            "description": desc,
            "current_ducat_value": curr,
            "initial_ducat_value": init,
        }
        for tid, name, desc, curr, init in tasks
    ]
    prompt = prompts.report_processing_prompt(tasks_data, report_text)
    # Send to Gemini, get structured JSON output
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": list[TaskAward],  # Structured output!
        }
    )
    awarded_results: list[TaskAward] = response.parsed

    total_ducats = 0
    detailed_results = []
    now = datetime.now().isoformat()

    for result in awarded_results:
        tid = int(result.id)
        awarded = float(result.awarded)
        reason = result.reason
        # Get current value
        cur_val = db.query("SELECT current_ducat_value FROM tasks WHERE id=?", (tid,))[0][0]
        new_val = max(cur_val - awarded, 0)
        is_complete = new_val <= 0
        db.query(
            "UPDATE tasks SET current_ducat_value=?, completed=?, last_completed=? WHERE id=?",
            (new_val, int(is_complete), now , tid), commit=True
        )
        # Award ducats
        db.query("UPDATE user_stats SET value=value+? WHERE key='ducats_earned'", (awarded,), commit=True)
        total_ducats += awarded
        detailed_results.append((tid, awarded, reason, is_complete))
    save_report(report_text)
    return detailed_results, total_ducats

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
    days_ahead = (7 - now.weekday()) % 7  # Days until next Monday
    next_monday_8am = (now + timedelta(days=days_ahead)).replace(hour=8, minute=0, second=0, microsecond=0)
    next_monday_12pm = (now + timedelta(days=days_ahead)).replace(hour=12, minute=0, second=0, microsecond=0)
    weekly_left = next_monday_8am - now
    shop_left = next_monday_12pm - now

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

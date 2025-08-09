import os, random
from datetime import datetime
import db
import utils.prompts as prompts
from pydantic import BaseModel
from google import genai
import requests
from google.genai import types
from dotenv import load_dotenv
from utils.context_helpers import get_budget_context, get_shop_context, save_report

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

def llm_rate_task(desc: str, typ: str):
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
    data: list[TaskValuation] = resp.parsed  # type: ignore # uses structured Gemini flow :contentReference[oaicite:2]{index=2}
    if not data:
        return "Untitled Task", random.randint(1, 10)
    return data[0].title, data[0].value


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
    items: list[ShopItem] = resp.parsed # type: ignore
    if not items:
        return "Unnamed Item", ""
    item = items[0]
    return item.title, item.description


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
    awarded_results: list[TaskAward] = response.parsed # type: ignore

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

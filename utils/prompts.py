# prompts.py

def task_valuation_prompt(description, task_type, context, shop_context):
    # This is an example baseline. You should set this to what feels right for your economy.
    # Let's assume conversion_rate = 100, so this is $0.50.
    baseline_minimal_task_value = float(context['conversion_rate'])

    return (
        "You are a fair and balanced Game Master for a gamified productivity app. Your goal is to assign a motivating, but not inflated, ducat value to a user's task."
        "Your valuation must be grounded in reality and prevent the user from accumulating wealth too easily."

        f"\n**Task Details:**\n"
        f"- Description: '{description}'\n"
        f"- Type: {task_type} (daily, weekly, one-time)\n"

        f"\n**User & Economy Context:**\n"
        f"- User budget for all rewards: {context['budget']}$\n"
        f"- Conversion rate: {context['conversion_rate']} ducats to 1$\n"
        f"- User current available ducats: {context['ducats_available']}\n"
        f"- Total ducat rewards for all current tasks: {context['total_task_rewards']}\n"
        f"- Most expensive available item: {shop_context['max_item_cost']} ducats\n"
        f"- Average available item value: {shop_context['avg_item_cost']} ducats\n"

        f"\n**Valuation Framework & Rules:**\n"
        f"1. **The Anchor Rule:** A standard, minimal-effort task taking 5-10 minutes (like 'Take out the trash' or 'Fill out a simple form') should be worth around **{baseline_minimal_task_value} ducats**. All other tasks must be scaled relative to this firm baseline. Do not deviate from this principle.\n"
        "2. **Effort is Primary:** Value is determined by **effort (time commitment + mental/physical energy)**. Do not automatically assign high value to 'one-time' tasks if they are simple. A difficult, hour-long daily task is worth more than a simple, 5-minute one-time task.\n"
        "3. **The Sanity Check Rule:** Before finalizing, convert your suggested ducat value to real currency. If this amount seems too high for the described effort in a real-world context (e.g., >$2 for a simple 5-minute task), you MUST reduce the value. The user should feel accomplished, not like they've found an infinite money glitch.\n"
        "4. **Inflation Control:** Be very strict with high values if the `total_task_rewards` (in ducats) converted to dollars is approaching 85% of the `budget`.\n"

        "\n**Your Process:**\n"
        "1. First, briefly analyze the task's estimated time, mental effort, and importance.\n"
        "2. Then, using the Valuation Framework, assign a ducat value.\n"
        "3. Suggest a concise, clear title for the task.\n"

        "**Output format:**\n"
        "Title: <title>\n"
        "Reasoning: <Your brief analysis of time, effort, and why you chose the value based on the rules.>\n"
        "Value: <value>"
    )

def shop_item_prompt(link_or_img, value):
    return (
        f"Given this purchase info: {link_or_img} with value ${value}, and the imgae(if provided)"
        "generate a concise item title and a short description suitable for a rewards shop. The description should be at most 1 very short sentance. Always return results in english, no matter waht source language provided."
        "Output format:\nTitle: <title>\nDescription: <description>"
    )

def report_processing_prompt(task_list, report):
    return (
        f"Given these tasks: {task_list} and this user report: '{report}', "
        "match completed tasks, confirm which can be marked done, and briefly justify your decision. "
        "Output format:\nCompleted: <list of task titles>"
    )

def report_processing_prompt(tasks, report_text):
    """
    tasks: list of dicts with id, name, description, current_ducat_value, initial_ducat_value
    report_text: str
    """
    task_strings = [
        f"Task:\n" 
        f"- id: {t['id']} | name: {t['name']} | description: {t['description']}\n"
        f"- Current Ducat Value: {t['current_ducat_value']} | Initial Value: {t['initial_ducat_value']}\n"
        for t in tasks
    ]
    return (
        "Here are the user's active tasks:\n"
        + "\n".join(task_strings)
        + "\n\nHere is the user's report about what they did:\n"
        + report_text
        + "\n\nFor each task, decide how many ducats to award (from 0 up to the task's current ducat value). "
          "Return a JSON list like: [{'id': task_id, 'awarded': ducats, 'reason': short_reason}] "
          "Only include tasks that should receive a reward."
    )


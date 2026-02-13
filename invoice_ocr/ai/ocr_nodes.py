import json
import requests
import frappe

from .confidence import calculate_confidence


DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V3"


# ============================================================
# DeepInfra Caller
# ============================================================

def call_deepinfra(prompt: str) -> dict:
    api_key = frappe.conf.get("deepinfra_api_key")

    if not api_key:
        frappe.throw("DeepInfra API key not configured")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    res = requests.post(DEEPINFRA_API_URL, json=payload, headers=headers, timeout=120)
    res.raise_for_status()

    data = res.json()
    content = data["choices"][0]["message"]["content"]

    return json.loads(content)


# ============================================================
# HEADER
# ============================================================

def extract_header(state: dict):
    from .prompts import HEADER_PROMPT

    prompt = HEADER_PROMPT + "\n\nOCR_TEXT:\n" + state["ocr_text"]
    result = call_deepinfra(prompt)

    state["header"] = result
    return state


# ============================================================
# ITEMS
# ============================================================

def extract_items(state: dict):
    from .prompts import ITEMS_PROMPT

    prompt = ITEMS_PROMPT + "\n\nOCR_TEXT:\n" + state["ocr_text"]
    result = call_deepinfra(prompt)

    state["items"] = result
    return state


# ============================================================
# TAXES
# ============================================================

def extract_taxes(state: dict):
    from .prompts import TAX_PROMPT

    prompt = TAX_PROMPT + "\n\nOCR_TEXT:\n" + state["ocr_text"]
    result = call_deepinfra(prompt)

    state["taxes"] = result
    return state


# ============================================================
# CONFIDENCE
# ============================================================
from .confidence import calculate_confidence

def score_confidence(state: dict):

    state["confidence"] = calculate_confidence(state)

    return state


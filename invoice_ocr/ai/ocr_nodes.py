import json
import requests
import frappe
from .prompts import UNIVERSAL_INVOICE_PROMPT

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V3"


def call_deepinfra(prompt: str) -> dict:
    api_key = frappe.conf.get("deepinfra_api_key")

    if not api_key:
        frappe.throw("DeepInfra API key not configured")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
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


def extract_invoice(state: dict):
    prompt = UNIVERSAL_INVOICE_PROMPT + "\n\nOCR_TEXT:\n" + state["ocr_text"]
    result = call_deepinfra(prompt)
    state["data"] = result
    return state

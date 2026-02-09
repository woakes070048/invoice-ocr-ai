import os
import base64
import mimetypes
import requests
import frappe
from frappe import _

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-OCR"

def _encode_file_to_base64(file_url):
    file_url = file_url.lstrip("/")
    absolute_path = frappe.get_site_path(file_url)

    if not os.path.exists(absolute_path):
        frappe.throw(_("File not found"))

    with open(absolute_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def _detect_mime_type(file_url):
    mime, _ = mimetypes.guess_type(file_url)
    return mime or "image/png"

def run_vision_ocr(file_url):
    api_key = frappe.conf.get("deepinfra_api_key")

    if not api_key:
        frappe.throw(_("DEEPINFRA API key not configured"))

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{_detect_mime_type(file_url)};base64,{_encode_file_to_base64(file_url)}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    res = requests.post(DEEPINFRA_API_URL, json=payload, headers=headers, timeout=120)
    res.raise_for_status()

    data = res.json()
    content = data["choices"][0]["message"]["content"]

    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content)

    return content.strip()

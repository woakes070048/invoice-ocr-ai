import os
import base64
import mimetypes
import requests
import frappe
from frappe import _

# ============================================================
# CONFIG
# ============================================================

DEEPSEEK_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-OCR"

# ============================================================
# HELPERS (⚠️ MUST BE ABOVE run_vision_ocr)
# ============================================================

def _detect_mime_type(file_url: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_url)
    return mime_type or "image/png"


def _encode_file_to_base64(file_url: str) -> str:
    if not file_url:
        frappe.throw(_("No file provided for OCR"))

    file_url = file_url.lstrip("/")
    absolute_path = frappe.get_site_path(file_url)

    if not os.path.exists(absolute_path):
        frappe.throw(_("File not found at {0}").format(absolute_path))

    with open(absolute_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# ============================================================
# MAIN OCR FUNCTION
# ============================================================

def run_vision_ocr(file_url: str) -> str:
    api_key = frappe.conf.get("deepseek_api_key")

    if not api_key:
        frappe.throw(_("DeepSeek API key not found in site_config.json"))

    mime_type = _detect_mime_type(file_url)
    encoded_file = _encode_file_to_base64(file_url)

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_file}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            json=payload,
            headers=headers,
            timeout=120
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # DeepInfra sometimes returns list
        if isinstance(content, list):
            return " ".join(c.get("text", "") for c in content)

        return content.strip()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Invoice OCR – DeepSeek Error")
        frappe.throw(_("Failed to process OCR request"))

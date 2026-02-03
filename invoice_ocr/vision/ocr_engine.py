import os
import base64
import mimetypes
import requests
import frappe

# ============================================================
# CONFIG – DeepSeek OCR via DeepInfra
# ============================================================

DEEPINFRA_API_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-OCR"


# ============================================================
# HELPERS
# ============================================================

def _detect_mime_type(file_path: str) -> str:
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "image/png"


def _encode_file_to_base64(file_path: str) -> str:
    if not os.path.exists(file_path):
        frappe.throw(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# MAIN VISION OCR FUNCTION
# ============================================================

def run_vision_ocr(file_url: str) -> str:
    """
    Run DeepSeek OCR (Vision only).
    Returns raw OCR text.
    """

    api_key = frappe.conf.get("DEEPINFRA_API_KEY")
    if not api_key:
        frappe.throw("DEEPINFRA_API_KEY not configured")

    file_path = frappe.get_site_path(file_url.lstrip("/"))
    mime_type = _detect_mime_type(file_path)
    encoded_file = _encode_file_to_base64(file_path)

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
        "temperature": 0
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(
            DEEPINFRA_API_URL,
            json=payload,
            headers=headers,
            timeout=120
        )
        res.raise_for_status()

        data = res.json()
        content = data["choices"][0]["message"]["content"]

        if isinstance(content, list):
            return " ".join(c.get("text", "") for c in content)

        return content.strip()

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Invoice OCR – Vision OCR Error"
        )
        frappe.throw("Vision OCR failed")


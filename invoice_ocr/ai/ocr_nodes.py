import json
import frappe
from langchain_openai import ChatOpenAI

from invoice_ocr.ai.prompts import HEADER_PROMPT, ITEMS_PROMPT, TAX_PROMPT
from invoice_ocr.ai.confidence import calculate_confidence



# ============================================================
# LLM (FRAPPE CLOUD SAFE)
# ============================================================

def get_llm():
    api_key = frappe.conf.get("OPENAI_API_KEY")

    if not api_key:
        frappe.throw("OPENAI_API_KEY not configured in Frappe Cloud")

    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=api_key,
        timeout=60,
        max_retries=2
    )


# ============================================================
# SAFE JSON PARSER
# ============================================================

def _safe_json(content, default):
    try:
        data = json.loads(content)
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


# ============================================================
# OCR NODES
# ============================================================

def extract_header(state: dict):
    if not state.get("ocr_text"):
        state["header"] = {}
        return state

    llm = get_llm()

    response = llm.invoke(
        HEADER_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )

    state["header"] = _safe_json(response.content, {})
    return state


def extract_items(state: dict):
    if not state.get("ocr_text"):
        state["items"] = []
        return state

    llm = get_llm()

    response = llm.invoke(
        ITEMS_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )

    state["items"] = _safe_json(response.content, [])
    return state


def extract_taxes(state: dict):
    if not state.get("ocr_text"):
        state["taxes"] = []
        return state

    llm = get_llm()

    response = llm.invoke(
        TAX_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )

    state["taxes"] = _safe_json(response.content, [])
    return state


def score_confidence(state: dict):
    try:
        state["confidence"] = calculate_confidence(state)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Invoice OCR – Confidence Calculation Error"
        )
        state["confidence"] = 0

    return state

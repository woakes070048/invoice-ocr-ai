import json
import frappe
from langchain_openai import ChatOpenAI
from .prompts import HEADER_PROMPT, ITEMS_PROMPT, TAX_PROMPT
from .confidence import calculate_confidence


# ============================================================
# LLM (Frappe-safe)
# ============================================================

def get_llm():
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=frappe.conf.get("openai_api_key")
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
    llm = get_llm()

    response = llm.invoke(
        HEADER_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )

    state["header"] = _safe_json(response.content, {})
    return state


def extract_items(state: dict):
    llm = get_llm()

    response = llm.invoke(
        ITEMS_PROMPT + "\nOCR_TEXT:\n" + state["ocr_text"]
    )

    state["items"] = _safe_json(response.content, [])
    return state


def extract_taxes(state: dict):
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
            "OCR Confidence Calculation Error"
        )
        state["confidence"] = 0

    return state

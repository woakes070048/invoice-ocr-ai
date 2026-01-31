from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
import frappe
import json

# ============================================================
# STATE DEFINITION
# ============================================================

class OCRState(TypedDict):
    ocr_text: str
    header: Dict[str, Any]
    items: List[Dict[str, Any]]
    taxes: List[Dict[str, Any]]
    confidence: float


# ============================================================
# SAFE JSON PARSER (LLM GUARD)
# ============================================================

def safe_json_load(text: str):
    try:
        if not text:
            return None

        text = text.strip()

        # remove ```json ``` wrappers if present
        if text.startswith("```"):
            text = text.split("```")[1]

        return json.loads(text)
    except Exception:
        return None


# ============================================================
# LLM HELPER (CLOUD SAFE)
# ============================================================

def get_llm():
    api_key = frappe.conf.get("openai_api_key")

    if not api_key:
        frappe.throw("OpenAI API key not configured in site_config.json")

    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=api_key,
        timeout=60,
        max_retries=2
    )


# ============================================================
# NODE 1️⃣ HEADER EXTRACTION
# ============================================================

def extract_header(state: OCRState):

    if not state.get("ocr_text"):
        return {"header": {}}

    llm = get_llm()

    prompt = f"""
You are an ERP invoice header extraction agent.

Rules:
- Extract ONLY what is clearly present
- Do NOT guess
- Return valid JSON only

Schema:
{{
  "supplier": string | null,
  "invoice_number": string | null,
  "invoice_date": "YYYY-MM-DD" | null,
  "currency": string | null
}}

OCR TEXT:
{state["ocr_text"]}
"""

    response = llm.invoke(prompt)
    header = safe_json_load(response.content) or {}

    return {"header": header}


# ============================================================
# NODE 2️⃣ ITEM EXTRACTION
# ============================================================

def extract_items(state: OCRState):

    if not state.get("ocr_text"):
        return {"items": []}

    llm = get_llm()

    prompt = f"""
You are an ERP invoice line-item extractor.

Rules:
- Extract ALL line items
- If value missing, return null
- Numbers must be numeric
- Do NOT merge items

Schema:
[
  {{
    "item_name": string | null,
    "description": string | null,
    "qty": number | null,
    "rate": number | null
  }}
]

OCR TEXT:
{state["ocr_text"]}
"""

    response = llm.invoke(prompt)
    items = safe_json_load(response.content)

    if not isinstance(items, list):
        items = []

    return {"items": items}


# ============================================================
# NODE 3️⃣ TAX EXTRACTION
# ============================================================

def extract_taxes(state: OCRState):

    if not state.get("ocr_text"):
        return {"taxes": []}

    llm = get_llm()

    prompt = f"""
You are an ERP tax extraction agent.

Rules:
- Extract taxes ONLY if present
- Do NOT invent tax
- Return empty list if none found

Schema:
[
  {{
    "charge_type": "On Net Total",
    "account_head": string | null,
    "rate": number | null
  }}
]

OCR TEXT:
{state["ocr_text"]}
"""

    response = llm.invoke(prompt)
    taxes = safe_json_load(response.content)

    if not isinstance(taxes, list):
        taxes = []

    return {"taxes": taxes}


# ============================================================
# NODE 4️⃣ CONFIDENCE SCORING
# ============================================================

def score_confidence(state: OCRState):

    score = 0

    header = state.get("header", {})
    items = state.get("items", [])
    taxes = state.get("taxes", [])

    # ---------- HEADER (50%) ----------
    if header.get("supplier"):
        score += 15
    if header.get("invoice_number"):
        score += 15
    if header.get("invoice_date"):
        score += 10
    if header.get("currency"):
        score += 10

    # ---------- ITEMS (35%) ----------
    if items:
        score += 15
        valid = 0
        for i in items:
            if i.get("qty") and i.get("rate"):
                valid += 1
        if valid == len(items):
            score += 20

    # ---------- TAXES (15%) ----------
    if taxes:
        score += 15

    return {"confidence": min(score, 100)}


# ============================================================
# BUILD LANGGRAPH AGENT
# ============================================================

def build_ocr_agent():

    graph = StateGraph(OCRState)

    graph.add_node("header", extract_header)
    graph.add_node("items", extract_items)
    graph.add_node("taxes", extract_taxes)
    graph.add_node("confidence", score_confidence)

    graph.set_entry_point("header")

    graph.add_edge("header", "items")
    graph.add_edge("items", "taxes")
    graph.add_edge("taxes", "confidence")
    graph.add_edge("confidence", END)

    return graph.compile()

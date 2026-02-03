"""
Confidence scoring for Invoice OCR
Cloud-safe, deterministic, no external dependencies
"""

def calculate_confidence(state: dict) -> int:
    """
    Calculate confidence score (0–100) based on extracted data quality
    """

    score = 0

    # ---------------- HEADER (40%) ----------------
    header = state.get("header") or {}
    if header:
        if header.get("supplier"):
            score += 15
        if header.get("invoice_number"):
            score += 10
        if header.get("invoice_date"):
            score += 10
        if header.get("currency"):
            score += 5

    # ---------------- ITEMS (40%) ----------------
    items = state.get("items") or []
    if items:
        score += 20
        valid_items = 0
        for i in items:
            if i.get("qty") and i.get("rate"):
                valid_items += 1
        if valid_items == len(items):
            score += 20

    # ---------------- TAXES (20%) ----------------
    taxes = state.get("taxes") or []
    if taxes:
        score += 20

    # ---------------- SAFE BOUNDS ----------------
    if score < 0:
        score = 0
    if score > 100:
        score = 100

    return score

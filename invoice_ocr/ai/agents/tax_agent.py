import re
from invoice_ocr.ai.prompts import TAX_PROMPT
from invoice_ocr.ai.ocr_nodes import call_deepinfra


def extract_tax_agent(state: dict):

    text = state.get("ocr_text", "")
    net_total = state.get("net_total") or 0
    detected_grand_total = state.get("detected_grand_total") or 0

    # ---------------------------------------------
    # 1️⃣ LLM EXTRACTION
    # ---------------------------------------------
    prompt = TAX_PROMPT + "\n\nOCR_TEXT:\n" + text
    result = call_deepinfra(prompt)

    # Ensure list
    if not isinstance(result, list):
        result = []

    cleaned_taxes = []

    for tax in result:

        try:
            amount = float(tax.get("amount") or 0)
        except Exception:
            continue

        label = (tax.get("label") or "").lower()

        # ---------------------------------------------
        # 2️⃣ SAFETY FILTERS
        # ---------------------------------------------

        # Skip zero
        if amount <= 0:
            continue

        # Skip if equals grand total
        if detected_grand_total and amount == detected_grand_total:
            continue

        # Skip if equals net total (common hallucination)
        if net_total and amount == net_total:
            continue

        # Skip summary words
        if any(word in label for word in [
            "total",
            "net total",
            "grand",
            "including"
        ]):
            continue

        cleaned_taxes.append({
            "label": tax.get("label"),
            "rate": tax.get("rate"),
            "amount": amount,
            "charge_type": "Actual"
        })

    state["taxes"] = cleaned_taxes
    return state
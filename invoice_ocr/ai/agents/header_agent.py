from invoice_ocr.ai.prompts import HEADER_PROMPT_TEMPLATE
from invoice_ocr.ai.ocr_nodes import call_deepinfra

def extract_header_agent(state: dict):

    context = state.get("context", {})

    country = context.get("country", "UNKNOWN")
    invoice_type = context.get("invoice_type", "Invoice")

    # SAFE TEMPLATE INJECTION (NO .format())
    prompt = HEADER_PROMPT_TEMPLATE
    prompt = prompt.replace("{country}", context.get("country", "UNKNOWN"))
    prompt = prompt.replace("{invoice_type}", context.get("invoice_type", "Invoice"))


    prompt += "\n\nOCR_TEXT:\n" + state["ocr_text"]

    result = call_deepinfra(prompt)

    state["header"] = result
    return state

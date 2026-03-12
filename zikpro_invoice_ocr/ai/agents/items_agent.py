from zikpro_invoice_ocr.ai.prompts import ITEMS_PROMPT_TEMPLATE
from zikpro_invoice_ocr.ai.ocr_nodes import call_deepinfra

def extract_items_agent(state: dict):

    context = state.get("context", {})

    table_structure = context.get("table_structure", "SIMPLE")

    prompt = ITEMS_PROMPT_TEMPLATE
    prompt = prompt.replace("{table_structure}", str(table_structure))

    prompt += "\n\nOCR_TEXT:\n" + state["ocr_text"]

    result = call_deepinfra(prompt)
    state["items"] = result
    return state

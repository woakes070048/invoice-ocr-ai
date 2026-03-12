from zikpro_invoice_ocr.ai.ocr_nodes import call_deepinfra

REFLECTION_PROMPT = """
Review the extracted invoice JSON below.
Fix inconsistencies.
Ensure financial correctness.
Return corrected JSON only.
"""

def reflect_and_correct(state):

    prompt = REFLECTION_PROMPT + "\n\nDATA:\n" + str(state)
    result = call_deepinfra(prompt)

    return result

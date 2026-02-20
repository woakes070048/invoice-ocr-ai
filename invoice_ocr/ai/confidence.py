def calculate_confidence(state):

    score = 0

    header = state.get("header", {})
    items = state.get("items", [])
    taxes = state.get("taxes", [])
    financial = state.get("financial_validation", {})

    if header.get("invoice_number"):
        score += 15

    if header.get("invoice_date"):
        score += 15

    if header.get("currency"):
        score += 10

    if items:
        score += 20

    if taxes:
        score += 15

    if financial.get("is_valid"):
        score += 25

    return min(score, 100)

def calculate_confidence(data: dict, validation: dict) -> int:
    score = 0

    header = data.get("header") or {}
    items = data.get("items") or []
    totals = data.get("totals") or {}

    if header.get("supplier_name"):
        score += 15
    if header.get("invoice_number"):
        score += 10
    if header.get("invoice_date"):
        score += 10
    if header.get("currency"):
        score += 5

    if items:
        score += 30

    if totals.get("grand_total"):
        score += 20

    if not validation.get("errors"):
        score += 10

    return min(score, 100)

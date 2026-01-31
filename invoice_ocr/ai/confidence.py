def calculate_confidence(state):
    score = 100

    header = state.get("header", {})
    items = state.get("items", [])

    if not header:
        score -= 40

    if not items:
        score -= 40

    if "null" in str(header).lower():
        score -= 10

    if score < 0:
        score = 0

    return score



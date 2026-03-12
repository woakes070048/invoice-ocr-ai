def build_context(state):

    layout = state.get("layout", {})

    context = {}

    context["country"] = layout.get("country_pattern", "UNKNOWN")

    if layout.get("invoice_type") == "SERVICE":
        context["invoice_type"] = "Service Invoice"
    else:
        context["invoice_type"] = "Goods Invoice"

    if layout.get("country_pattern") == "INDIA_GST":
        context["tax_model"] = "CGST_SGST"

    elif layout.get("country_pattern") == "UK_VAT":
        context["tax_model"] = "SINGLE_VAT"

    elif layout.get("country_pattern") == "PAK_FBR":
        context["tax_model"] = "SALES_TAX"

    else:
        context["tax_model"] = "GENERIC"

    state["context"] = context
    return state


import frappe


def update_supplier_memory(doc):
    """
    Learn supplier behavior after invoice is posted
    """

    if not doc.supplier:
        return

    profile = frappe.db.exists(
        "Supplier AI Profile",
        {"supplier": doc.supplier}
    )

    if profile:
        profile = frappe.get_doc("Supplier AI Profile", profile)
    else:
        profile = frappe.new_doc("Supplier AI Profile")
        profile.supplier = doc.supplier
        profile.invoice_count = 0

    # ---------------- Expense Account Learning ----------------
    if doc.items:
        first_item = doc.items[0]
        profile.default_expense_account = first_item.expense_account

    # ---------------- Tax Learning ----------------
    if doc.taxes:
        first_tax = doc.taxes[0]
        profile.default_tax_account = first_tax.account_head

    # ---------------- Currency Learning ----------------
    profile.last_currency = doc.currency

    # ---------------- Average Invoice ----------------
    total = doc.grand_total or 0

    count = profile.invoice_count or 0
    avg = profile.avg_invoice_amount or 0

    new_avg = ((avg * count) + total) / (count + 1)

    profile.avg_invoice_amount = new_avg
    profile.invoice_count = count + 1

    profile.save(ignore_permissions=True)

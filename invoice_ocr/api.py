import re
import frappe
from invoice_ocr.vision.ocr_engine import run_vision_ocr


# ============================================================
# UTILITIES
# ============================================================

def detect_currency(text):
    t = text.upper()
    if "£" in t or "GBP" in t:
        return "GBP"
    if "$" in t or "USD" in t:
        return "USD"
    if "€" in t or "EUR" in t:
        return "EUR"
    if "₨" in t or "PKR" in t:
        return "PKR"
    return frappe.defaults.get_global_default("currency")

# ============================================================
# RUN OCR PIPELINE (Enterprise Safe + Intelligent Matching)
# ============================================================

@frappe.whitelist()
def run_ocr(docname):

    from invoice_ocr.ai.ocr_nodes import (
        extract_header,
        extract_items,
        extract_taxes,
        score_confidence
    )

    from invoice_ocr.intelligence.supplier_matcher import intelligent_supplier_match

    doc = frappe.get_doc("Invoice OCR", docname)

    # ---------------- 1️⃣ Vision OCR ----------------
    raw = run_vision_ocr(doc.invoice_file)
    doc.raw_ocr_text = raw

    # ---------------- 2️⃣ AI Extraction ----------------
    state = {
        "ocr_text": raw,
        "header": {},
        "items": [],
        "taxes": [],
        "confidence": 0
    }

    state = extract_header(state)
    state = extract_items(state)
    state = extract_taxes(state)
    state = score_confidence(state)

    header = state.get("header") or {}
    items = state.get("items") or []
    taxes = state.get("taxes") or []
    confidence = state.get("confidence", 60)

    # ============================================================
    # 3️⃣ Intelligent Supplier Auto Detection
    # ============================================================

    supplier_name = header.get("supplier_name")
    detected_supplier = None

    if supplier_name:

        supplier_name_clean = supplier_name.strip().lower()

        # 🔹 1️⃣ Exact Match
        exact = frappe.db.get_value(
            "Supplier",
            {"supplier_name": supplier_name},
            "name"
        )

        if exact:
            detected_supplier = exact

        # 🔹 2️⃣ LIKE Match
        if not detected_supplier:
            like_match = frappe.db.get_value(
                "Supplier",
                {"supplier_name": ["like", f"%{supplier_name}%"]},
                "name"
            )
            if like_match:
                detected_supplier = like_match

        # 🔹 3️⃣ Fuzzy Match (Simple similarity)
        if not detected_supplier:
            suppliers = frappe.get_all(
                "Supplier",
                fields=["name", "supplier_name"]
            )

            for sup in suppliers:
                db_name = (sup.supplier_name or "").lower()
                if supplier_name_clean in db_name or db_name in supplier_name_clean:
                    detected_supplier = sup.name
                    break

    # Apply result
    if detected_supplier:
        doc.supplier = detected_supplier

    doc.detected_supplier_name = supplier_name

    # ============================================================
    # 4️⃣ APPLY SUPPLIER MEMORY (If Exists)
    # ============================================================

    if doc.supplier:

        profile_name = frappe.db.exists(
            "Supplier AI Profile",
            {"supplier": doc.supplier}
        )

        if profile_name:
            profile = frappe.get_doc("Supplier AI Profile", profile_name)

            doc.detected_supplier_name = "Known Supplier (AI Memory)"

            # Future auto-apply logic example:
            if profile.default_currency:
                doc.currency = profile.default_currency

    # ============================================================
    # 5️⃣ SAVE HEADER
    # ============================================================

    doc.invoice_number = header.get("invoice_number")
    doc.invoice_date = header.get("invoice_date")

    if not doc.currency:
        doc.currency = header.get("currency") or detect_currency(raw)

    # ============================================================
    # 6️⃣ SAVE ITEMS
    # ============================================================

    doc.items = []
    net_total = 0

    for it in items:

        qty = it.get("qty", 1) or 1
        rate = it.get("rate", 0) or 0
        amount = qty * rate

        net_total += amount

        doc.append("items", {
            "item_name": it.get("item_name"),
            "qty": qty,
            "rate": rate,
            "uom": "Nos"
        })

    # ============================================================
    # 7️⃣ SAVE TAXES
    # ============================================================

    doc.taxes = []
    tax_total = 0

    for tx in taxes:

        amount = tx.get("amount") or 0
        tax_total += amount

        doc.append("taxes", {
            "charge_type": tx.get("charge_type") or "Actual",
            "account_head": tx.get("account_head"),
            "description": tx.get("label") or "Tax",
            "rate": tx.get("rate") or 0,
            "tax_amount": amount
        })

    # ============================================================
    # 8️⃣ TOTALS
    # ============================================================

    doc.net_total = net_total
    doc.tax_total = tax_total
    doc.grand_total = net_total + tax_total

    # ============================================================
    # 9️⃣ SAVE SEMANTIC JSON
    # ============================================================

    doc.semantic_invoice_json = frappe.as_json(state, indent=2)

    # ============================================================
    # 🔟 FINAL SAVE
    # ============================================================

    doc.confidence = confidence
    doc.status = "Ready"

    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "confidence": confidence,
        "net_total": doc.net_total,
        "tax_total": doc.tax_total,
        "grand_total": doc.grand_total
    }
# ============================================================
# CREATE PURCHASE INVOICE (Enterprise Safe + Memory Integrated)
# ============================================================

@frappe.whitelist()
def create_purchase_invoice(docname):

    doc = frappe.get_doc("Invoice OCR", docname)

    # ============================================================
    # 1️⃣ BASIC VALIDATIONS
    # ============================================================

    if not doc.supplier:
        frappe.throw("Please select Supplier before creating Purchase Invoice")

    if not doc.invoice_number:
        frappe.throw("Invoice Number missing")

    if not doc.invoice_date:
        frappe.throw("Invoice Date missing")

    if not doc.items:
        frappe.throw("No items found")

    company = frappe.defaults.get_user_default("Company")

    if not company:
        frappe.throw("Default Company not found")

    # Prevent duplicate invoice
    existing = frappe.db.exists(
        "Purchase Invoice",
        {
            "bill_no": doc.invoice_number,
            "supplier": doc.supplier
        }
    )

    if existing:
        frappe.throw(f"Purchase Invoice already exists: {existing}")

    # ============================================================
    # 2️⃣ CREATE PURCHASE INVOICE
    # ============================================================

    pi = frappe.new_doc("Purchase Invoice")

    pi.company = company
    pi.supplier = doc.supplier
    pi.bill_no = doc.invoice_number
    pi.bill_date = doc.invoice_date
    pi.posting_date = doc.invoice_date
    pi.currency = doc.currency
    pi.update_stock = 0

    # ============================================================
    # 3️⃣ LOAD SUPPLIER MEMORY (If Exists)
    # ============================================================

    profile = frappe.db.exists(
        "Supplier AI Profile",
        {"supplier": doc.supplier}
    )

    memory = None

    if profile:
        memory = frappe.get_doc("Supplier AI Profile", profile)

    # ============================================================
    # 4️⃣ ITEMS SECTION
    # ============================================================

    for row in doc.items:

        # Priority:
        # 1. Supplier Memory
        # 2. First Expense Account
        # 3. Throw error

        expense_account = None

        if memory and memory.default_expense_account:
            expense_account = memory.default_expense_account
        else:
            expense_account = frappe.db.get_value(
                "Account",
                {
                    "company": company,
                    "root_type": "Expense",
                    "is_group": 0
                },
                "name"
            )

        if not expense_account:
            frappe.throw("No Expense Account found for this company")

        pi.append("items", {
            "item_name": row.item_name,
            "description": row.item_name,
            "qty": row.qty or 1,
            "rate": row.rate or 0,
            "expense_account": expense_account
        })

    # ============================================================
    # 5️⃣ TAX SECTION (Company Safe Mapping)
    # ============================================================

    if doc.taxes:

        company_tax_accounts = frappe.get_all(
            "Account",
            filters={
                "company": company,
                "account_type": "Tax",
                "is_group": 0
            },
            fields=["name"]
        )

        valid_tax_accounts = [a.name for a in company_tax_accounts]

        for tax in doc.taxes:

            account_head = None

            # Priority:
            # 1. Valid detected tax account
            # 2. Supplier memory tax account
            # 3. First company tax account

            if tax.account_head in valid_tax_accounts:
                account_head = tax.account_head

            elif memory and memory.default_tax_account in valid_tax_accounts:
                account_head = memory.default_tax_account

            elif valid_tax_accounts:
                account_head = valid_tax_accounts[0]

            if not account_head:
                continue

            pi.append("taxes", {
                "charge_type": tax.charge_type or "On Net Total",
                "account_head": account_head,
                "description": tax.description or account_head,
                "rate": tax.rate or 0,
                "tax_amount": tax.tax_amount or 0
            })

    # ============================================================
    # 6️⃣ INSERT & SUBMIT
    # ============================================================

    pi.insert(ignore_permissions=True)

    if pi.docstatus == 0:
        pi.submit()

    # ============================================================
    # 7️⃣ UPDATE SUPPLIER MEMORY
    # ============================================================

    try:
        from invoice_ocr.intelligence.supplier_memory import update_supplier_memory
        update_supplier_memory(pi)
    except Exception as e:
        frappe.log_error(str(e), "Supplier Memory Update Failed")

    # ============================================================
    # 8️⃣ LINK BACK
    # ============================================================

    doc.purchase_invoice = pi.name
    doc.status = "Posted"
    doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "purchase_invoice": pi.name,
        "status": "Submitted"
    }

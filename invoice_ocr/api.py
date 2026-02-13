import re
import json
import frappe
from datetime import date, datetime
from invoice_ocr.vision.ocr_engine import run_vision_ocr


# ============================================================
# CONSTANTS
# ============================================================

CURRENCY_RE = r"[₹₨£$€]?\s?([\d,]+\.\d{2})"
INVOICE_RE = r"ACC\-PINV\-\d{4}\-\d+"


# ============================================================
# UTILITIES
# ============================================================

def normalize(text):
    return "\n".join(l.strip() for l in text.splitlines() if l.strip())

def json_safe(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v

def get_company():
    return frappe.defaults.get_user_default("Company")

def detect_currency(text):
    t = text.upper()
    if "£" in t or "GBP" in t: return "GBP"
    if "$" in t or "USD" in t: return "USD"
    if "€" in t or "EUR" in t: return "EUR"
    if "₨" in t or "PKR" in t or "RS" in t: return "PKR"
    return frappe.defaults.get_global_default("currency")

def clean_name(s):
    s = re.sub(r"[|]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()[:140] or "Service"


# ============================================================
# HEADER EXTRACTION (Improved)
# ============================================================

def extract_header(text):
    header = {}

    # Flexible date detection
    date_patterns = [
        r"\d{2}[-/]\d{2}[-/]\d{4}",
        r"\d{1,2}-[A-Za-z]{3}-\d{4}",
        r"\d{1,2}\s+[A-Za-z]+\s+\d{4}"
    ]

    for pattern in date_patterns:
        m = re.search(pattern, text)
        if m:
            try:
                header["invoice_date"] = frappe.utils.getdate(m.group(0))
                break
            except:
                pass

    # Invoice number detection
    m = re.search(INVOICE_RE, text)
    if m:
        header["invoice_number"] = m.group(0)

    header["currency"] = detect_currency(text)

    return header


# ============================================================
# FLEXIBLE ITEM EXTRACTION (DAY 1 FIX)
# ============================================================

def extract_items(text, invoice_number):
    items = []

    for line in text.splitlines():

        if "|" not in line:
            continue

        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 4:
            continue

        item_name = clean_name(cols[0])

        # Skip tax-like rows
        if re.search(r"(CGST|SGST|VAT|Tax|Total)", item_name, re.I):
            continue

        # Extract quantity (first number in second column)
        qty_match = re.search(r"\d+", cols[1])
        qty = int(qty_match.group()) if qty_match else 1

        # Extract rate (decimal from third column)
        rate_match = re.search(r"\d+\.?\d*", cols[2])
        rate = float(rate_match.group()) if rate_match else 0.0

        # Extract amount (last column decimal)
        amount_match = re.search(r"[\d,]+\.\d+", cols[-1])
        if amount_match:
            amount = float(amount_match.group().replace(",", ""))
        else:
            amount = qty * rate

        if qty > 0 and amount > 0:
            items.append({
                "item_no": len(items) + 1,
                "item_name": item_name,
                "qty": qty,
                "rate": rate,
                "amount": amount
            })

    return items


# ============================================================
# GRAND TOTAL EXTRACTION
# ============================================================

def extract_grand_total(text):
    for line in text.splitlines():
        if "grand total" in line.lower():
            m = re.search(CURRENCY_RE, line)
            if m:
                return float(m.group(1).replace(",", ""))
    return None

# ==========================================================
#  Helper Function ABOVE run_ocr()
# ==========================================================

def is_regex_result_valid(items, net_total, grand_total):
    if not items:
        return False

    # Reject unrealistic quantity
    for i in items:
        if i.get("qty", 0) > 1000:
            return False
        if i.get("rate", 0) <= 0:
            return False

    # Totals sanity check (allow 2% difference)
    if grand_total and net_total:
        diff = abs(grand_total - net_total)
        if diff > (grand_total * 0.02):
            return False

    return True


# ============================================================
# RUN OCR PIPELINE (UNCHANGED STRUCTURE)
# ============================================================

@frappe.whitelist()
def run_ocr(docname):

    from invoice_ocr.ai.ocr_agent import run_ocr_agent

    doc = frappe.get_doc("Invoice OCR", docname)
    company = get_company()

    # ============================================================
    # 1️⃣ Vision OCR
    # ============================================================

    raw = run_vision_ocr(doc.invoice_file)
    doc.raw_ocr_text = raw

    result = run_ocr_agent(raw)

    data = result.get("data") or {}
    validation = result.get("validation") or {}

    header = data.get("header") or {}
    items = data.get("items") or []
    charges = data.get("charges") or []
    totals = data.get("totals") or {}

    # ============================================================
    # 2️⃣ HEADER
    # ============================================================

    doc.invoice_number = header.get("invoice_number")
    doc.invoice_date = header.get("invoice_date")
    doc.currency = header.get("currency")

    # ============================================================
    # 3️⃣ SUPPLIER AUTO-DETECTION
    # ============================================================

    detected_supplier = header.get("supplier_name")

    if detected_supplier:
        supplier_match = frappe.db.get_value(
            "Supplier",
            {"supplier_name": ["like", f"%{detected_supplier}%"]},
            "name"
        )

        if supplier_match:
            doc.supplier = supplier_match
        else:
            # store suggestion (create custom field if needed)
            doc.detected_supplier_name = detected_supplier

    # ============================================================
    # 4️⃣ ITEMS
    # ============================================================

    doc.items = []

    for it in items:
        doc.append("items", {
            "item_name": it.get("item_name"),
            "qty": it.get("qty", 1),
            "rate": it.get("rate", 0),
            "uom": "Nos"
        })

    # ============================================================
    # 5️⃣ TAX HANDLING (Enterprise Generic)
    # ============================================================

    doc.taxes = []

    tax_total = 0

    for c in charges:

        if c.get("type") != "tax":
            continue

        tax_amount = c.get("amount") or 0
        tax_total += tax_amount

        # Find any tax account in company
        tax_account = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "root_type": "Liability",
                "is_group": 0
            },
            "name"
        )

        if not tax_account:
            continue

        doc.append("taxes", {
            "charge_type": "Actual",
            "account_head": tax_account,
            "description": c.get("label") or "Tax",
            "tax_amount": tax_amount,
            "rate": c.get("rate") or 0
        })

    # ============================================================
    # 6️⃣ TOTALS
    # ============================================================

    doc.net_total = totals.get("net_total") or 0
    doc.tax_total = tax_total
    doc.grand_total = totals.get("grand_total") or (
        doc.net_total + tax_total
    )

    # ============================================================
    # 7️⃣ SAVE SEMANTIC JSON
    # ============================================================

    doc.semantic_invoice_json = frappe.as_json(result, indent=2)

    # ============================================================
    # 8️⃣ CONFIDENCE & STATUS
    # ============================================================

    doc.confidence = result.get("confidence", 60)
    doc.status = "Ready"

    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return result


# ==========================================================
# create_purchase_invoice
# ===========================================================
@frappe.whitelist()
def create_purchase_invoice(docname):
    """
    Enterprise-safe Purchase Invoice creation
    """

    doc = frappe.get_doc("Invoice OCR", docname)

    if not doc.supplier:
        frappe.throw("Please select Supplier before creating Purchase Invoice")

    if not doc.items:
        frappe.throw("No items found to create Purchase Invoice")

    if not doc.invoice_date:
        frappe.throw("Invoice Date missing")

    if not doc.invoice_number:
        frappe.throw("Invoice Number missing")

    company = frappe.defaults.get_user_default("Company")

    if not company:
        frappe.throw("No default company found")

    # Prevent duplicate bill
    existing = frappe.db.exists("Purchase Invoice", {
        "bill_no": doc.invoice_number,
        "supplier": doc.supplier
    })

    if existing:
        frappe.throw(f"Purchase Invoice already exists: {existing}")

    pi = frappe.new_doc("Purchase Invoice")

    pi.company = company
    pi.supplier = doc.supplier
    pi.bill_no = doc.invoice_number
    pi.bill_date = doc.invoice_date
    pi.posting_date = doc.invoice_date
    pi.currency = doc.currency or frappe.get_cached_value(
        "Company",
        company,
        "default_currency"
    )
    pi.update_stock = 0

    # ---------------- ITEMS ----------------
    for row in doc.items:

        if not row.item_name:
            continue

        expense_account = (
            row.expense_account
            or frappe.db.get_value(
                "Account",
                {"company": company, "root_type": "Expense", "is_group": 0},
                "name"
            )
        )

        if not expense_account:
            frappe.throw("No Expense Account found in Company")

        pi.append("items", {
            "item_name": row.item_name,
            "description": row.item_name,
            "qty": row.qty or 1,
            "rate": row.rate or 0,
            "expense_account": expense_account
        })

    # ---------------- TAXES ----------------
    if doc.taxes:
        for tax in doc.taxes:

            if not tax.account_head:
                continue

            pi.append("taxes", {
                "charge_type": tax.charge_type or "On Net Total",
                "account_head": tax.account_head,
                "description": tax.description or tax.account_head or "Tax",
                "rate": tax.rate or 0,
                "tax_amount": tax.tax_amount or 0
            })

    # ---------------- SAVE ----------------
    pi.insert(ignore_permissions=True)

    if pi.docstatus == 0:
        pi.submit()

    # ---------------- LINK BACK ----------------
    doc.purchase_invoice = pi.name
    doc.status = "Posted"
    doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "purchase_invoice": pi.name,
        "status": "Submitted"
    }

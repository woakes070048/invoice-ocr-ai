import re
import json
import frappe
import frappe.utils
from datetime import date, datetime
from invoice_ocr.ai.ocr_engine import run_vision_ocr

# ============================================================
# CONSTANTS
# ============================================================

CURRENCY_RE = r"[₹₨£$€]\s?([\d,]+\.\d{2})"
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
    if "£" in t or "GBP" in t:
        return "GBP"
    if "$" in t or "USD" in t:
        return "USD"
    if "€" in t or "EUR" in t:
        return "EUR"
    if "₨" in t or "PKR" in t or "RS" in t:
        return "PKR"
    return frappe.defaults.get_global_default("currency")

def get_expense_account(company):
    acc = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Expense", "is_group": 0},
        "name"
    )
    if not acc:
        frappe.throw("Expense Account not found")
    return acc

def get_tax_account(company):
    acc = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": ["like", "%VAT%"], "is_group": 0},
        "name"
    )
    if not acc:
        frappe.throw("VAT Account not found for company")
    return acc

def clean_name(s):
    s = re.sub(r"[|]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()[:140] or "Service"

# ============================================================
# HEADER EXTRACTION
# ============================================================

def extract_header(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    header = {}

    for i, l in enumerate(lines):
        if re.search(r"Supplier\s*Name", l, re.I):
            parts = l.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                header["supplier_name"] = parts[1].strip()
            elif i + 1 < len(lines):
                header["supplier_name"] = lines[i + 1]
            break

    m = re.search(INVOICE_RE, text)
    if m:
        header["invoice_number"] = m.group(0)

    m = re.search(r"(\d{2}[-/]\d{2}[-/]\d{4})", text)
    if m:
        header["invoice_date"] = frappe.utils.getdate(m.group(1))

    header["currency"] = detect_currency(text)
    return header

# ============================================================
# ITEM EXTRACTION (NO DUPLICATES)
# ============================================================

def extract_items(text, invoice_number):
    items = []
    started = False

    for line in text.splitlines():

        if invoice_number and invoice_number in line:
            started = True
            continue

        if not started:
            continue

        if re.search(INVOICE_RE, line) and items:
            break

        if "|" not in line:
            continue

        if re.search(r"(total|tax|grand)", line.lower()):
            continue

        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 6:
            continue

        item_name = clean_name(cols[1])
        qty = int(cols[3]) if cols[3].isdigit() and int(cols[3]) > 0 else 1

        rates = re.findall(CURRENCY_RE, line)
        if not rates:
            continue

        rate = float(rates[-1].replace(",", ""))

        items.append({
            "item_no": len(items) + 1,
            "item_name": item_name,
            "qty": qty,
            "rate": rate,
            "amount": qty * rate
        })

    return items

# ============================================================
# GRAND TOTAL EXTRACTION
# ============================================================

def extract_grand_total(text):
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if "grand total" in l.lower():
            m = re.search(CURRENCY_RE, l)
            if m:
                return float(m.group(1).replace(",", ""))
            if i + 1 < len(lines):
                m2 = re.search(CURRENCY_RE, lines[i + 1])
                if m2:
                    return float(m2.group(1).replace(",", ""))
    return None

# ============================================================
# RUN OCR
# ============================================================

@frappe.whitelist()
def run_ocr(docname):

    doc = frappe.get_doc("Invoice OCR", docname)
    company = get_company()

    raw = run_vision_ocr(doc.invoice_file)
    doc.raw_ocr_text = raw
    text = normalize(raw)

    header = extract_header(text)
    items = extract_items(text, header.get("invoice_number"))

    net_total = sum(i["amount"] for i in items)

    grand_total = extract_grand_total(text)
    if grand_total is None:
        grand_total = net_total

    tax_total = round(grand_total - net_total, 2) if grand_total > net_total else 0.0

    # ---------------- HEADER ----------------
    if not doc.supplier_name:
        doc.supplier_name = header.get("supplier_name")

    doc.invoice_number = header.get("invoice_number")
    doc.invoice_date = header.get("invoice_date")
    doc.currency = header.get("currency")

    # ---------------- ITEMS ----------------
    doc.items = []
    expense_account = get_expense_account(company)

    for it in items:
        doc.append("items", {
            "item_name": it["item_name"],
            "qty": it["qty"],
            "rate": it["rate"],
            "amount": it["amount"],
            "uom": "Nos",
            "expense_account": expense_account
        })

    # ---------------- TAXES ----------------
    doc.taxes = []
    if tax_total > 0:
        tax_account = get_tax_account(company)
        doc.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": tax_account,
            "description": tax_account,
            "rate": 0,
            "tax_amount": tax_total
        })

    # ---------------- TOTALS ----------------
    doc.net_total = net_total
    doc.tax_total = tax_total
    doc.grand_total = grand_total

    # ---------------- SEMANTIC JSON ----------------
    tax_account = get_tax_account(company) if tax_total > 0 else None

    doc.semantic_invoice_json = json.dumps({
        "header": {
            "supplier_name": header.get("supplier_name"),
            "invoice_number": header.get("invoice_number"),
            "invoice_date": json_safe(header.get("invoice_date")),
            "currency": header.get("currency")
        },
        "items": items,
        "taxes": [{
            "charge_type": "On Net Total",
            "account_head": tax_account,
            "description": tax_account,
            "rate": 0,
            "tax_amount": tax_total
        }] if tax_total > 0 else [],
        "totals": {
            "net_total": net_total,
            "tax_total": tax_total,
            "grand_total": grand_total
        }
    }, indent=2)

    doc.confidence = 100 if items else 60
    doc.status = "Ready"

    doc.flags.ignore_mandatory = True
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "net_total": net_total,
        "tax_total": tax_total,
        "grand_total": grand_total
    }

# ============================================================
# CREATE PURCHASE INVOICE (ERP SAFE)
# ============================================================

@frappe.whitelist()
def create_purchase_invoice(docname):

    doc = frappe.get_doc("Invoice OCR", docname)

    if not doc.supplier:
        frappe.throw("Please select Supplier")

    if not doc.items:
        frappe.throw("No items found")

    company = get_company()
    company_currency = frappe.get_cached_value(
        "Company", company, "default_currency"
    )

    pi = frappe.new_doc("Purchase Invoice")
    pi.company = company
    pi.supplier = doc.supplier
    pi.bill_no = doc.invoice_number

    invoice_date = doc.invoice_date
    today = frappe.utils.getdate(frappe.utils.nowdate())

    pi.bill_date = invoice_date
    pi.posting_date = invoice_date if invoice_date <= today else today

    pi.currency = doc.currency
    pi.update_stock = 0
    pi.ignore_pricing_rule = 1

    # ---------------- ITEMS ----------------
    for row in doc.items:
        pi.append("items", {
            "item_name": row.item_name,
            "qty": row.qty,
            "rate": row.rate,
            "expense_account": row.expense_account
        })

    # ---------------- TAXES ----------------
    for tax in doc.taxes:
        pi.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": tax.account_head,
            "description": tax.description,
            "rate": 0,
            "tax_amount": tax.tax_amount
        })

    pi.insert(ignore_permissions=True)

    # ---------------- LINK BACK ----------------
    doc.purchase_invoice = pi.name
    doc.status = "Posted"
    doc.save(ignore_permissions=True)

    frappe.db.commit()

    return pi.name

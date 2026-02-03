import frappe
import json
import traceback
import re
from datetime import date, datetime

from invoice_ocr.vision.ocr_engine import run_vision_ocr
from invoice_ocr.ai.ocr_agent import run_ocr_agent


# ============================================================
# CONSTANTS & HELPERS
# ============================================================

CURRENCY_RE = r"[£$€₹₨]\s?([\d,]+\.\d{2})"


def json_safe(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def get_company():
    company = frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Default Company not set")
    return company


def get_expense_account(company):
    acc = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Expense", "is_group": 0},
        "name"
    )
    if not acc:
        frappe.throw("Expense account not found")
    return acc


def get_tax_account(company):
    acc = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": ["like", "%VAT%"], "is_group": 0},
        "name"
    )
    return acc


# ============================================================
# FALLBACK ITEM EXTRACTION (ACCOUNTING SAFE)
# ============================================================

def fallback_extract_items(text):
    items = []

    for line in text.splitlines():
        if "|" not in line:
            continue
        if re.search(r"(total|tax|grand)", line.lower()):
            continue

        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) < 2:
            continue

        rates = re.findall(CURRENCY_RE, line)
        if not rates:
            continue

        rate = float(rates[-1].replace(",", ""))

        items.append({
            "item_name": cols[1][:140],
            "qty": 1,
            "rate": rate,
            "amount": rate
        })

    return items


# ============================================================
# MAIN OCR
# ============================================================

@frappe.whitelist()
def run_ocr(docname):
    try:
        doc = frappe.get_doc("Invoice OCR", docname)
        company = get_company()

        # ---------------- STEP 1: OCR ----------------
        raw_text = run_vision_ocr(doc.invoice_file)
        doc.raw_ocr_text = raw_text

        # ---------------- STEP 2: AI ----------------
        result = run_ocr_agent(raw_text)

        header = result.get("header", {})
        items = result.get("items", [])
        taxes = result.get("taxes", [])
        confidence = result.get("confidence", 0)

        # ---------------- STEP 3: FALLBACK ----------------
        if not items:
            items = fallback_extract_items(raw_text)
            confidence = max(confidence, 60)

        # ---------------- HEADER ----------------
        doc.supplier_name = header.get("supplier_name")
        doc.invoice_number = header.get("invoice_number")
        doc.invoice_date = header.get("invoice_date")
        doc.currency = header.get("currency") or doc.currency

        # ---------------- ITEMS ----------------
        doc.items = []
        expense_account = get_expense_account(company)
        net_total = 0

        for it in items:
            net_total += it["amount"]

            doc.append("items", {
                "item_name": it["item_name"],
                "qty": it["qty"],
                "rate": it["rate"],
                "amount": it["amount"],
                "uom": "Nos",
                "expense_account": expense_account
            })

        # ---------------- TAX ----------------
        tax_total = 0
        doc.taxes = []

        tax_account = get_tax_account(company)
        if tax_account:
            grand_match = re.search(r"grand total.*?([\d,]+\.\d{2})", raw_text.lower())
            if grand_match:
                grand_total = float(grand_match.group(1).replace(",", ""))
                tax_total = round(grand_total - net_total, 2)

                if tax_total > 0:
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
        doc.grand_total = net_total + tax_total

        # ---------------- META ----------------
        doc.semantic_invoice_json = json.dumps({
            "header": header,
            "items": items,
            "taxes": taxes,
            "totals": {
                "net_total": net_total,
                "tax_total": tax_total,
                "grand_total": doc.grand_total
            }
        }, indent=2)

        doc.confidence = confidence
        doc.status = "Ready"

        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "net_total": net_total,
            "tax_total": tax_total,
            "grand_total": doc.grand_total,
            "confidence": confidence
        }

    except Exception as e:
        frappe.log_error(traceback.format_exc(), "Invoice OCR Failed")
        frappe.throw(str(e))

# ============================================================
# CREATE PURCHASE INVOICE (FINAL – ERP SAFE)
# ============================================================

@frappe.whitelist()
def create_purchase_invoice(docname):
    doc = frappe.get_doc("Invoice OCR", docname)

    if doc.status != "Ready":
        frappe.throw("OCR is not Ready")

    if doc.purchase_invoice:
        frappe.throw("Purchase Invoice already created")

    if not doc.supplier:
        frappe.throw("Please select Supplier")

    if not doc.items:
        frappe.throw("No items found")

    company = frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw("Default Company not set")

    pi = frappe.new_doc("Purchase Invoice")
    pi.company = company
    pi.supplier = doc.supplier
    pi.bill_no = doc.invoice_number
    pi.bill_date = doc.invoice_date
    pi.posting_date = doc.invoice_date
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
            "charge_type": tax.charge_type,
            "account_head": tax.account_head,
            "rate": tax.rate,
            "tax_amount": tax.tax_amount
        })

    pi.flags.ignore_mandatory = True
    pi.insert(ignore_permissions=True)
    pi.submit()

    # ---------------- LINK BACK ----------------
    doc.purchase_invoice = pi.name
    doc.status = "Posted"
    doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
    "status": "success",
    "purchase_invoice": pi.name,
    "redirect": f"/app/purchase-invoice/{pi.name}"
}


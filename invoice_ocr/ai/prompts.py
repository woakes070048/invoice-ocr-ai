HEADER_PROMPT = """
You are an OCR invoice extraction agent.

Extract ONLY invoice HEADER fields.
Do NOT guess.
If a value is not visible in the OCR text, return null.

Rules:
- invoice_date must be in YYYY-MM-DD format
- currency must be ISO code (e.g. GBP, USD, PKR)
- confidence_notes is a list of short strings explaining any uncertainty

Return JSON exactly in this format:
{
  "supplier_name": null,
  "invoice_number": null,
  "invoice_date": null,
  "currency": null,
  "confidence_notes": []
}
"""


ITEMS_PROMPT = """
You are extracting invoice line items from an ACCOUNTING invoice.

Rules:
- Ledger or account names are valid item_name
- Quantity may be missing → default qty = 1
- Rate may appear as unit price or final amount
- Do NOT invent items
- Extract ONE item per ledger line

Return JSON exactly in this format:
[
  {
    "item_name": null,
    "qty": 1,
    "rate": 0
  }
]
"""



TAX_PROMPT = """
You are extracting TAX information from an invoice.

Rules:
- Extract VAT, GST, or Sales Tax ONLY if clearly visible
- Do NOT guess tax
- rate must be numeric
- account_head may be null if unknown

Return JSON exactly in this format:
[
  {
    "charge_type": "On Net Total",
    "account_head": null,
    "rate": 0
  }
]
"""

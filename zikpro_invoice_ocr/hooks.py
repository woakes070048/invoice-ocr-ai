app_name = "zikpro_invoice_ocr"
app_title = "Zikpro AI Invoice OCR"
app_publisher = "Zikpro Ltd"
app_description = "AI-powered Invoice OCR to Purchase Invoice automation using DeepInfra"
app_email = "info@zikpro.com"
app_license = "MIT"

# -------------------------------------------------
# Required Apps
# -------------------------------------------------
required_apps = ["erpnext"]

# -------------------------------------------------
# DocType JS
# -------------------------------------------------
doctype_js = {
    "Invoice OCR": "public/js/invoice_ocr.js"
}

# -------------------------------------------------
# Optional: App visibility in Desk (disabled)
# -------------------------------------------------
# add_to_apps_screen = [
#     {
#         "name": "invoice_ocr",
#         "logo": "/assets/zikpro_invoice_ocr/logo.png",
#         "title": "OCR-AI",
#         "route": "/invoice_ocr",
#         "has_permission": "zikpro_invoice_ocr.api.permission.has_app_permission"
#     }
# ]

frappe.ui.form.on("Invoice OCR", {

    refresh(frm) {

        frm.clear_custom_buttons();
        frm.page.clear_primary_action();

        frm.add_custom_button("📸 Open Camera", () => {

            let input = document.createElement("input");
            input.type = "file";
            input.accept = "image/*";
            input.capture = "environment";

            input.onchange = function(e) {

                let file = e.target.files[0];
                if (!file) return;

                let reader = new FileReader();

                reader.onload = function() {

                    let base64 = reader.result.split(",")[1];

                    frappe.call({
                        method: "invoice_ocr.api.upload_camera_image",
                        args: {
                            docname: frm.doc.name,
                            filename: file.name,
                            filedata: base64
                        },
                        freeze: true,
                        freeze_message: __("Uploading image..."),
                        callback: function() {
                            frm.reload_doc();
                        }
                    });
                };

                reader.readAsDataURL(file);
            };

            input.click();
        });

        if (frm.doc.invoice_file && frm.doc.status === "Draft") {

            frm.add_custom_button("▶ Run OCR", () => {

                frm.call({
                    method: "invoice_ocr.api.run_ocr",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Running OCR...")
                }).then(() => {
                    frm.reload_doc();
                });

            });
        }

        if (frm.doc.status === "Ready" && !frm.doc.purchase_invoice) {

            frm.add_custom_button("🧾 Generate Purchase Invoice", async () => {

                if (frm.is_dirty()) {
                    await frm.save();
                }

                await frm.call({
                    method: "invoice_ocr.api.create_purchase_invoice",
                    args: { docname: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Creating Purchase Invoice...")
                });

                frm.reload_doc();
            });
        }

        if (frm.doc.purchase_invoice) {

            frm.add_custom_button("📄 View Purchase Invoice", () => {
                frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice);
            });
        }
    }
});
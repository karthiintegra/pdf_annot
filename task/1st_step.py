# summa.py
# Convert InDesign GoToR (remote) links to internal GoTo links
# Keeps tags, bookmarks, structure tree intact
# Generates a CSV report with all converted links

import os
import csv

try:
    from pdfixsdk import *  # or `from pdfix import *` depending on your environment
except ImportError:
    from pdfixsdk import *

# Input and Output files
INPUT_PDF = r"c:\Users\is6076\Downloads\full_merge_2025.pdf"
OUTPUT_PDF = os.path.splitext(INPUT_PDF)[0] + "_links_fixed.pdf"
CSV_REPORT = os.path.splitext(INPUT_PDF)[0] + "_link_report.csv"

# Helper for Pdfix error handling
def _check(ok, pdfix: "Pdfix"):
    if ok:
        return
    err_type = pdfix.GetErrorType()
    err = pdfix.GetError()
    desc = pdfix.GetErrorDescription()
    raise RuntimeError(f"Pdfix error {err_type}: {err} | {desc}")

# Open the PDF
def open_doc(pdfix: "Pdfix", path: str) -> "PdfDoc":
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    doc = pdfix.OpenDoc(path, "")
    if not doc:
        _check(False, pdfix)
    return doc

# Convert a single link annotation if it has a GoToR action
def ensure_internal_goto(pdfix: "Pdfix", doc: "PdfDoc", page_index: int, annot_index: int, link_annot: "PdfLinkAnnot", report_rows: list):
    action = link_annot.GetAction()
    if not action:
        return False

    subtype = action.GetSubtype()
    if subtype != kActionGoToR:
        return False

    view_dest = action.GetViewDestination()
    if not view_dest:
        return False

    dest_page_num = view_dest.GetPageNum(doc)
    if dest_page_num < 0 or dest_page_num >= doc.GetNumPages():
        return False

    new_dest = doc.CreateViewDestination(dest_page_num, kDestFit, PdfRect(), 0.0)
    if not new_dest:
        return False

    new_action = doc.CreateAction(kActionGoTo)
    if not new_action:
        return False

    _check(new_action.SetViewDestination(new_dest), pdfix)
    _check(link_annot.SetAction(new_action), pdfix)

    # Add entry to report
    report_rows.append({
        "Source Page": page_index + 1,
        "Destination Page": dest_page_num + 1
    })

    print(f"✅ Converted link on page {page_index+1} ➜ destination page {dest_page_num+1}")
    return True

# Walk all link annotations in the PDF
def process_links(pdfix: "Pdfix", doc: "PdfDoc", report_rows: list) -> int:
    updated = 0
    for page_idx in range(doc.GetNumPages()):
        page = doc.AcquirePage(page_idx)
        if not page:
            continue
        try:
            ann_count = page.GetNumAnnots()
            for i in range(ann_count):
                annot = page.GetAnnot(i)
                if not annot:
                    continue
                if annot.GetSubtype() != kAnnotLink:
                    continue

                link = PdfLinkAnnot(annot.obj)
                if not link:
                    continue

                if ensure_internal_goto(pdfix, doc, page_idx, i, link, report_rows):
                    updated += 1
        finally:
            page.Release()
    return updated

# Export a CSV report of converted links
def export_csv_report(report_rows: list, csv_path: str):
    if not report_rows:
        print("📄 No links were converted, skipping CSV export.")
        return

    with open(csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["Source Page", "Destination Page"])
        writer.writeheader()
        for row in report_rows:
            writer.writerow(row)

    print(f"📊 CSV report generated: {csv_path}")

# Main function
def main():
    pdfix = GetPdfix()
    if not pdfix:
        raise RuntimeError("❌ Failed to initialize Pdfix SDK.")

    try:
        doc = open_doc(pdfix, INPUT_PDF)
        print(f"📄 Opened PDF: {INPUT_PDF}")
        print(f"📌 Total pages: {doc.GetNumPages()}")

        report_rows = []
        changes = process_links(pdfix, doc, report_rows)
        print(f"🔗 Links converted (GoToR ➜ GoTo): {changes}")

        _check(doc.Save(OUTPUT_PDF, kSaveFull), pdfix)
        print(f"💾 Saved fixed PDF: {OUTPUT_PDF}")

        export_csv_report(report_rows, CSV_REPORT)

        doc.Close()
    finally:
        pdfix.Destroy()

if __name__ == "__main__":
    main()

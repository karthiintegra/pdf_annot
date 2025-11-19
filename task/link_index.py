# final_converter_with_visible_alt.py
from pdfixsdk import *
import os, csv, traceback

INPUT_PDF = r"C:\Users\IS12765\Desktop\see11.pdf"
OUTPUT_PDF = os.path.splitext(INPUT_PDF)[0] + "_links_fixed.pdf"
CSV_REPORT = os.path.splitext(INPUT_PDF)[0] + "_link_report.csv"

def set_link_alt_readable(annot, text):
    """Correct way to set link description Acrobat will show."""
    try:
        annot.SetContents(text)
        return True
    except:
        pass

    try:
        obj = annot.GetObject()
        obj.PutString("Contents", text)
        return True
    except:
        return False


def get_dest_page_num(doc, dest):
    try:
        return dest.GetPageNum(doc)  # correct for your PDFix version
    except:
        return None


def create_goto_action(doc, page_num):
    try:
        fit = kDestFit
        rect = PdfRect()
        rect.left = rect.top = rect.right = rect.bottom = 0

        dest = doc.CreateViewDestination(page_num, fit, rect, 0.0)
        if not dest:
            return None

        action = doc.CreateAction(kActionGoTo)
        if not action:
            return None

        if not action.SetViewDestination(dest):
            return None

        return action
    except:
        traceback.print_exc()
        return None


def main():
    pdfix = GetPdfix()
    doc = pdfix.OpenDoc(INPUT_PDF, "")

    pages = doc.GetNumPages()
    print("Opened:", INPUT_PDF)
    print("Pages:", pages)

    converted = 0
    report_rows = []

    for p in range(pages):
        page = doc.AcquirePage(p)
        annots = page.GetNumAnnots()

        for i in range(annots):
            annot = page.GetAnnot(i)
            if annot.GetSubtype() != kAnnotLink:
                continue

            link = PdfLinkAnnot(annot.obj)
            action = link.GetAction()
            if not action:
                continue

            dest = action.GetViewDestination()
            if not dest:
                continue

            dest_page = get_dest_page_num(doc, dest)
            if dest_page is None or dest_page < 0 or dest_page >= pages:
                continue

            print(f"Page {p+1}, Link {i}: GoTo page {dest_page+1}")

            # create internal action
            new_action = create_goto_action(doc, dest_page)
            if not new_action:
                continue

            if not link.SetAction(new_action):
                continue

            # real alt text visible in Acrobat
            alt_text = f"{dest_page+1}"
            set_link_alt_readable(annot, alt_text)

            # optional: set ActualText in structure
            try:
                struct_obj = annot.GetStructObject(0)
                if struct_obj:
                    elem = doc.GetStructTree().GetStructElementFromObject(struct_obj)
                    elem.SetActualText(alt_text)
            except:
                pass

            report_rows.append({
                "Source Page": p+1,
                "Destination Page": dest_page+1,
                "Alt Text": alt_text
            })

            converted += 1

        page.Release()

    print("Converted:", converted)

    doc.Save(OUTPUT_PDF, kSaveFull)
    print("Saved:", OUTPUT_PDF)

    # csv
    if report_rows:
        with open(CSV_REPORT, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Source Page", "Destination Page", "Alt Text"])
            w.writeheader()
            w.writerows(report_rows)
        print("CSV:", CSV_REPORT)

    doc.Close()
    pdfix.Destroy()


if __name__ == "__main__":
    main()

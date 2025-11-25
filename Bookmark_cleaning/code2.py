import os
from pdfixsdk import *

def remove_filtered_bookmarks(input_pdf, output_pdf, filters):
    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception("PDFix initialization failed")

    doc = pdfix.OpenDoc(input_pdf, "")
    if doc is None:
        raise Exception("Failed to open PDF: " + pdfix.GetError())

    root = doc.GetBookmarkRoot()
    if root is not None:
        filters_lower = [f.lower() for f in filters]

        def clean(parent):
            i = 0
            count = parent.GetNumChildren()
            while i < count:
                child = parent.GetChild(i)

                clean(child)  # recurse first

                title = (child.GetTitle() or "").lower()
                match = any(f in title for f in filters_lower)

                if match:
                    sub_count = child.GetNumChildren()
                    for s in range(sub_count):
                        sub = child.GetChild(s)
                        parent.AddChild(i, sub)
                        i += 1
                        count += 1

                    parent.RemoveChild(i)
                    count -= 1
                    continue

                i += 1

        clean(root)

    if not doc.Save(output_pdf, kSaveFull):
        err = pdfix.GetError()
        doc.Close()
        raise Exception("Save failed: " + err)

    doc.Close()


def process_folder(input_folder, output_folder, filters):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("⚠ No PDF files found in folder:", input_folder)
        return

    for pdf_name in pdf_files:
        input_pdf = os.path.join(input_folder, pdf_name)
        output_pdf = os.path.join(output_folder, pdf_name)  # same name

        print(f"🔄 Processing: {pdf_name}")
        try:
            remove_filtered_bookmarks(input_pdf, output_pdf, filters)
            print(f"✅ Saved → {output_pdf}\n")
        except Exception as e:
            print(f"❌ Failed: {pdf_name} → {e}\n")

    print("🎉 Folder processing complete!")


if __name__ == "__main__":
    input_folder  = r"\\integrafs3\ShareYourDocuments\CTAE\karthi\New folder"
    output_folder = r"\\integrafs3\ShareYourDocuments\CTAE\karthi\New folder\output"
    filters = [".pdf", "outline placeholder"]   # or add more filters

    process_folder(input_folder, output_folder, filters)

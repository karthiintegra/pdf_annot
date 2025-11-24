from pdfixsdk import *


def remove_filtered_bookmarks(input_pdf, output_pdf, filters):
    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception("PDFix initialization failed")

    doc = pdfix.OpenDoc(input_pdf, "")
    if doc is None:
        raise Exception("Failed to open PDF: " + pdfix.GetError())

    root = doc.GetBookmarkRoot()
    if root is None:
        print("No bookmarks found.")
    else:
        filters_lower = [f.lower() for f in filters]

        def clean(parent):
            i = 0
            count = parent.GetNumChildren()
            while i < count:
                child = parent.GetChild(i)

                # Recurse first
                clean(child)

                title = (child.GetTitle() or "").lower()
                match = any(f in title for f in filters_lower)

                if match:
                    # Move child's children into parent at the same position
                    sub_count = child.GetNumChildren()
                    for s in range(sub_count):
                        sub = child.GetChild(s)
                        # Insert this sub-bookmark into parent, before removing pdf bookmark
                        parent.AddChild(i, sub)
                        i += 1
                        count += 1

                    # Now remove .pdf bookmark itself
                    parent.RemoveChild(i)

                    # Do NOT increment i here (because next bookmark is already at same index)
                    count -= 1
                    continue

                i += 1

        clean(root)

    if not doc.Save(output_pdf, kSaveFull):
        err = pdfix.GetError()
        doc.Close()
        raise Exception("Save failed: " + err)

    doc.Close()
    print("Removed only .pdf / Outline placeholder bookmarks and kept structure intact.")
    print("Saved:", output_pdf)


def main():
    input_pdf = r"C:\Users\IS12765\Downloads\20-11-2025\booksmark\978-3-032-09127-7_Book_OnlinePDF_Incorrect.pdf"
    output_pdf = r"C:\Users\IS12765\Downloads\20-11-2025\booksmark\978-3-032-09127-7_Book_OnlinePDF_Filtered.pdf"

    filters = [".pdf", "outline placeholder"]
    remove_filtered_bookmarks(input_pdf, output_pdf, filters)


if __name__ == "__main__":
    main()

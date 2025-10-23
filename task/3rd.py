from pdfixsdk import *
import re
from DeleteTags import *

pdfix = GetPdfix()

def process_struct_elem(elem: PdsStructElement):
    """
    Recursively traverse the structure tree and replace <_Note_> tags with <Note>.
    """
    # Check current element type
    elem_type = elem.GetType(False)
    if elem_type == "_Note_":
        print(f"📝 Found <_Note_> tag — replacing with <Note>")
        elem.SetType("Note")

    # Traverse children
    num_children = elem.GetNumChildren()
    for i in range(num_children):
        if elem.GetChildType(i) == kPdsStructChildElement:
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if child_elem:
                process_struct_elem(child_elem)


def modify_pdf_tags(input_path, output_path):
    """
    Open the PDF, traverse the tag tree, replace <_Note_> tags,
    save the modified PDF, and run post-processing.
    """
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception(f"❌ Failed to open PDF: {pdfix.GetError()}")

    struct_tree = doc.GetStructTree()
    if not struct_tree:
        raise Exception("❌ No structure tree found in PDF")

    # Traverse top-level children
    for i in range(struct_tree.GetNumChildren()):
        obj = struct_tree.GetChildObject(i)
        elem = struct_tree.GetStructElementFromObject(obj)
        if elem:
            process_struct_elem(elem)

    # Save the modified PDF
    if not doc.Save(output_path, kSaveFull):
        raise Exception(f"❌ Failed to save PDF: {pdfix.GetError()}")

    doc.Close()
    print(f"✅ PDF modified and saved to: {output_path}")

    # Optional cleanup
    final_output = r"final_output.pdf"
    delete_tags_in_pdf(output_path, final_output)
    print(f"🧹 Post-processing done. Final file: {final_output}")


if __name__ == "__main__":
    input_pdf = r"c:\Users\is6076\Downloads\output_with_links.pdf"
    output_pdf = r"c:\Users\is6076\Downloads\modify_____.pdf"
    print("🔹 Starting tag rename process...")
    modify_pdf_tags(input_pdf, output_pdf)
    print("✅ Process completed.")

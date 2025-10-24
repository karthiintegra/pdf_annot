from pdfixsdk import *
import uuid
import re

pdfix = GetPdfix()


def starts_with_number(text):
    return bool(re.match(r"^\d+\.(\d+\.(\d+\.)?)?\s+(.*)", text))


def process_struct_elem(elem: PdsStructElement, parent: PdsStructElement = None):
    # Only check when parent is present
    if parent is not None:
        caption_index = -1
        figure_index = -1
        caption_elem = None
        figure_elem = None

        # 1️⃣ Find Caption and Figure inside the same parent
        for i in range(parent.GetNumChildren()):
            if parent.GetChildType(i) != kPdsStructChildElement:
                continue

            obj = parent.GetChildObject(i)
            child = parent.GetStructTree().GetStructElementFromObject(obj)
            if not child:
                continue

            if child.GetType(False) == "Caption":
                caption_index = i
                caption_elem = child
            elif child.GetType(False) == "Figure":
                figure_index = i
                figure_elem = child

        # 2️⃣ If both found, move Caption under Figure
        if caption_elem is not None and figure_elem is not None:
            # adjust index if caption is before figure
            if caption_index < figure_index:
                figure_index -= 1

            parent.MoveChild(caption_index, figure_elem, -1)
            print("✅ Caption moved under Figure")

    # 3️⃣ Recursive traversal
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if child_elem:
                process_struct_elem(child_elem, elem)


def modify_pdf_tags(input_path, output_path):
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception("Failed to open PDF")
    # print("COme")
    struct_tree = doc.GetStructTree()
    for i in range(struct_tree.GetNumChildren()):
        obj = struct_tree.GetChildObject(i)
        elem = struct_tree.GetStructElementFromObject(obj)
        if elem:
            process_struct_elem(elem)

    if not doc.Save(output_path, kSaveFull):
        raise Exception("Failed to save PDF")
    final_output = r"final_output.pdf"
    print(f"PDF modified and saved to: {output_path}")


modify_pdf_tags(r"C:\Users\IS12765\Downloads\modify2.pdf", r'C:\Users\IS12765\Downloads\modify3.pdf')

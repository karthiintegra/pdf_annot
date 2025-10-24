from pdfixsdk import *
import uuid
import re

pdfix = GetPdfix()


def starts_with_number(text):
    return bool(re.match(r"^\d+\.(\d+\.(\d+\.)?)?\s+(.*)", text))


def process_struct_elem(elem: PdsStructElement, parent: PdsStructElement = None):
    # 1️⃣ Check if the current element is Caption
    if elem.GetType(False) == "Caption":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) != kPdsStructChildElement:
                continue

            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if not child_elem:
                continue

            # 2️⃣ If the child is Figure
            if child_elem.GetType(False) == "Figure" and parent is not None:
                print("🪄 Found Figure inside Caption, moving it up to parent...")

                # 3️⃣ Move Figure from Caption (elem) to its parent (Story)
                elem.MoveChild(i, parent, -1)
                print("✅ Figure moved to parent successfully")
                return  # stop after moving

    # 4️⃣ Recurse into children and pass current element as parent
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


modify_pdf_tags(r"C:\Users\IS12765\Downloads\modify1.pdf", r'C:\Users\IS12765\Downloads\modify2.pdf')

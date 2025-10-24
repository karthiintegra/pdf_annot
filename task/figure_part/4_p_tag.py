from pdfixsdk import *
import re

pdfix = GetPdfix()

def starts_with_number(text):
    return bool(re.match(r"^\d+\.(\d+\.(\d+\.)?)?\s+(.*)", text))


def process_struct_elem(elem: PdsStructElement):
    # ✅ Step 1: Check if the current element is a Figure
    if elem.GetType(False) == "Figure":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) != kPdsStructChildElement:
                continue

            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if not child_elem:
                continue

            # ✅ Step 2: Look for Caption inside Figure
            if child_elem.GetType(False) == "Caption":
                print("🪄 Found Caption inside Figure")

                num_children = child_elem.GetNumChildren()
                if num_children == 0:
                    print("⚠️ Caption is empty")
                    continue

                # ✅ Step 3: Add new <P> inside Caption
                p_elem = child_elem.AddNewChild("P", -1)

                # ✅ Step 4: Move all existing children of Caption into P
                for _ in range(num_children):
                    # Always move index 0, because children shift down after each move
                    child_elem.MoveChild(0, p_elem, -1)

                print(f"✅ Moved {num_children} children into new <P> tag under Caption")

    # ✅ Step 5: Recursive traversal
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if child_elem:
                process_struct_elem(child_elem)


def modify_pdf_tags(input_path, output_path):
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception("❌ Failed to open PDF")

    struct_tree = doc.GetStructTree()
    for i in range(struct_tree.GetNumChildren()):
        obj = struct_tree.GetChildObject(i)
        elem = struct_tree.GetStructElementFromObject(obj)
        if elem:
            process_struct_elem(elem)

    if not doc.Save(output_path, kSaveFull):
        raise Exception("❌ Failed to save PDF")

    print(f"✅ PDF modified and saved to: {output_path}")


# 🧪 Example usage
modify_pdf_tags(
    r"C:\Users\IS12765\Downloads\modify4.pdf",
    r"C:\Users\IS12765\Downloads\modify5.pdf"
)

from pdfixsdk import *
import uuid
import re

pdfix = GetPdfix()


def starts_with_number(text):
    return bool(re.match(r"^\d+\.(\d+\.(\d+\.)?)?\s+(.*)", text))


def process_struct_elem(elem: PdsStructElement):
    if elem.GetType(False) == "Story":
        for i in range(elem.GetNumChildren()):
            child_type = elem.GetChildType(i)
            if child_type == kPdsStructChildElement:
                obj = elem.GetChildObject(i)
                child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
                if child_elem.GetType(False) == "Caption":
                    print('note')
                print(elem.GetText(False))

                num_children = (elem.GetNumChildren())
                if num_children == 0:
                    return

                lbl_elem = elem.AddNewChild("lb1l", 0)
                for _ in range(num_children):
                    elem.MoveChild(1, lbl_elem, -1)





    for i in range(elem.GetNumChildren()):
        child_type = elem.GetChildType(i)
        if child_type == kPdsStructChildElement:
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            process_struct_elem(child_elem)


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


modify_pdf_tags(r"C:\Users\IS12765\Downloads\07_9780443184529_Ch03.pdf", r'C:\Users\IS12765\Downloads\modify1.pdf')

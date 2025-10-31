from pdfixsdk import *
import re
import json
import ctypes

# ============================================================
# Initialize Pdfix
# ============================================================
pdfix = GetPdfix()
if pdfix is None:
    raise Exception("❌ Pdfix initialization failed")


# ============================================================
# Helper: Convert JSON dict → raw Pdfix memory stream data
# ============================================================
def jsonToRawData(json_dict):
    json_str = json.dumps(json_dict)
    json_data = bytearray(json_str.encode("utf-8"))
    json_data_size = len(json_str)
    json_data_raw = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
    return json_data_raw, json_data_size


# ============================================================
# 1️⃣ Rename <Story> → <Sect> inside <Article>
# ============================================================
def process_article_story(elem: PdsStructElement):
    st = elem.GetStructTree()
    elem = st.GetStructElementFromObject(elem.GetObject())
    if not elem:
        return

    if elem.GetType(False) == "Article":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) == kPdsStructChildElement:
                obj = elem.GetChildObject(i)
                child = st.GetStructElementFromObject(obj)
                if child and child.GetType(False) == "Story":
                    print("🧩 <Story> → <Sect>")
                    child.SetType("Sect")

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            process_article_story(st.GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 2️⃣ Rename <Span> → <P> inside <_No_paragraph_style_>
# ============================================================
def process_no_paragraph_style(elem: PdsStructElement):
    st = elem.GetStructTree()
    elem = st.GetStructElementFromObject(elem.GetObject())
    if not elem:
        return

    if elem.GetType(False) == "_No_paragraph_style_":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) == kPdsStructChildElement:
                obj = elem.GetChildObject(i)
                child = st.GetStructElementFromObject(obj)
                if child and child.GetType(False) == "Span":
                    print("🧩 <Span> → <P>")
                    child.SetType("P")

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            process_no_paragraph_style(st.GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 3️⃣ Delete unwanted tags safely
# ============================================================
def delete_tags_in_pdf(doc, tag_name):
    json_dict = {
        "commands": [
            {
                "name": "delete_tags",
                "params": [
                    {"name": "tag_names", "value": tag_name},
                    {"name": "exclude_tag_names", "value": "false"},
                    {"name": "skip_tag_names", "value": ""},
                    {"name": "flags", "value": 255},
                    {"name": "tag_content", "value": "move"},
                ],
            }
        ]
    }

    json_data, json_size = jsonToRawData(json_dict)
    memStm = pdfix.CreateMemStream()
    memStm.Write(0, json_data, json_size)
    command = doc.GetCommand()
    command.LoadParamsFromStream(memStm, kDataFormatJson)
    memStm.Destroy()

    print(f"🗑️ Removing all <{tag_name}> tags...")
    if not command.Run():
        raise Exception("❌ Failed to delete tags: " + pdfix.GetError())


# ============================================================
# 4️⃣ Move (1) text node into <Figure> under <Eq_num>
# ============================================================
def move_number_into_figure(elem: PdsStructElement):
    st = elem.GetStructTree()
    elem = st.GetStructElementFromObject(elem.GetObject())
    if not elem:
        return
    if elem.GetType(False) == "Eq_num":
        figure_elem, number_index = None, -1
        for i in range(elem.GetNumChildren()):
            ctype, cobj = elem.GetChildType(i), elem.GetChildObject(i)
            if ctype != kPdsStructChildElement:
                number_index = i
                continue
            child = st.GetStructElementFromObject(cobj)
            if child and child.GetType(False) == "Figure":
                figure_elem = child
        if figure_elem and number_index != -1:
            eq_ref = st.GetStructElementFromObject(elem.GetObject())
            fig_ref = st.GetStructElementFromObject(figure_elem.GetObject())
            if eq_ref and fig_ref:
                eq_ref.MoveChild(number_index, fig_ref, -1)
                print("✅ Moved (1) into Figure")
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            move_number_into_figure(st.GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 5️⃣ Move space nodes from Eq_num → previous <P>
# ============================================================
def _is_whitespace_struct(elem: PdsStructElement) -> bool:
    try:
        txt = elem.GetText(True)
        return txt is not None and txt.strip() == ""
    except Exception:
        return False


def _move_kid(eq_elem, kid_index, dest_p):
    st = eq_elem.GetStructTree()
    fresh_eq = st.GetStructElementFromObject(eq_elem.GetObject())
    fresh_dest = st.GetStructElementFromObject(dest_p.GetObject())
    if not (fresh_eq and fresh_dest):
        return
    if not fresh_eq.MoveChild(kid_index, fresh_dest, -1):
        cobj = fresh_eq.GetChildObject(kid_index)
        if cobj:
            fresh_dest.AddKidObject(cobj, -1)
            fresh_eq.RemoveChild(kid_index)


def _move_space_from_eqnum_to_previous_p(grand):
    st = grand.GetStructTree()
    grand = st.GetStructElementFromObject(grand.GetObject())
    if not grand:
        return
    last_p_elem = None
    for i in range(grand.GetNumChildren()):
        if grand.GetChildType(i) != kPdsStructChildElement:
            continue
        cobj = grand.GetChildObject(i)
        child = st.GetStructElementFromObject(cobj)
        if not child:
            continue
        tag = child.GetType(False)
        if tag == "P":
            last_p_elem = child
        elif tag == "Eq_num" and last_p_elem:
            candidates = []
            for k in range(child.GetNumChildren()):
                ktype = child.GetChildType(k)
                if ktype in (kPdsStructChildPageContent, kPdsStructChildStreamContent):
                    candidates.append(k)
                elif ktype == kPdsStructChildElement:
                    s_elem = st.GetStructElementFromObject(child.GetChildObject(k))
                    if s_elem and _is_whitespace_struct(s_elem):
                        candidates.append(k)
            for idx in reversed(candidates):
                _move_kid(child, idx, last_p_elem)
                print("🪶 Moved space into preceding <P>")


def traverse(elem):
    _move_space_from_eqnum_to_previous_p(elem)
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            traverse(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 6️⃣ Rename <Figure> → <Formula> under <Eq_num>
# ============================================================
def rename_figure_to_formula(elem):
    st = elem.GetStructTree()
    elem = st.GetStructElementFromObject(elem.GetObject())
    if not elem:
        return
    if elem.GetType(False) == "Eq_num":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) == kPdsStructChildElement:
                child = st.GetStructElementFromObject(elem.GetChildObject(i))
                if child and child.GetType(False) == "Figure":
                    print("🧩 <Figure> → <Formula>")
                    child.SetType("Formula")
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            rename_figure_to_formula(st.GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 7️⃣ Delete <Article> and 8️⃣ Delete <Eq_num>
# ============================================================
def delete_article_tags(doc):
    delete_tags_in_pdf(doc, "Article")


def delete_eqnum_tags(doc):
    delete_tags_in_pdf(doc, "Eq_num")


# ============================================================
# 9️⃣ Rename <_Figure_> → <__Figure__> inside <Story>
# ============================================================
def rename_nested_figure(elem: PdsStructElement):
    if elem.GetType(False) == "Story":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) != kPdsStructChildElement:
                continue
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if not child_elem:
                continue
            if child_elem.GetType(False) == "_Figure_":
                for j in range(child_elem.GetNumChildren()):
                    if child_elem.GetChildType(j) == kPdsStructChildElement:
                        sub_obj = child_elem.GetChildObject(j)
                        sub_elem = child_elem.GetStructTree().GetStructElementFromObject(sub_obj)
                        if sub_elem and sub_elem.GetType(False) == "Figure":
                            print("🧩 <_Figure_> → <__Figure__>")
                            child_elem.SetType("__Figure__")
                            break

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            rename_nested_figure(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 🔟 Wrap <Story> content into <lb1l> if it has <__Figure__>
# ============================================================
def wrap_story_with_lb1l(elem: PdsStructElement):
    if elem.GetType(False) == "Story":
        contains_double_fig = any(
            elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)).GetType(False) == "__Figure__"
            for i in range(elem.GetNumChildren())
            if elem.GetChildType(i) == kPdsStructChildElement
        )

        if contains_double_fig:
            print("🧩 Wrapping <Story> content into <lb1l>")
            num_children = elem.GetNumChildren()
            if num_children == 0:
                return
            lbl_elem = elem.AddNewChild("lb1l", 0)
            for _ in range(num_children):
                if elem.GetNumChildren() > 1:
                    elem.MoveChild(1, lbl_elem, -1)

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            wrap_story_with_lb1l(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))


# ============================================================
# 1️⃣1️⃣ Move <Figure> out of <__Figure__> to parent
# ============================================================
def move_figure_out_of_double_figure(elem: PdsStructElement, parent: PdsStructElement = None):
    if elem.GetType(False) == "__Figure__":
        st = elem.GetStructTree()
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) != kPdsStructChildElement:
                continue
            obj = elem.GetChildObject(i)
            child_elem = st.GetStructElementFromObject(obj)
            if not child_elem:
                continue

            if child_elem.GetType(False) == "Figure" and parent is not None:
                print("🪄 Found <Figure> inside <__Figure__>, moving it up to parent...")
                fresh_parent = st.GetStructElementFromObject(parent.GetObject())
                fresh_elem = st.GetStructElementFromObject(elem.GetObject())
                if fresh_parent and fresh_elem:
                    fresh_elem.MoveChild(i, fresh_parent, -1)
                    print("✅ Figure moved to parent successfully")
                return

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            move_figure_out_of_double_figure(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)),
                                             elem)


# ============================================================
# 1️⃣2️⃣ Move <__Figure__> under <Figure>
# ============================================================
def move_caption_under_figure(elem: PdsStructElement, parent: PdsStructElement = None):
    if parent is not None:
        caption_index = -1
        figure_index = -1
        caption_elem = None
        figure_elem = None

        for i in range(parent.GetNumChildren()):
            if parent.GetChildType(i) != kPdsStructChildElement:
                continue

            obj = parent.GetChildObject(i)
            child = parent.GetStructTree().GetStructElementFromObject(obj)
            if not child:
                continue

            if child.GetType(False) == "__Figure__":
                caption_index = i
                caption_elem = child
            elif child.GetType(False) == "Figure":
                figure_index = i
                figure_elem = child

        if caption_elem is not None and figure_elem is not None:
            if caption_index < figure_index:
                figure_index -= 1
            parent.MoveChild(caption_index, figure_elem, -1)
            print("✅ <__Figure__> moved under <Figure>")

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            move_caption_under_figure(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)), elem)


# ============================================================
# 1️⃣3️⃣ Add <P> inside <__Figure__> under <Figure>
# ============================================================
def add_p_inside_caption(elem: PdsStructElement):
    if elem.GetType(False) == "Figure":
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) != kPdsStructChildElement:
                continue
            obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(obj)
            if not child_elem:
                continue
            if child_elem.GetType(False) == "__Figure__":
                print("🪄 Found <__Figure__> inside <Figure>")
                num_children = child_elem.GetNumChildren()
                if num_children == 0:
                    print("⚠️ Caption is empty")
                    continue
                p_elem = child_elem.AddNewChild("P", -1)
                for _ in range(num_children):
                    child_elem.MoveChild(0, p_elem, -1)
                print(f"✅ Moved {num_children} children into new <P> under Caption")

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            add_p_inside_caption(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))




# ============================================================
# MASTER FUNCTION
# ============================================================
def modify_pdf_tags(input_path, output_path):
    doc = pdfix.OpenDoc(input_path, "")
    if not doc:
        raise Exception("❌ Failed to open PDF")
    st = doc.GetStructTree()
    if not st:
        raise Exception("❌ No structure tree found")

    print("🔍 Starting all PDF tag transformations...")
    for i in range(st.GetNumChildren()):
        elem = st.GetStructElementFromObject(st.GetChildObject(i))
        if elem:
            process_article_story(elem)
            process_no_paragraph_style(elem)
            move_number_into_figure(elem)
            traverse(elem)
            rename_figure_to_formula(elem)
            rename_nested_figure(elem)
            wrap_story_with_lb1l(elem)
            move_figure_out_of_double_figure(elem)
            move_caption_under_figure(elem)
            add_p_inside_caption(elem)

    delete_article_tags(doc)
    delete_tags_in_pdf(doc, "_No_paragraph_style_")
    delete_eqnum_tags(doc)

    if not doc.Save(output_path, kSaveFull):
        raise Exception(f"❌ Failed to save PDF: {pdfix.GetError()}")

    doc.Close()
    print(f"✅ All transformations complete. Saved: {output_path}")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    modify_pdf_tags(
        r"D:\Karthik\9780443275982chp4_Actual_InDesign_output (1).pdf",
        r"D:\Karthik\work2__.pdf"
    )





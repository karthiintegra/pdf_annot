from pdfixsdk import *
import json
import re
import ctypes


# ============================================================
# CLASS 1 → Phase 1 (Steps 1–13)
# ============================================================
class PdfTagTransformerPhase1:
    """Handles steps 1–13 of the PDF tag transformation process."""

    def __init__(self, pdfix):
        self.pdfix = pdfix
        if not pdfix:
            raise Exception("❌ Pdfix initialization failed")

    # -------------------- Helper --------------------
    def jsonToRawData(self, json_dict):
        json_str = json.dumps(json_dict)
        json_data = bytearray(json_str.encode("utf-8"))
        json_data_size = len(json_str)
        json_data_raw = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
        return json_data_raw, json_data_size

    # -------------------- Step 1 --------------------
    def process_article_story(self, elem: PdsStructElement):
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
                self.process_article_story(st.GetStructElementFromObject(elem.GetChildObject(i)))

    # -------------------- Step 2 --------------------
    def process_no_paragraph_style(self, elem: PdsStructElement):
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
                self.process_no_paragraph_style(st.GetStructElementFromObject(elem.GetChildObject(i)))

    # -------------------- Step 3 --------------------
    def delete_tags_in_pdf(self, doc, tag_name):
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

        json_data, json_size = self.jsonToRawData(json_dict)
        memStm = self.pdfix.CreateMemStream()
        memStm.Write(0, json_data, json_size)
        command = doc.GetCommand()
        command.LoadParamsFromStream(memStm, kDataFormatJson)
        memStm.Destroy()

        print(f"🗑️ Removing <{tag_name}>...")
        if not command.Run():
            raise Exception("❌ Failed to delete tags: " + self.pdfix.GetError())

    # ============================================================
    # 4️⃣ Move (1) text node into <Figure> under <Eq_num>
    # ============================================================
    def move_number_into_figure(self,elem: PdsStructElement):
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
                self.move_number_into_figure(st.GetStructElementFromObject(elem.GetChildObject(i)))

    # ============================================================
    # 5️⃣ Move space nodes from Eq_num → previous <P>
    # ============================================================
    def _is_whitespace_struct(self,elem: PdsStructElement) -> bool:
        try:
            txt = elem.GetText(True)
            return txt is not None and txt.strip() == ""
        except Exception:
            return False

    def _move_kid(self,eq_elem, kid_index, dest_p):
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

    def _move_space_from_eqnum_to_previous_p(self,grand):
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
                        if s_elem and self._is_whitespace_struct(s_elem):
                            candidates.append(k)
                for idx in reversed(candidates):
                    self._move_kid(child, idx, last_p_elem)
                    print("🪶 Moved space into preceding <P>")

    def traverse(self,elem):
        self._move_space_from_eqnum_to_previous_p(elem)
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) == kPdsStructChildElement:
                self.traverse(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))

    # ============================================================
    # 6️⃣ Rename <Figure> → <Formula> under <Eq_num>
    # ============================================================
    def rename_figure_to_formula(self,elem):
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
                self.rename_figure_to_formula(st.GetStructElementFromObject(elem.GetChildObject(i)))

    # ============================================================
    # 7️⃣ Delete <Article> and 8️⃣ Delete <Eq_num>
    # ============================================================
    def delete_article_tags(self,doc):
        self.delete_tags_in_pdf(doc, "Article")

    def delete_eqnum_tags(self,doc):
        self.delete_tags_in_pdf(doc, "Eq_num")

    # ============================================================
    # 9️⃣ Rename <_Figure_> → <__Figure__> inside <Story>
    # ============================================================
    def rename_nested_figure(self,elem: PdsStructElement):
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
                self.rename_nested_figure(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))

    # ============================================================
    # 🔟 Wrap <Story> content into <lb1l> if it has <__Figure__>
    # ============================================================
    def wrap_story_with_lb1l(self,elem: PdsStructElement):
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
                self.wrap_story_with_lb1l(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))

    # ============================================================
    # 1️⃣1️⃣ Move <Figure> out of <__Figure__> to parent
    # ============================================================
    def move_figure_out_of_double_figure(self,elem: PdsStructElement, parent: PdsStructElement = None):
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
                self.move_figure_out_of_double_figure(
                    elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)),
                    elem)

    # ============================================================
    # 1️⃣2️⃣ Move <__Figure__> under <Figure>
    # ============================================================
    def move_caption_under_figure(self,elem: PdsStructElement, parent: PdsStructElement = None):
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
                self.move_caption_under_figure(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)), elem)

    # ============================================================
    # 1️⃣3️⃣ Add <P> inside <__Figure__> under <Figure>
    # ============================================================
    def add_p_inside_caption(self,elem: PdsStructElement):
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
                self.add_p_inside_caption(elem.GetStructTree().GetStructElementFromObject(elem.GetChildObject(i)))

    # -------------------- Run All Steps --------------------
    def modify_pdf_tags(self, input_path, output_path):
        doc = self.pdfix.OpenDoc(input_path, "")
        if not doc:
            raise Exception("❌ Failed to open PDF")

        st = doc.GetStructTree()
        if not st:
            raise Exception("❌ No structure tree found")

        print("🚀 Starting Phase 1 transformations...")

        for i in range(st.GetNumChildren()):
            elem = st.GetStructElementFromObject(st.GetChildObject(i))
            if elem:
                self.process_article_story(elem)
                self.process_no_paragraph_style(elem)
                self.move_number_into_figure(elem)
                self.traverse(elem)
                self.rename_figure_to_formula(elem)
                self.rename_nested_figure(elem)
                self.wrap_story_with_lb1l(elem)
                self.move_figure_out_of_double_figure(elem)
                self.move_caption_under_figure(elem)
                self.add_p_inside_caption(elem)

        self.delete_tags_in_pdf(doc, "Article")
        self.delete_tags_in_pdf(doc, "_No_paragraph_style_")
        self.delete_tags_in_pdf(doc, "Eq_num")

        if not doc.Save(output_path, kSaveFull):
            raise Exception(f"❌ Failed to save PDF: {self.pdfix.GetError()}")

        doc.Close()
        print(f"✅ Phase 1 complete. Saved to: {output_path}")


# ============================================================
# CLASS 2 → Phase 2 (Future Steps 14–30)
# ============================================================
class Reference:
    """Handles Steps 14–30 (new operations)."""

    def __init__(self, pdfix):
        self.pdfix = pdfix

    def step14_move_references_p_to_l(self, elem: PdsStructElement, parent: PdsStructElement = None):
        """Step 14: Find <H2> tag with 'References' and move all following <P> tags under new <L> tag."""
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ Step 1: Detect H2 tag with "References"
        if fresh_elem.GetType(False) == "H2":
            text_content = fresh_elem.GetText(True)
            if text_content and text_content.strip().lower() == "references":
                print("📘 Found 'References' H2 tag — collecting following <P> tags...")

                if parent:
                    start_index = None

                    # Find index of the H2 tag within its parent
                    for i in range(parent.GetNumChildren()):
                        if parent.GetChildType(i) != kPdsStructChildElement:
                            continue
                        obj = parent.GetChildObject(i)
                        sibling = st.GetStructElementFromObject(obj)
                        if sibling and sibling.GetObject().obj == fresh_elem.GetObject().obj:
                            start_index = i
                            break

                    if start_index is not None:
                        # ✅ Create new <L> tag right after <H2>
                        l_elem = parent.AddNewChild("L", start_index + 1)
                        l_struct = st.GetStructElementFromObject(l_elem.GetObject())

                        if not l_struct:
                            print("⚠️ Failed to create <L> tag")
                            return

                        print("🧩 Created <L> tag for reference paragraphs")

                        # ✅ Keep moving <P> tags after <H2> dynamically until none remain
                        moved_count = 0
                        while True:
                            moved = False
                            total_children = parent.GetNumChildren()

                            for j in range(start_index + 1, total_children):
                                if parent.GetChildType(j) != kPdsStructChildElement:
                                    continue
                                obj = parent.GetChildObject(j)
                                sibling = st.GetStructElementFromObject(obj)
                                if sibling and sibling.GetType(False) == "P":
                                    parent.MoveChild(j, l_struct, -1)
                                    moved_count += 1
                                    moved = True
                                    break  # restart after move to update structure

                            if not moved:
                                break  # stop when no more <P> remain

                        print(f"✅ Moved {moved_count} <P> tags under new <L>")

        # ✅ Step 2: Continue recursion
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step14_move_references_p_to_l(child_elem, fresh_elem)  # your future logic for deleting Story and lb1l

    def step15_wrap_p_into_li(self, elem: PdsStructElement):
        """Step 15: Wrap all <P> tags under <L> into a single <LI> tag."""
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ Identify <L> tags
        if fresh_elem.GetType(False) == "L":
            print("🧩 Found <L> tag — wrapping its content into <LI>")

            num_children = fresh_elem.GetNumChildren()
            if num_children == 0:
                return

            # ✅ Create new <LI> tag at the beginning
            li_elem = fresh_elem.AddNewChild("LI", 0)
            li_struct = st.GetStructElementFromObject(li_elem.GetObject())
            if not li_struct:
                print("⚠️ Failed to create <LI> tag")
                return

            moved_count = 0
            # ✅ Move all existing children (except the newly created <LI>) into it
            # Always move index 1, since index 0 is the new <LI> itself
            while fresh_elem.GetNumChildren() > 1:
                fresh_elem.MoveChild(1, li_struct, -1)
                moved_count += 1

            print(f"✅ Moved {moved_count} children into <LI> under <L>")

        # ✅ Recurse into children
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step15_wrap_p_into_li(child_elem)

    def step16_rename_p_to_lbody_in_li(self, elem: PdsStructElement):
        """Step 16: Inside each <LI> tag, rename <P> to <LBody>."""
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ If current element is <LI>
        if fresh_elem.GetType(False) == "LI":
            print("🧩 Found <LI> tag — converting <P> to <LBody>")
            for i in range(fresh_elem.GetNumChildren()):
                if fresh_elem.GetChildType(i) != kPdsStructChildElement:
                    continue
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if not child_elem:
                    continue

                if child_elem.GetType(False) == "P":
                    print("🔹 Found <P> under <LI> — renaming to <LBody>")
                    child_elem.SetType("LBody")

        # ✅ Recursively process all descendants
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step16_rename_p_to_lbody_in_li(child_elem)  # move T_credit tag under Table logic

    def step17_split_multiple_lbody_in_li(self, elem: PdsStructElement):
        """Step 17: If an <LI> has multiple <LBody> children, move each into its own <LI>."""
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ Only process <L> tags
        if fresh_elem.GetType(False) == "L":
            print("🔍 Processing <L> structure...")

            # Collect LI children
            li_indices = []
            for i in range(fresh_elem.GetNumChildren()):
                if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                    obj = fresh_elem.GetChildObject(i)
                    child = st.GetStructElementFromObject(obj)
                    if child and child.GetType(False) == "LI":
                        li_indices.append(i)

            # ✅ Process each <LI>
            for li_index in reversed(li_indices):
                li_obj = fresh_elem.GetChildObject(li_index)
                li_elem = st.GetStructElementFromObject(li_obj)
                if not li_elem:
                    continue

                # Find all <LBody> children
                lbody_indices = []
                for j in range(li_elem.GetNumChildren()):
                    if li_elem.GetChildType(j) == kPdsStructChildElement:
                        obj = li_elem.GetChildObject(j)
                        child = st.GetStructElementFromObject(obj)
                        if child and child.GetType(False) == "LBody":
                            lbody_indices.append(j)

                # ✅ If multiple LBodies — split them
                if len(lbody_indices) > 1:
                    print(f"🧩 Found <LI> with {len(lbody_indices)} <LBody> — splitting...")

                    # Move each LBody (except the first) into a new <LI>
                    for idx in reversed(lbody_indices[1:]):
                        lbody_obj = li_elem.GetChildObject(idx)
                        if not lbody_obj:
                            continue

                        # Create a new LI right after the current one
                        new_li = fresh_elem.AddNewChild("LI", li_index + 1)
                        new_li_elem = st.GetStructElementFromObject(new_li.GetObject())
                        if not new_li_elem:
                            continue

                        # Move the LBody into the new LI
                        li_elem.MoveChild(idx, new_li_elem, -1)
                        print("✅ Moved one <LBody> into new <LI>")

        # ✅ Recurse through children
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step17_split_multiple_lbody_in_li(child_elem)

    def modify_pdf_tags(self, input_path, output_path):
        doc = self.pdfix.OpenDoc(input_path, "")
        if not doc:
            raise Exception("❌ Failed to open PDF")

        st = doc.GetStructTree()
        print("🚀 Starting Phase 2 transformations...")

        for i in range(st.GetNumChildren()):
            elem = st.GetStructElementFromObject(st.GetChildObject(i))
            if elem:
                self.step14_move_references_p_to_l(elem)
                self.step15_wrap_p_into_li(elem)
                self.step16_rename_p_to_lbody_in_li(elem)
                self.step17_split_multiple_lbody_in_li(elem)

        if not doc.Save(output_path, kSaveFull):
            raise Exception(f"❌ Failed to save: {self.pdfix.GetError()}")

        doc.Close()
        print(f"✅ Phase 2 complete. Saved to: {output_path}")


class Table:
    """Handles Steps 14–30 (new operations)."""

    def __init__(self, pdfix):
        self.pdfix = pdfix

    def step18_fix_table_structure(self, elem: PdsStructElement):
        """Detect <Table> tags and restructure TRs into <THead> and <TBody>."""
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ Process only <Table> elements
        if fresh_elem.GetType(False) == "Table":
            print("📊 Found <Table> — restructuring TRs into <THead> and <TBody>")

            tr_indices = []
            for i in range(fresh_elem.GetNumChildren()):
                if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                    obj = fresh_elem.GetChildObject(i)
                    child = st.GetStructElementFromObject(obj)
                    if child and child.GetType(False) == "TR":
                        tr_indices.append(i)

            # ✅ Only proceed if multiple TR tags exist
            if len(tr_indices) > 1:
                # Create <THead> and <TBody> under <Table>
                thead = fresh_elem.AddNewChild("THead", 0)
                tbody = fresh_elem.AddNewChild("TBody", -1)

                thead_elem = st.GetStructElementFromObject(thead.GetObject())
                tbody_elem = st.GetStructElementFromObject(tbody.GetObject())

                if not thead_elem or not tbody_elem:
                    print("⚠️ Failed to create <THead> or <TBody>")
                    return

                print(f"🧩 Created <THead> and <TBody> with {len(tr_indices)} <TR> tags")

                # ✅ Move first TR into <THead>
                first_tr_index = tr_indices[0]
                # Add offset of +2 since <THead> and <TBody> are already added
                adjusted_index = min(first_tr_index + 2, fresh_elem.GetNumChildren() - 1)
                fresh_elem.MoveChild(adjusted_index, thead_elem, -1)
                print("✅ Moved first <TR> to <THead>")

                # ✅ Move remaining TRs into <TBody>
                while True:
                    moved = False
                    for i in range(fresh_elem.GetNumChildren()):
                        if fresh_elem.GetChildType(i) != kPdsStructChildElement:
                            continue
                        obj = fresh_elem.GetChildObject(i)
                        child = st.GetStructElementFromObject(obj)
                        if child and child.GetType(False) == "TR":
                            fresh_elem.MoveChild(i, tbody_elem, -1)
                            moved = True
                            break
                    if not moved:
                        break

                print("✅ Remaining <TR> tags moved to <TBody>")

        # ✅ Recurse through children
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step18_fix_table_structure(child_elem)



    def step19_move_tcredit_under_table(self, elem: PdsStructElement):
        st = elem.GetStructTree()
        fresh_elem = st.GetStructElementFromObject(elem.GetObject())
        if not fresh_elem:
            return

        # ✅ Only process <Story> elements
        if fresh_elem.GetType(False) == "Story":
            figure_elem = None
            tcredit_elem = None

            # 1️⃣ Find <_Figure_> and <T_credit>
            for i in range(fresh_elem.GetNumChildren()):
                if fresh_elem.GetChildType(i) != kPdsStructChildElement:
                    continue

                obj = fresh_elem.GetChildObject(i)
                child = st.GetStructElementFromObject(obj)
                if not child:
                    continue

                tag = child.GetType(False)
                if tag == "_Figure_":
                    figure_elem = child
                elif tag == "T_credit":
                    tcredit_elem = child

            # 2️⃣ If both are found
            if figure_elem and tcredit_elem:
                table_elem = None
                for j in range(figure_elem.GetNumChildren()):
                    if figure_elem.GetChildType(j) == kPdsStructChildElement:
                        obj = figure_elem.GetChildObject(j)
                        child = st.GetStructElementFromObject(obj)
                        if child and child.GetType(False) == "Table":
                            table_elem = child
                            break

                # 3️⃣ Move <T_credit> into <Table>
                if table_elem:
                    print("🧩 Found <Story> with <_Figure_> + <Table> + sibling <T_credit>")
                    print("   Moving <T_credit> into <Table>...")

                    fresh_story = st.GetStructElementFromObject(fresh_elem.GetObject())
                    table_fresh = st.GetStructElementFromObject(table_elem.GetObject())

                    for i in range(fresh_story.GetNumChildren()):
                        if fresh_story.GetChildType(i) != kPdsStructChildElement:
                            continue
                        obj = fresh_story.GetChildObject(i)
                        if obj.obj == tcredit_elem.GetObject().obj:
                            fresh_story.MoveChild(i, table_fresh, -1)
                            print("✅ <T_credit> moved inside <Table>")
                            break

        # 4️⃣ Recurse into child elements
        for i in range(fresh_elem.GetNumChildren()):
            if fresh_elem.GetChildType(i) == kPdsStructChildElement:
                obj = fresh_elem.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(obj)
                if child_elem:
                    self.step19_move_tcredit_under_table(child_elem)




    # def step17_split_multiple_lbody_in_li(self, elem: PdsStructElement):
    #     pass
    def modify_pdf_tags(self, input_path, output_path):
        doc = self.pdfix.OpenDoc(input_path, "")
        if not doc:
            raise Exception("❌ Failed to open PDF")

        st = doc.GetStructTree()
        print("🚀 Starting Phase 2 transformations...")

        for i in range(st.GetNumChildren()):
            elem = st.GetStructElementFromObject(st.GetChildObject(i))
            if elem:
                self.step18_fix_table_structure(elem)
                self.step19_move_tcredit_under_table(elem)
                # self.step15_wrap_p_into_li(elem)
                # self.step16_rename_p_to_lbody_in_li(elem)
                # self.step17_split_multiple_lbody_in_li(elem)

        if not doc.Save(output_path, kSaveFull):
            raise Exception(f"❌ Failed to save: {self.pdfix.GetError()}")

        doc.Close()
        print(f"✅ Phase 2 complete. Saved to: {output_path}")



# ============================================================
# MAIN ENTRY POINT
# ============================================================
if __name__ == "__main__":
    pdfix = GetPdfix()

    # Run Phase 1 (Steps 1–13)
    phase1 = PdfTagTransformerPhase1(pdfix)
    phase1.modify_pdf_tags(
        r"C:\Users\IS12765\Downloads\work_final\9780443275982chp4_Actual_InDesign_output (1).pdf",
        r"C:\Users\IS12765\Downloads\work_final\phase1_output.pdf"
    )

    # Run Phase 2 (Steps 14–30)
    phase2 = Reference(pdfix)
    phase2.modify_pdf_tags(
        r"C:\Users\IS12765\Downloads\work_final\phase1_output.pdf",
        r"C:\Users\IS12765\Downloads\work_final\phase2_output.pdf"
    )
    transformer = Table(pdfix)
    transformer.modify_pdf_tags(
        r"C:\Users\IS12765\Downloads\work_final\phase2_output.pdf",
        r"C:\Users\IS12765\Downloads\work_final\phase3_output.pdf"
    )

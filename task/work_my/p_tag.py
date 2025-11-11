from pdfixsdk import *

pdfix = GetPdfix()
if not pdfix:
    raise Exception("❌ Failed to initialize Pdfix SDK")


def wrap_eqnum_in_p(elem: PdsStructElement, parent: PdsStructElement = None):
    """If an <ADA_Eq_num> is found, wrap it in a new <P> tag (PAC-safe)."""
    if not elem:
        return

    st = elem.GetStructTree()
    fresh_elem = st.GetStructElementFromObject(elem.GetObject())
    if not fresh_elem:
        return

    tag = fresh_elem.GetType(False)

    # ✅ Found an ADA_Eq_num — wrap it inside a <P>
    if tag == "ADA_Eq_num" and parent is not None:
        print("🧩 Found <ADA_Eq_num> — wrapping inside new <P>...")

        # 1️⃣ Find its index in the parent
        eq_idx = -1
        for i in range(parent.GetNumChildren()):
            if parent.GetChildType(i) != kPdsStructChildElement:
                continue
            obj = parent.GetChildObject(i)
            sib = st.GetStructElementFromObject(obj)
            if sib and sib.GetObject().obj == fresh_elem.GetObject().obj:
                eq_idx = i
                break

        if eq_idx == -1:
            print("⚠️ Could not locate ADA_Eq_num position in parent.")
        else:
            # 2️⃣ Create a new <P> before the ADA_Eq_num
            p_elem_obj = parent.AddNewChild("P", eq_idx)
            p_elem = st.GetStructElementFromObject(p_elem_obj.GetObject())

            if not p_elem:
                print("❌ Failed to create <P> tag.")
                return

            # 3️⃣ Move the ADA_Eq_num into <P>
            ok = parent.MoveChild(eq_idx + 1, p_elem, -1)
            if ok:
                print("✅ Successfully wrapped <ADA_Eq_num> inside <P>")
            else:
                print("⚠️ MoveChild failed — possible invalid structure link")

    # 4️⃣ Recurse deeper in the structure tree
    for i in range(fresh_elem.GetNumChildren()):
        if fresh_elem.GetChildType(i) == kPdsStructChildElement:
            child_obj = fresh_elem.GetChildObject(i)
            child_elem = st.GetStructElementFromObject(child_obj)
            if child_elem:
                wrap_eqnum_in_p(child_elem, fresh_elem)

def move_number_into_figure(self, elem: PdsStructElement):
    st = elem.GetStructTree()
    elem = st.GetStructElementFromObject(elem.GetObject())
    if not elem:
        return
    if elem.GetType(False) == "ADA_Eq_num":
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



def modify_pdf(input_path, output_path):
    """Main processor: open PDF, wrap all ADA_Eq_num tags in <P>, and save."""
    doc = pdfix.OpenDoc(input_path, "")
    if not doc:
        raise Exception("❌ Failed to open PDF")

    st = doc.GetStructTree()
    if not st:
        raise Exception("❌ Structure tree not found")

    print("🚀 Wrapping <ADA_Eq_num> tags in <P> (PAC-safe)...")

    for i in range(st.GetNumChildren()):
        root_obj = st.GetChildObject(i)
        root_elem = st.GetStructElementFromObject(root_obj)
        if root_elem:
            wrap_eqnum_in_p(root_elem, None)
    # Save modified file
    if not doc.Save(output_path, kSaveFull):
        raise Exception(f"❌ Save failed: {pdfix.GetError()}")

    doc.Close()
    print(f"✅ Completed. Saved to: {output_path}")


# -------- RUN --------
if __name__ == "__main__":
    modify_pdf(
        r"C:\Users\IS12765\Downloads\9780443275982chp3.pdf",
        r"C:\Users\IS12765\Downloads\ADA_EQNUM_WRAPPED_IN_P.pdf"
    )

    pdfix.Destroy()

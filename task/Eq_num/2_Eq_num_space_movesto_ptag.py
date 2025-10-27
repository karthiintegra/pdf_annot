from pdfixsdk import *

pdfix = GetPdfix()

# Utility: is a struct element effectively only whitespace?
def _is_whitespace_struct(elem: PdsStructElement) -> bool:
    try:
        txt = elem.GetText(True)
        return txt is not None and txt.strip() == ""
    except Exception:
        return False

def _move_kid(eq_elem: PdsStructElement, kid_index: int, dest_p: PdsStructElement) -> None:
    """
    Try to move a child (page content / stream content / struct element)
    from eq_elem to dest_p as the last child. Prefer MoveChild; if SDK
    rejects it for page/stream content, fallback to AddKidObject + RemoveChild.
    """
    # Try MoveChild first (works for both content and element kids in Pdfix)
    if eq_elem.MoveChild(kid_index, dest_p, -1):
        return
    # Fallback: AddKidObject + RemoveChild
    cobj = eq_elem.GetChildObject(kid_index)
    if cobj:
        dest_p.AddKidObject(cobj, -1)
        eq_elem.RemoveChild(kid_index)

def _move_space_from_eqnum_to_previous_p(grand: PdsStructElement) -> None:
    """
    In a container (grand), for each Eq_num, locate the nearest previous <P>,
    then move page/stream content kids (and whitespace-only wrapper tags)
    from Eq_num into that P.
    """
    # Walk children and remember the last seen <P>
    last_p_index = -1
    last_p_elem: PdsStructElement | None = None

    # We’ll traverse by index because we may modify children lists.
    i = 0
    while i < grand.GetNumChildren():
        ctype = grand.GetChildType(i)
        if ctype != kPdsStructChildElement:
            # Non-struct at grand level; skip
            i += 1
            continue

        cobj = grand.GetChildObject(i)
        child = grand.GetStructTree().GetStructElementFromObject(cobj)
        if not child:
            i += 1
            continue

        tag = child.GetType(False)

        if tag == "P":
            # Update the “nearest previous P”
            last_p_index = i
            last_p_elem = child
            i += 1
            continue

        if tag == "Eq_num" and last_p_elem is not None:
            # We have an Eq_num and a P before it -> move space kids into that P
            # Collect candidate child indices inside Eq_num:
            # - page content / stream content kids (Space/MCID)
            # - struct kids whose text is only whitespace
            candidates = []

            for k in range(child.GetNumChildren()):
                ktype = child.GetChildType(k)
                if ktype in (kPdsStructChildPageContent, kPdsStructChildStreamContent):
                    candidates.append(k)
                elif ktype == kPdsStructChildElement:
                    s_obj = child.GetChildObject(k)
                    s_elem = child.GetStructTree().GetStructElementFromObject(s_obj)
                    if s_elem and _is_whitespace_struct(s_elem):
                        candidates.append(k)

            # Move from high to low indices to avoid shifting issues
            for idx in reversed(candidates):
                _move_kid(child, idx, last_p_elem)

        # Keep walking
        i += 1

def traverse(elem: PdsStructElement, parent: PdsStructElement | None = None):
    # If elem has struct element kids, run the local re-parenting pass on this container
    _move_space_from_eqnum_to_previous_p(elem)

    # Recurse
    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            obj = elem.GetChildObject(i)
            child = elem.GetStructTree().GetStructElementFromObject(obj)
            if child:
                traverse(child, elem)

def modify_pdf_tags(input_path: str, output_path: str):
    doc = pdfix.OpenDoc(input_path, "")
    if not doc:
        raise Exception("Failed to open PDF")

    st = doc.GetStructTree()
    for i in range(st.GetNumChildren()):
        robj = st.GetChildObject(i)
        root = st.GetStructElementFromObject(robj)
        if root:
            traverse(root, None)

    if not doc.Save(output_path, kSaveFull):
        raise Exception(f"Failed to save PDF: {pdfix.GetError()}")

    doc.Close()
    print(f"✅ Space text node(s) moved into the preceding <P>. Saved: {output_path}")
modify_pdf_tags(
    r"C:\Users\IS12765\Downloads\output_equation_fixed.pdf",
    r"C:\Users\IS12765\Downloads\10.pdf"
)
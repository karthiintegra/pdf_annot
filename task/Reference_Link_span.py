from pdfixsdk import *

pdfix = GetPdfix()

def wrap_link_in_reference(elem: PdsStructElement, parent: PdsStructElement = None):
    st = elem.GetStructTree()
    fresh = st.GetStructElementFromObject(elem.GetObject())
    if not fresh:
        return

    tag = fresh.GetType(False)

    # If we find <Link> with a <Span> child
    if tag == "Link" and parent:
        has_span_child = False
        for i in range(fresh.GetNumChildren()):
            if fresh.GetChildType(i) == kPdsStructChildElement:
                child = st.GetStructElementFromObject(fresh.GetChildObject(i))
                if child and child.GetType(False) == "Span":
                    has_span_child = True
                    break

        if has_span_child:
            print("🔄 Found <Link> having <Span> → wrapping in <Reference>")

            # Create new <Reference> tag in parent at same position
            # Find index of this <Link> in parent
            link_index = None
            for j in range(parent.GetNumChildren()):
                if parent.GetChildType(j) == kPdsStructChildElement:
                    if parent.GetChildObject(j).obj == fresh.GetObject().obj:
                        link_index = j
                        break

            if link_index is not None:
                # Create <Reference> at same position
                ref_obj = parent.AddNewChild("Reference", link_index)
                ref_elem = st.GetStructElementFromObject(ref_obj.GetObject())

                # Now move the <Link> under <Reference>
                parent.MoveChild(link_index + 1, ref_elem, -1)
                print("✅ Wrapped successfully")

    # Recurse
    for i in range(fresh.GetNumChildren()):
        if fresh.GetChildType(i) == kPdsStructChildElement:
            child = st.GetStructElementFromObject(fresh.GetChildObject(i))
            if child:
                wrap_link_in_reference(child, fresh)


def modify_pdf(input_path, output_path):
    doc = pdfix.OpenDoc(input_path, "")
    if not doc:
        raise Exception("Failed to open PDF")

    st = doc.GetStructTree()

    for i in range(st.GetNumChildren()):
        elem = st.GetStructElementFromObject(st.GetChildObject(i))
        if elem:
            wrap_link_in_reference(elem, None)

    if not doc.Save(output_path, kSaveFull):
        raise Exception(pdfix.GetError())

    doc.Close()
    print("✅ Done. Saved to:", output_path)


# Run
if __name__ == "__main__":
    modify_pdf(
        r"C:\Users\IS12765\Downloads\devi\17-11-2025\Great Canon Slav-ePub-FIN_Web.pdf",
        r"C:\Users\IS12765\Downloads\output_reference.pdf"
    )
    pdfix.Destroy()


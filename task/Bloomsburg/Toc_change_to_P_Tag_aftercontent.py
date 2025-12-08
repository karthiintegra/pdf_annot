from pdfixsdk import *

def check_h2_content_followed_by_toc(pdf_path):
    pdfix = GetPdfix()
    doc = pdfix.OpenDoc(pdf_path, "")

    st = doc.GetStructTree()
    if not st:
        print("❌ No structure tree found")
        return

    print("\n🔍 Scanning for H2 tag containing 'content'...\n")

    def walk(elem, parent):
        tag = elem.GetType(False)

        # =========================================================
        #  CHECK FOR H2 TAG WITH TEXT "content"
        # =========================================================
        if tag == "H2":
            text_content = elem.GetText(True) or ""
            if "content" in text_content.lower():
                print("\n======================================")
                print("📘 FOUND <H2> TAG WITH TEXT 'content'")
                print("======================================")
                print(f"➡ Text: {text_content}")

                if not parent:
                    print("⚠ Parent not found → cannot check next element")
                else:
                    # Find THIS H2 index under parent
                    index = None
                    for i in range(parent.GetNumChildren()):
                        if parent.GetChildType(i) != kPdsStructChildElement:
                            continue
                        obj = parent.GetChildObject(i)
                        child = st.GetStructElementFromObject(obj)
                        if child and child.GetObject().obj == elem.GetObject().obj:
                            index = i
                            break

                    if index is None:
                        print("⚠ Could not find H2 index under parent")
                    else:
                        next_index = index + 1
                        if next_index < parent.GetNumChildren():

                            # Get next sibling element
                            if parent.GetChildType(next_index) == kPdsStructChildElement:
                                next_obj = parent.GetChildObject(next_index)
                                next_elem = st.GetStructElementFromObject(next_obj)
                                next_tag = next_elem.GetType(False)

                                print(f"➡ Next tag after H2: <{next_tag}>")

                                # =====================================================
                                #  RULE: If <TOC> follows <H2 content>, rename to <P>
                                # =====================================================
                                if next_tag == "TOC":
                                    print("✅ TRUE: The next tag is <TOC>")
                                    print("✏ Renaming <TOC> → <P> ...")

                                    if next_elem.SetType("P"):
                                        print("✅ Successfully renamed TOC → P")
                                    else:
                                        print("❌ Failed to rename TOC → P")
                                else:
                                    print("❌ FALSE: The next tag is NOT <TOC>")
                            else:
                                print("❌ FALSE: Next item is not a struct element")
                        else:
                            print("❌ FALSE: No element exists after this H2")

        # =========================================================
        #  Continue Recursion
        # =========================================================
        for i in range(elem.GetNumChildren()):
            if elem.GetChildType(i) == kPdsStructChildElement:
                obj = elem.GetChildObject(i)
                child = st.GetStructElementFromObject(obj)
                if child:
                    walk(child, elem)

    # Start scanning
    for i in range(st.GetNumChildren()):
        obj = st.GetChildObject(i)
        elem = st.GetStructElementFromObject(obj)
        walk(elem, None)

    # Save the modified PDF
    out_path = pdf_path.replace(".pdf", "_fixed.pdf")
    if doc.Save(out_path, kSaveFull):
        print(f"\n💾 Saved updated PDF → {out_path}")
    else:
        print("❌ Failed to save PDF:", pdfix.GetError())

    doc.Close()
    pdfix.Destroy()


# RUN TEST
check_h2_content_followed_by_toc(
    r"C:\Users\IS12765\Downloads\work\02-12-2025-bloomsberry\1182\9781350337848_web.pdf"
)

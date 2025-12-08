from pdfixsdk import *


class LTagListAttributeAdder:
    """
    Phase: Add /O /List + /ListNumbering /Decimal attribute
    to all <L> tags that currently have no attribute objects.
    """

    def __init__(self, pdfix):
        self.pdfix = pdfix
        if not pdfix:
            raise Exception("❌ Pdfix initialization failed")

    # -------------------- CORE STEP --------------------
    def _add_list_attr_to_L(self, elem: PdsStructElement):
        """
        For a single <L> element:
        - If it has NO attribute objects,
        - Write an /A array with one attribute dict:
              << /O /List /ListNumbering /Decimal >>
        directly into the underlying struct element dictionary.
        """
        st = elem.GetStructTree()
        fresh = st.GetStructElementFromObject(elem.GetObject())
        if not fresh:
            return

        tag = fresh.GetType(False)
        if tag != "L":
            return

        # Already has attribute objects? Then do nothing.
        num_attrs = fresh.GetNumAttrObjects()
        if num_attrs > 0:
            # print(f"ℹ️ <L> already has {num_attrs} attribute object(s) — skipping")
            return

        print("\n======================")
        print("FOUND <L> WITHOUT ATTRIBUTES")
        print("======================")

        # 1️⃣ Get underlying struct element dictionary
        se_obj = fresh.GetObject()
        if not se_obj:
            print("⚠️ Struct element has no underlying object")
            return

        if se_obj.GetObjectType() != kPdsDictionary:
            print("⚠️ Struct element object is not a dictionary")
            return

        elem_dict = PdsDictionary(se_obj.obj)

        # 2️⃣ Get owning PdfDoc
        doc = se_obj.GetDoc()
        if not doc:
            print("⚠️ Could not resolve PdfDoc from struct element object")
            return

        # 3️⃣ Ensure /A array exists on the struct element dictionary
        attrs_array = elem_dict.GetArray("A")
        if not attrs_array:
            print("🧩 Creating /A array on struct element dictionary")
            attrs_array = elem_dict.PutArray("A")

        if not attrs_array:
            print("⚠️ Failed to create /A array on element dict")
            return

        # 4️⃣ Create an INDIRECT attribute dictionary in this doc
        attr_dict = doc.CreateDictObject(True)
        if not attr_dict:
            print("⚠️ PdfDoc.CreateDictObject failed")
            return

        # 5️⃣ Fill the attribute dictionary:
        #     /O             /List
        #     /ListNumbering /Decimal
        if not attr_dict.PutName("O", "List"):
            print("⚠️ Failed to set O=List on attr dict")
        if not attr_dict.PutName("ListNumbering", "Decimal"):
            print("⚠️ Failed to set ListNumbering=Decimal on attr dict")

        # 6️⃣ Append this dictionary into /A array
        insert_pos = attrs_array.GetNumObjects()
        ok = attrs_array.Insert(insert_pos, attr_dict)
        if not ok:
            print("⚠️ Failed to insert attr dict into /A")
            return

        print("✅ List attributes attached via /A dict to <L>")

    # -------------------- TRAVERSAL --------------------
    def _walk(self, elem: PdsStructElement):
        """
        Recursive walk over the structure tree.
        """
        st = elem.GetStructTree()
        fresh = st.GetStructElementFromObject(elem.GetObject())
        if not fresh:
            return

        # Try to add attributes if this is <L> without attrs
        self._add_list_attr_to_L(fresh)

        # Recurse over children
        for i in range(fresh.GetNumChildren()):
            if fresh.GetChildType(i) == kPdsStructChildElement:
                child_obj = fresh.GetChildObject(i)
                child_elem = st.GetStructElementFromObject(child_obj)
                if child_elem:
                    self._walk(child_elem)

    # -------------------- PUBLIC API --------------------
    def modify_pdf_tags(self, input_path, output_path):
        """
        Open input PDF, walk structure tree, add attributes
        to <L> tags, and save to output_path.
        """
        doc = self.pdfix.OpenDoc(input_path, "")
        if not doc:
            raise Exception("❌ Failed to open PDF: " + self.pdfix.GetError())

        st = doc.GetStructTree()
        if not st:
            print("❌ No structure tree found")
            doc.Close()
            return

        print("🚀 Starting LTagListAttributeAdder phase...")
        print(f"   Input : {input_path}")
        print(f"   Output: {output_path}")

        # Walk top-level children
        for i in range(st.GetNumChildren()):
            obj = st.GetChildObject(i)
            elem = st.GetStructElementFromObject(obj)
            if elem:
                self._walk(elem)

        # Save the result
        if not doc.Save(output_path, kSaveFull):
            err = self.pdfix.GetError()
            doc.Close()
            raise Exception(f"❌ Failed to save PDF: {err}")

        doc.Close()
        print(f"✅ LTagListAttributeAdder complete. Saved to: {output_path}")


# ============================================================
# MAIN (example usage)
# ============================================================
if __name__ == "__main__":
    pdfix = GetPdfix()
    if not pdfix:
        raise Exception("❌ Pdfix init failed")

    phase = LTagListAttributeAdder(pdfix)
    phase.modify_pdf_tags(
        r"C:\Users\IS12765\Downloads\work\02-12-2025-bloomsberry\1212\9781440880711_web.pdf",
        r"C:\Users\IS12765\Downloads\work\02-12-2025-bloomsberry\1212\9781440880711_web__1.pdf",
    )

    pdfix.Destroy()


"""
Transfer XMP metadata from .xmp sidecar file to PDF — SAFE version (preserves bookmarks & tags).
"""

import xml.etree.ElementTree as ET
import os
import shutil
from datetime import datetime

# Prefer pikepdf
try:
    import pikepdf
    USE_PIKEPDF = True
except Exception:
    USE_PIKEPDF = False

# Optional fallback (NOT safe unless forced)
try:
    from pypdf import PdfReader, PdfWriter
    USE_PYPDF = True
except Exception:
    USE_PYPDF = False


class XMPtoPDFUpdater:
    """Read XMP and update PDF metadata without losing bookmarks/tags."""

    def __init__(self):
        self.namespaces = {
            'x': 'adobe:ns:meta/',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'xmp': 'http://ns.adobe.com/xap/1.0/',
            'pdf': 'http://ns.adobe.com/pdf/1.3/',
            'pdfx': 'http://ns.adobe.com/pdfx/1.3/',
            'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
            'xmpRights': 'http://ns.adobe.com/xap/1.0/rights/',
            'prism': 'http://prismstandard.org/namespaces/basic/2.0/',
            'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/'
        }

        for prefix, uri in self.namespaces.items():
            ET.register_namespace(prefix, uri)

    # -------------------------------------------------------------
    # XMP PARSING UTILITIES
    # -------------------------------------------------------------

    def get_text_from_element(self, element):
        if element is None:
            return None

        rdf = self.namespaces['rdf']

        alt = element.find(f"{{{rdf}}}Alt")
        if alt is not None:
            li = alt.find(f"{{{rdf}}}li")
            if li is not None and li.text:
                return li.text.strip()

        seq = element.find(f"{{{rdf}}}Seq")
        if seq is not None:
            return [li.text.strip() for li in seq.findall(f"{{{rdf}}}li") if li.text]

        bag = element.find(f"{{{rdf}}}Bag")
        if bag is not None:
            return [li.text.strip() for li in bag.findall(f"{{{rdf}}}li") if li.text]

        if element.text:
            return element.text.strip()

        return None

    def read_xmp_file(self, xmp_path, debug=True):
        tree = ET.parse(xmp_path)
        root = tree.getroot()

        metadata = {}

        if debug:
            print("\n" + "="*70)
            print("DEBUG: Analyzing XMP structure")
            print("="*70)

        descriptions = root.findall(f".//{{{self.namespaces['rdf']}}}Description")

        for i, desc in enumerate(descriptions):
            if debug:
                print(f"\nDescription block #{i+1}:")
            for child in desc:
                value = self.get_text_from_element(child)
                if debug and value:
                    ns = child.tag.split('}')[0][1:]
                    name = child.tag.split('}')[-1]
                    print(f"  {ns}:{name} = {value}")

        if debug:
            print("="*70 + "\n")

        # Extract metadata
        for desc in descriptions:
            title = desc.find(f"{{{self.namespaces['dc']}}}title")
            if title is not None:
                t = self.get_text_from_element(title)
                if t:
                    metadata["title"] = t

            creator = desc.find(f"{{{self.namespaces['dc']}}}creator")
            if creator is not None:
                c = self.get_text_from_element(creator)
                if c:
                    metadata["creator"] = "; ".join(c) if isinstance(c, list) else c

            desc_elem = desc.find(f"{{{self.namespaces['dc']}}}description")
            if desc_elem is not None:
                d = self.get_text_from_element(desc_elem)
                if d:
                    metadata["description"] = d

            subject = desc.find(f"{{{self.namespaces['dc']}}}subject")
            if subject is not None:
                s = self.get_text_from_element(subject)
                if s:
                    metadata["keywords"] = ", ".join(s) if isinstance(s, list) else s

        return metadata

    # -------------------------------------------------------------
    # BOOKMARK + TAG SAFETY CHECK (PIKEPDF)
    # -------------------------------------------------------------

    def _inspect_pdf_structure(self, pdf):
        """Check for bookmark tree (/Outlines) and tag tree (/StructTreeRoot)."""
        root = pdf.Root  # FIXED

        has_outlines = "Outlines" in root
        has_struct = "StructTreeRoot" in root

        return has_outlines, has_struct

    # -------------------------------------------------------------
    # SAFE METADATA UPDATE USING PIKEPDF
    # -------------------------------------------------------------

    def update_pdf_with_pikepdf(self, pdf_path, metadata, output_path):

        pdf = pikepdf.Pdf.open(pdf_path)

        has_out_before, has_struct_before = self._inspect_pdf_structure(pdf)
        print(f"Before update: Outlines={has_out_before}, StructureTags={has_struct_before}")

        # Backup original once
        backup_path = output_path + ".bak"
        if not os.path.exists(backup_path):
            shutil.copy2(pdf_path, backup_path)
            print(f"Backup saved: {backup_path}")

        with pdf.open_metadata() as meta:
            if "title" in metadata:
                meta["dc:title"] = metadata["title"]
            if "creator" in metadata:
                meta["dc:creator"] = [c.strip() for c in metadata["creator"].split(";")]
            if "description" in metadata:
                meta["dc:description"] = metadata["description"]
            if "keywords" in metadata:
                meta["dc:subject"] = [k.strip() for k in metadata["keywords"].split(",")]
                meta["pdf:Keywords"] = metadata["keywords"]

        pdf.save(output_path)

        # Re-check after update
        pdf2 = pikepdf.Pdf.open(output_path)
        has_out_after, has_struct_after = self._inspect_pdf_structure(pdf2)

        print(f"After update:  Outlines={has_out_after}, StructureTags={has_struct_after}")

        if has_out_before and not has_out_after:
            print("⚠ BOOKMARK LOSS DETECTED! Backup kept.")

        if has_struct_before and not has_struct_after:
            print("⚠ TAG STRUCTURE LOSS DETECTED! Backup kept.")

        print(f"✓ PDF updated safely using pikepdf: {output_path}")

    # -------------------------------------------------------------
    # DANGEROUS pypdf UPDATE (ONLY IF FORCED)
    # -------------------------------------------------------------

    def update_pdf_with_pypdf(self, pdf_path, metadata, output_path):
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        pdf_meta = dict(reader.metadata or {})

        if "title" in metadata:
            pdf_meta["/Title"] = metadata["title"]
        if "creator" in metadata:
            pdf_meta["/Author"] = metadata["creator"]
        if "description" in metadata:
            pdf_meta["/Subject"] = metadata["description"]
        if "keywords" in metadata:
            pdf_meta["/Keywords"] = metadata["keywords"]

        writer.add_metadata(pdf_meta)

        with open(output_path, "wb") as f:
            writer.write(f)

        print("⚠ WARNING: pypdf rebuilt PDF — bookmarks/tags may be lost.")

    # -------------------------------------------------------------
    # MAIN PROCESS
    # -------------------------------------------------------------

    def process(self, pdf_path, xmp_path, output_path=None, debug=True, allow_pypdf=False):

        if not os.path.exists(pdf_path):
            print("PDF not found:", pdf_path)
            return

        if not os.path.exists(xmp_path):
            print("XMP not found:", xmp_path)
            return

        print(f"Reading XMP: {xmp_path}")
        metadata = self.read_xmp_file(xmp_path, debug=debug)

        print("\nExtracted metadata:", metadata, "\n")

        if output_path is None:
            base, ext = os.path.splitext(pdf_path)
            output_path = base + "_updated" + ext

        # Prefer PikePDF
        if USE_PIKEPDF:
            print("Using safe PikePDF path...")
            self.update_pdf_with_pikepdf(pdf_path, metadata, output_path)
            return

        # Fallback only if user explicitly allows it
        if USE_PYPDF and allow_pypdf:
            print("Using UNSAFE PyPDF path...")
            self.update_pdf_with_pypdf(pdf_path, metadata, output_path)
            return

        print("ERROR: Neither pikepdf installed nor pypdf allowed.")
        print("Run: pip install pikepdf")
        return


# -------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: xmp.exe <pdf_file> <xmp_file>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    xmp_path = sys.argv[2]

    updater = XMPtoPDFUpdater()
    updater.process(pdf_path, xmp_path, output_path=None, debug=True, allow_pypdf=False)


# if __name__ == "__main__":
#     import sys
#     if len(sys.argv) < 3:
#         print("Usage: xmp.exe <pdf_file> <xmp_file>")
#         sys.exit(1)

#     pdf_path = sys.argv[1]
#     xmp_path = sys.argv[2]

#     updater = XMPtoPDFUpdater()
#     updater.process(pdf_path, xmp_path, output_path=None, debug=True, allow_pypdf=False)





"""
SMART MERGE XMP into PDF + CUSTOM PROPERTIES
Works with PikePDF 5.x – 9.x safely
"""

import os
from lxml import etree
import pikepdf

NSMAP = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "pdfx": "http://ns.adobe.com/pdfx/1.3/",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
}


# =====================================================================
# READ existing XMP
# =====================================================================
def read_existing_xmp(pdf_path):
    pdf = pikepdf.open(pdf_path)

    try:
        meta_stream = pdf.Root.Metadata
        raw = meta_stream.read_bytes()
    except Exception:
        raw = b""

    pdf.close()
    return raw


# =====================================================================
# READ new XMP file
# =====================================================================
def read_new_xmp(xmp_path):
    return open(xmp_path, "rb").read()


# =====================================================================
# SMART MERGE (append new rdf:Description blocks)
# =====================================================================
def smart_merge_xmp(existing_bytes, new_bytes):
    if not existing_bytes.strip():
        return new_bytes

    existing_root = etree.fromstring(existing_bytes)
    new_root = etree.fromstring(new_bytes)

    existing_rdf = existing_root.xpath("//rdf:RDF", namespaces=NSMAP)[0]
    new_rdf = new_root.xpath("//rdf:RDF", namespaces=NSMAP)[0]

    prop_map = {}

    for desc in existing_rdf.xpath("rdf:Description", namespaces=NSMAP):
        about = desc.get("{%s}about" % NSMAP['rdf'], "")
        for prop in desc:
            ns = prop.tag.split("}")[0][1:]
            name = prop.tag.split("}")[-1]
            prop_map[(about, ns, name)] = prop

    for new_desc in new_rdf.xpath("rdf:Description", namespaces=NSMAP):
        about = new_desc.get("{%s}about" % NSMAP['rdf'], "")

        target = None
        for d in existing_rdf.xpath("rdf:Description", namespaces=NSMAP):
            if d.get("{%s}about" % NSMAP['rdf'], "") == about:
                target = d
                break

        if target is None:
            existing_rdf.append(new_desc)
            continue

        for new_prop in new_desc:
            ns = new_prop.tag.split("}")[0][1:]
            name = new_prop.tag.split("}")[-1]
            key = (about, ns, name)

            if key in prop_map:
                old = prop_map[key]
                old.clear()
                old.text = new_prop.text
                for c in new_prop:
                    old.append(c)
            else:
                target.append(new_prop)
                prop_map[key] = new_prop

    final_xml = etree.tostring(existing_root, pretty_print=True, encoding="utf-8")

    return (
        b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n' +
        final_xml +
        b'\n<?xpacket end="w"?>'
    )


# =====================================================================
# EXTRACT CUSTOM PROPERTIES FROM MERGED XMP
# =====================================================================
def extract_custom_properties(merged_xmp):
    root = etree.fromstring(merged_xmp)
    custom = {}

    # helper: find ANY namespace → match by local-name()
    def find_any(tag_name):
        nodes = root.xpath(f"//*[local-name()='{tag_name}']")
        if nodes and nodes[0].text:
            return nodes[0].text.strip()
        return None

    # fix your fields
    custom["CrossmarkDomainExclusive"] = find_any("CrossmarkDomainExclusive")
    custom["CrossmarkMajorVersionDate"] = find_any("CrossmarkMajorVersionDate")

    custom["ElsevierWebPDFSpecifications"] = find_any("ElsevierWebPDFSpecifications")
    custom["doi"] = find_any("doi")
    custom["robots"] = find_any("robots")

    # only return non-empty
    return {k: v for k, v in custom.items() if v}


# =====================================================================
# WRITE MERGED XMP BACK TO PDF
# =====================================================================
def write_merged_xmp(pdf_path, merged_bytes, output_path):
    pdf = pikepdf.open(pdf_path)

    pdf.Root.Metadata = pikepdf.Stream(pdf, merged_bytes)

    pdf.save(output_path)
    pdf.close()
    # print("✓ Wrote merged XMP to:", output_path)


# =====================================================================
# WRITE CUSTOM PROPERTIES TO Acrobat “Custom Tab”
# =====================================================================
def write_custom_properties(output_pdf, custom_dict):
    pdf = pikepdf.open(output_pdf, allow_overwriting_input=True)
    info = pdf.docinfo

    for k, v in custom_dict.items():
        pdf_key = "/" + k    # ✔ PikePDF requires /Prefix
        info[pdf_key] = str(v)

    pdf.save()
    pdf.close()
    # print("✓ Custom properties written:", custom_dict)


# =====================================================================
# MAIN MERGE PROCESS
# =====================================================================
def smart_merge_into_pdf(pdf_path, xmp_path, output_path=None):
    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = base + "_XMPmerged" + ext

    # print("Reading existing XMP...")
    existing = read_existing_xmp(pdf_path)

    # print("Reading new XMP...")
    new = read_new_xmp(xmp_path)

    # print("Merging...")
    merged = smart_merge_xmp(existing, new)

    # print("Writing merged XMP...")
    write_merged_xmp(pdf_path, merged, output_path)

    # print("Extracting custom properties...")
    custom = extract_custom_properties(merged)

    # print("Writing custom properties...")
    write_custom_properties(output_path, custom)

    print("\n✔ COMPLETE")
    # print("✔ All existing XMP preserved")
    # print("✔ All new XMP appended")
    # print("✔ Custom properties updated")
    # print("✔ Extensis / FontSense preserved")
    print("→ Output:", output_path)


# =====================================================================
# CLI ENTRY
# =====================================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python merge.py input.pdf input.xmp [output.pdf]")
        sys.exit(1)

    inp = sys.argv[1]
    xmp = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None

    smart_merge_into_pdf(inp, xmp, out)

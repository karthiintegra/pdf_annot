"""
SMART MERGE XMP into PDF + CUSTOM PROPERTIES + FIXED KEYWORDS
Works with PikePDF 5.x – 9.x safely.
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
# SMART MERGE XMP (preserves existing + adds new)
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

        # find matching description
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
        b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        + final_xml +
        b'\n<?xpacket end="w"?>'
    )

# =====================================================================
# EXTRACT CUSTOM PROPERTIES
# =====================================================================
def extract_custom_properties(merged_xmp):
    root = etree.fromstring(merged_xmp)
    custom = {}

    def find_any(tag_name):
        nodes = root.xpath(f"//*[local-name()='{tag_name}']")
        if nodes and nodes[0].text:
            return nodes[0].text.strip()
        return None

    custom["CrossmarkDomainExclusive"] = find_any("CrossmarkDomainExclusive")
    custom["CrossmarkMajorVersionDate"] = find_any("CrossmarkMajorVersionDate")
    custom["ElsevierWebPDFSpecifications"] = find_any("ElsevierWebPDFSpecifications")
    custom["doi"] = find_any("doi")
    custom["robots"] = find_any("robots")

    return {k: v for k, v in custom.items() if v}

# =====================================================================
# WRITE MERGED XMP
# =====================================================================
def write_merged_xmp(pdf_path, merged_bytes, output_path):
    pdf = pikepdf.open(pdf_path)
    pdf.Root.Metadata = pikepdf.Stream(pdf, merged_bytes)
    pdf.save(output_path)
    pdf.close()

# =====================================================================
# CLEAN LEADING SEMICOLON
# =====================================================================
def clean_leading_semicolon(text):
    if not text:
        return text
    t = text.strip()
    if t.startswith(";"):
        return t.lstrip(";").strip()
    return t

# =====================================================================
# WRITE KEYWORDS CORRECTLY (XMP + Info Dictionary)
# =====================================================================
def write_keywords_into_xmp_and_info(output_pdf, merged_xmp):
    root = etree.fromstring(merged_xmp)

    # --- Extract keywords from dc:subject ---
    nodes = root.xpath("//*[local-name()='subject']")
    if not nodes:
        return

    kw_node = nodes[0]
    li_items = kw_node.xpath(".//*[local-name()='li']")

    if li_items:
        raw_keywords = "; ".join([li.text.strip() for li in li_items if li.text])
    else:
        raw_keywords = kw_node.text.strip() if kw_node.text else ""

    if not raw_keywords:
        return

    # Clean and split
    raw_keywords = clean_leading_semicolon(raw_keywords)
    kw_list = [k.strip() for k in raw_keywords.replace(",", ";").split(";") if k.strip()]
    kw_list = list(dict.fromkeys(kw_list))  # remove duplicates

    final_kw_string = "; ".join(kw_list)

    pdf = pikepdf.open(output_pdf, allow_overwriting_input=True)

    # --- Write into XMP ---
    with pdf.open_metadata(update_docinfo=False) as meta:
        meta["dc:subject"] = kw_list
        meta["pdf:Keywords"] = final_kw_string

    # --- Write into PDF Info Dictionary (Acrobat UI) ---
    info = pdf.docinfo
    info["/Keywords"] = final_kw_string

    pdf.save()
    pdf.close()

    # print("✓ Keywords written to XMP and Acrobat UI (/Keywords)")

# =====================================================================
# WRITE CUSTOM PROPERTIES (info dictionary)
# =====================================================================
def write_custom_properties(output_pdf, custom_dict):
    pdf = pikepdf.open(output_pdf, allow_overwriting_input=True)
    info = pdf.docinfo

    # Sort keys alphabetically to control display order in Acrobat
    for k in sorted(custom_dict.keys()):
        pdf_key = "/" + k
        info[pdf_key] = clean_leading_semicolon(str(custom_dict[k]))

    # Force Trapped = Unknown
    info["/Trapped"] = pikepdf.Name("/Unknown")

    # Cleanup stray leading semicolons
    for key in list(info.keys()):
        val = info.get(key)
        if isinstance(val, str) and val.strip().startswith(";"):
            info[key] = clean_leading_semicolon(val)

    pdf.save()
    pdf.close()

    # print("✓ Custom properties written in alphabetical order")

# =====================================================================
# MAIN MERGE PROCESS
# =====================================================================
def smart_merge_into_pdf(pdf_path, xmp_path, output_path=None):
    if output_path is None:
        base, ext = os.path.splitext(pdf_path)
        output_path = base + "_XMPmerged" + ext

    existing = read_existing_xmp(pdf_path)
    new = read_new_xmp(xmp_path)

    merged = smart_merge_xmp(existing, new)
    write_merged_xmp(pdf_path, merged, output_path)

    custom = extract_custom_properties(merged)
    write_custom_properties(output_path, custom)

    write_keywords_into_xmp_and_info(output_path, merged)

    print("\n✔ COMPLETE")
    print("→ Output:", output_path)

# =====================================================================
# CLI
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

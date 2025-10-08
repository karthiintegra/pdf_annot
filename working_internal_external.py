#!/usr/bin/env python3
# merged_final.py
"""
Merged version of your merge routine that combines robust internal remapping
with the simpler, reliable external /F extraction + matching logic.
"""

import os
import time
import traceback

# Prefer pypdf, fall back to PyPDF2.
try:
    from pypdf import PdfReader, PdfWriter
    import pypdf.generic as generic
    LIB = "pypdf"
except Exception:
    from PyPDF2 import PdfReader, PdfWriter, generic
    LIB = "PyPDF2"

print(f"Using PDF library: {LIB}")


def _decode_pdf_string(value):
    """Decode PDF strings/bytes to Python str (handles UTF-16 BOM and utf-8)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        try:
            if value.startswith(b"\xfe\xff") or value.startswith(b"\xff\xfe"):
                return value.decode("utf-16")
        except Exception:
            pass
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return value.decode("latin1", errors="ignore")
    # fallback
    try:
        return str(value)
    except Exception:
        return repr(value)


def _extract_filespec_filename(fspec):
    """
    Robustly get a filename string from a filespec object which may be:
     - bytes/str
     - IndirectObject
     - dict with /UF or /F
    Returns decoded string or None.
    """
    if fspec is None:
        return None

    # Resolve indirect if possible
    try:
        if isinstance(fspec, generic.IndirectObject):
            try:
                fspec = fspec.get_object()
            except Exception:
                # can't resolve indirect
                return _decode_pdf_string(repr(fspec))
    except Exception:
        pass

    # If dict-like filespec with /UF or /F
    try:
        if isinstance(fspec, dict):
            # prefer /UF then /F
            for key in ("/UF", "/F", "/DOS", "/Mac", "/Unix"):
                if key in fspec:
                    return _decode_pdf_string(fspec[key])
            if "/F" in fspec:
                return _decode_pdf_string(fspec["/F"])
            return _decode_pdf_string(str(fspec))
    except Exception:
        # continue to other checks
        pass

    # If direct string/bytes
    if isinstance(fspec, (str, bytes)):
        return _decode_pdf_string(fspec)

    # Fallback to str()
    return _decode_pdf_string(fspec)


def _resolve_named_dest_to_page(reader, name):
    """
    Try to resolve a named destination to a page index in the given reader.
    Defensive: returns None on any failure.
    """
    if name is None:
        return None
    if isinstance(name, bytes):
        name = _decode_pdf_string(name)

    try:
        # pypdf: reader.named_destinations
        nd = getattr(reader, "named_destinations", None)
        if nd and name in nd:
            dest = nd[name]
            try:
                get_num = getattr(reader, "get_destination_page_number", None)
                if callable(get_num):
                    pn = get_num(dest)
                    if pn is not None:
                        return int(pn)
            except Exception:
                pass
            try:
                p_obj = getattr(dest, "page", None)
                if p_obj is not None:
                    for i, p in enumerate(reader.pages):
                        if p == p_obj:
                            return i
            except Exception:
                pass
    except Exception:
        pass

    try:
        # PyPDF2 older API
        get_named = getattr(reader, "getNamedDestinations", None)
        if callable(get_named):
            nd = get_named()
            if name in nd:
                dest = nd[name]
                try:
                    get_num = getattr(reader, "get_destination_page_number", None)
                    if callable(get_num):
                        pn = get_num(dest)
                        if pn is not None:
                            return int(pn)
                except Exception:
                    pass
    except Exception:
        pass

    return None


def merge_pdfs_preserve_links(pdf_files, output_path, sleep_between_files=0.0, sleep_between_pages=0.0):
    """
    Merge PDFs and preserve/repair internal and external hyperlinks.
    Uses robust extraction & matching for external GoToR links (based on filename).
    """
    writer = PdfWriter()
    readers = []
    total_pages = 0

    # Open input PDFs and build readers list (keep file handles open)
    print("=== Opening input PDFs ===")
    for path in pdf_files:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Input file not found: {abs_path}")
        f = open(abs_path, "rb")
        reader = PdfReader(f)
        filename = os.path.basename(abs_path)
        num_pages = len(reader.pages)
        rinfo = {
            "fileobj": f,
            "reader": reader,
            "filename": filename,
            "path": abs_path,
            "start_page": total_pages,
            "num_pages": num_pages
        }
        readers.append(rinfo)
        total_pages += num_pages
        print(f"  {filename}: {num_pages} pages (path: {abs_path})")

    print(f"Total pages expected: {total_pages}")

    # Copy pages into writer and build maps
    print("\n=== Copying pages into writer ===")
    src_page_id_map = {}       # id(source_page_obj) -> (reader_index, page_index)
    merged_page_to_source = {} # merged_index -> (reader_index, page_index)

    for r_idx, rinfo in enumerate(readers):
        reader = rinfo["reader"]
        for p_idx, page in enumerate(reader.pages):
            try:
                src_page_id_map[id(page)] = (r_idx, p_idx)
            except Exception:
                pass

            writer.add_page(page)
            m_idx = len(writer.pages) - 1
            merged_page_to_source[m_idx] = (r_idx, p_idx)

            if sleep_between_pages:
                time.sleep(sleep_between_pages)

        if sleep_between_files:
            time.sleep(sleep_between_files)

        print(f"  Added {rinfo['num_pages']} pages from {rinfo['filename']} (merged pages {rinfo['start_page']}..{rinfo['start_page'] + rinfo['num_pages'] - 1})")

    # Helper: find merged index for a source page object
    def _find_merged_page_for_source_pageobj(page_obj):
        try:
            s = src_page_id_map.get(id(page_obj))
            if s:
                r_idx, p_idx = s
                return readers[r_idx]["start_page"] + p_idx
        except Exception:
            pass
        # fallback brute-force
        try:
            for r_idx, rinfo in enumerate(readers):
                for p_idx, p in enumerate(rinfo["reader"].pages):
                    if p == page_obj:
                        return rinfo["start_page"] + p_idx
        except Exception:
            pass
        return None

    # Helper: convert dest object forms into ArrayObject referencing merged pages
    def _remap_dest(dest_obj, annot_src_reader_index):
        # IndirectObject page reference
        try:
            if isinstance(dest_obj, generic.IndirectObject):
                try:
                    page_obj = dest_obj.get_object()
                except Exception:
                    return None
                merged = _find_merged_page_for_source_pageobj(page_obj)
                if merged is None:
                    return None
                return generic.ArrayObject([writer.pages[merged].indirect_reference, generic.NameObject("/Fit")])
        except Exception:
            pass

        # Array-like dests: [pageObj /XYZ ...] or [num /Fit ...] or [name /Fit ...]
        try:
            if isinstance(dest_obj, (generic.ArrayObject, list, tuple)):
                arr = list(dest_obj)
                if not arr:
                    return None
                first = arr[0]
                # page object
                if isinstance(first, generic.IndirectObject):
                    try:
                        page_obj = first.get_object()
                    except Exception:
                        return None
                    merged = _find_merged_page_for_source_pageobj(page_obj)
                    if merged is None:
                        return None
                    return generic.ArrayObject([writer.pages[merged].indirect_reference] + arr[1:])
                # numeric index relative to that document
                if isinstance(first, (int, float, generic.NumberObject)):
                    try:
                        dest_index = int(first)
                        rinfo = readers[annot_src_reader_index]
                        merged = rinfo["start_page"] + dest_index
                        return generic.ArrayObject([writer.pages[merged].indirect_reference] + arr[1:]) if len(arr) > 1 else generic.ArrayObject([writer.pages[merged].indirect_reference, generic.NameObject("/Fit")])
                    except Exception:
                        return None
                # named dest inside array
                if isinstance(first, (generic.NameObject, generic.TextStringObject, str, bytes)):
                    nm = first
                    if isinstance(nm, bytes):
                        nm = _decode_pdf_string(nm)
                    # try resolve named dest in all readers
                    for rr_idx, rr in enumerate(readers):
                        try:
                            page_num = _resolve_named_dest_to_page(rr["reader"], nm)
                            if page_num is not None:
                                merged = rr["start_page"] + page_num
                                return generic.ArrayObject([writer.pages[merged].indirect_reference] + arr[1:])
                        except Exception:
                            continue
                    return None
        except Exception:
            pass

        # Plain numeric dest
        try:
            if isinstance(dest_obj, (int, float, generic.NumberObject)):
                dest_index = int(dest_obj)
                rinfo = readers[annot_src_reader_index]
                merged = rinfo["start_page"] + dest_index
                return generic.ArrayObject([writer.pages[merged].indirect_reference, generic.NameObject("/Fit")])
        except Exception:
            pass

        # Plain named dest
        try:
            if isinstance(dest_obj, (generic.NameObject, generic.TextStringObject, str, bytes)):
                nm = dest_obj
                if isinstance(nm, bytes):
                    nm = _decode_pdf_string(nm)
                for rr_idx, rr in enumerate(readers):
                    try:
                        page_num = _resolve_named_dest_to_page(rr["reader"], nm)
                        if page_num is not None:
                            merged = rr["start_page"] + page_num
                            return generic.ArrayObject([writer.pages[merged].indirect_reference, generic.NameObject("/Fit")])
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    # Now walk merged pages and process annotations
    print("\n=== Post-processing annotations & actions ===")
    links_updated = 0
    links_converted = 0
    links_normalized = 0
    links_remapped_internal = 0

    for m_idx in range(len(writer.pages)):
        page = writer.pages[m_idx]
        # try to find source reader for this merged page (best-effort)
        src_reader_idx = None
        for ridx, rinfo in enumerate(readers):
            if rinfo["start_page"] <= m_idx < rinfo["start_page"] + rinfo["num_pages"]:
                src_reader_idx = ridx
                break

        if "/Annots" not in page:
            continue

        annots = page["/Annots"]
        if isinstance(annots, generic.IndirectObject):
            try:
                annots = annots.get_object()
            except Exception:
                continue
        if not annots:
            continue

        try:
            annots_list = list(annots)
        except Exception:
            continue

        for a_ref in annots_list:
            try:
                annot = a_ref.get_object() if isinstance(a_ref, generic.IndirectObject) else a_ref
            except Exception:
                continue

            # only handle link annotations
            try:
                subtype = annot.get("/Subtype")
            except Exception:
                subtype = None
            if not (subtype == generic.NameObject("/Link") or str(subtype) == "/Link"):
                continue

            # Annot-level /Dest (some links use /Dest instead of /A)
            try:
                if "/Dest" in annot:
                    new_dest = _remap_dest(annot["/Dest"], src_reader_idx if src_reader_idx is not None else 0)
                    if new_dest is not None:
                        annot[generic.NameObject("/Dest")] = new_dest
                        links_remapped_internal += 1
                        print(f"Page {m_idx}: remapped annotation-level /Dest")
            except Exception:
                traceback.print_exc()

            # Action dictionary
            if "/A" not in annot:
                continue
            action = annot["/A"]
            if isinstance(action, generic.IndirectObject):
                try:
                    action = action.get_object()
                except Exception:
                    action = annot["/A"]

            s_val = action.get("/S")
            s_type = str(s_val) if s_val is not None else None

            # Internal GoTo remap
            if s_type == "/GoTo":
                try:
                    if "/D" in action:
                        newd = _remap_dest(action["/D"], src_reader_idx if src_reader_idx is not None else 0)
                        if newd is not None:
                            action[generic.NameObject("/D")] = newd
                            links_remapped_internal += 1
                            links_updated += 1
                            print(f"Page {m_idx}: remapped internal /GoTo")
                except Exception:
                    traceback.print_exc()

            # Remote GoToR handling
            if s_type == "/GoToR":
                try:
                    # Extract and decode filespec /F
                    target_raw = action.get("/F")
                    target_fname = _extract_filespec_filename(target_raw) if target_raw is not None else None

                    # If not decoded, try fallback to str()
                    if target_fname is None and target_raw is not None:
                        try:
                            target_fname = str(target_raw)
                        except Exception:
                            target_fname = None

                    # Normalize target filename for matching
                    target_basename = os.path.basename(target_fname) if target_fname else None
                    target_basename_lower = target_basename.lower() if target_basename else None

                    matched_ridx = None

                    # Match heuristics (ordered): exact basename, basename without ext, target contains filename, substring
                    if target_basename_lower:
                        for rr_idx, rr in enumerate(readers):
                            try:
                                # exact basename match
                                if rr["filename"].lower() == target_basename_lower:
                                    matched_ridx = rr_idx
                                    break
                            except Exception:
                                pass

                    # basename without extension
                    if matched_ridx is None and target_basename_lower:
                        tb0 = os.path.splitext(target_basename_lower)[0]
                        for rr_idx, rr in enumerate(readers):
                            try:
                                if os.path.splitext(rr["filename"])[0].lower() == tb0:
                                    matched_ridx = rr_idx
                                    break
                            except Exception:
                                pass

                    # target contains reader filename (some InDesign references use partial paths)
                    if matched_ridx is None and target_fname:
                        tnorm_lower = target_fname.lower()
                        for rr_idx, rr in enumerate(readers):
                            try:
                                if rr["filename"].lower() in tnorm_lower:
                                    matched_ridx = rr_idx
                                    break
                            except Exception:
                                pass

                    # last: substring of basename (very permissive)
                    if matched_ridx is None and target_basename_lower:
                        for rr_idx, rr in enumerate(readers):
                            try:
                                if rr["filename"].lower().replace(" ", "") in target_basename_lower.replace(" ", ""):
                                    matched_ridx = rr_idx
                                    break
                            except Exception:
                                pass

                    # If matched, compute destination page relative to that reader
                    converted = False
                    if matched_ridx is not None:
                        tgt_reader = readers[matched_ridx]
                        dest_page = 0
                        # compute dest_page from /D if present
                        if "/D" in action:
                            try:
                                D = action["/D"]
                                # array style
                                if isinstance(D, (list, generic.ArrayObject)) and len(D) > 0:
                                    first_item = D[0]
                                    # if page object (indirect) referencing target doc's page
                                    if isinstance(first_item, generic.IndirectObject):
                                        try:
                                            page_obj = first_item.get_object()
                                            for idx, p in enumerate(tgt_reader["reader"].pages):
                                                if p == page_obj:
                                                    dest_page = idx
                                                    break
                                        except Exception:
                                            dest_page = 0
                                    elif isinstance(first_item, (int, float, generic.NumberObject)):
                                        dest_page = int(first_item)
                                    elif isinstance(first_item, (generic.NameObject, generic.TextStringObject, str, bytes)):
                                        # named destination — try to resolve in target reader
                                        nm = first_item
                                        if isinstance(nm, bytes):
                                            nm = _decode_pdf_string(nm)
                                        try:
                                            pn = _resolve_named_dest_to_page(tgt_reader["reader"], nm)
                                            if pn is not None:
                                                dest_page = int(pn)
                                        except Exception:
                                            dest_page = 0
                                    else:
                                        dest_page = 0
                                # if D is number
                                elif isinstance(D, (int, float, generic.NumberObject)):
                                    dest_page = int(D)
                                # if D is namelike
                                elif isinstance(D, (generic.NameObject, generic.TextStringObject, str, bytes)):
                                    nm = D
                                    if isinstance(nm, bytes):
                                        nm = _decode_pdf_string(nm)
                                    try:
                                        pn = _resolve_named_dest_to_page(tgt_reader["reader"], nm)
                                        if pn is not None:
                                            dest_page = int(pn)
                                    except Exception:
                                        dest_page = 0
                            except Exception:
                                dest_page = 0

                        # compute merged page index
                        try:
                            new_page = tgt_reader["start_page"] + dest_page
                            # convert to internal GoTo
                            action[generic.NameObject('/S')] = generic.NameObject('/GoTo')
                            action[generic.NameObject('/D')] = generic.ArrayObject([
                                writer.pages[new_page].indirect_reference,
                                generic.NameObject('/Fit')
                            ])
                            # remove /F
                            if '/F' in action:
                                try:
                                    del action['/F']
                                except Exception:
                                    pass
                            links_updated += 1
                            links_converted += 1
                            converted = True
                            print(f"Page {m_idx}: converted GoToR -> GoTo (target {tgt_reader['filename']} page {dest_page} => merged page {new_page})")
                        except Exception:
                            converted = False

                    # If not converted (no match) — normalize /F to direct filespec so it is not an IndirectObject or dangling reference
                    if not converted:
                        if target_fname:
                            try:
                                fsdict = generic.DictionaryObject()
                                try:
                                    fsdict[generic.NameObject("/F")] = generic.TextStringObject(_decode_pdf_string(target_fname))
                                except Exception:
                                    fsdict["/F"] = _decode_pdf_string(target_fname)
                                try:
                                    fsdict[generic.NameObject("/UF")] = generic.TextStringObject(_decode_pdf_string(target_fname))
                                except Exception:
                                    pass
                                try:
                                    action[generic.NameObject("/F")] = fsdict
                                except Exception:
                                    action["/F"] = fsdict
                                links_normalized += 1
                                print(f"Page {m_idx}: normalized external GoToR /F -> {target_fname}")
                            except Exception:
                                # unexpected failure; leave as is but log
                                print(f"[WARN] could not normalize external filespec on merged page {m_idx}, target={target_fname}")
                                traceback.print_exc()
                        else:
                            # no filename decoded — nothing to do but log
                            print(f"[WARN] GoToR on page {m_idx} had no decodable /F filespec (raw: {repr(target_raw)})")
                except Exception:
                    traceback.print_exc()

            # URI handling: ensure it's string
            if s_type == "/URI" and "/URI" in action:
                try:
                    uri = action.get("/URI")
                    if isinstance(uri, generic.IndirectObject):
                        try:
                            uri = uri.get_object()
                        except Exception:
                            pass
                    if isinstance(uri, bytes):
                        uri = _decode_pdf_string(uri)
                    if uri is not None:
                        action[generic.NameObject("/URI")] = generic.TextStringObject(str(uri))
                except Exception:
                    traceback.print_exc()

    print(f"\nLinks converted: {links_converted}, normalized externals: {links_normalized}, internal remapped: {links_remapped_internal}")
    print(f"Total link actions updated: {links_updated}")

    # Save output PDF
    print("\n=== Saving merged PDF ===")
    with open(output_path, "wb") as out_f:
        writer.write(out_f)
    print(f"Saved to: {output_path}")

    # close source filehandles
    for r in readers:
        try:
            r["fileobj"].close()
        except Exception:
            pass

    return True


if __name__ == "__main__":
    # Edit this list to point at your PDFs
    pdf_files = [
        r"C:\Users\is6076\Downloads\merge\01_9780443184529_cop.pdf",
        r"C:\Users\is6076\Downloads\merge\02_9780443184529_con.pdf",
        r"C:\Users\is6076\Downloads\merge\03_9780443184529_lst.pdf",
        r"C:\Users\is6076\Downloads\merge\04_9780443184529_ack.pdf",
        r"C:\Users\is6076\Downloads\merge\05_9780443184529_Ch01.pdf",
        r"C:\Users\is6076\Downloads\merge\06_9780443184529_Ch02.pdf",
        r"C:\Users\is6076\Downloads\merge\07_9780443184529_Ch03.pdf",
        r"C:\Users\is6076\Downloads\merge\08_9780443184529_gls.pdf",
        r"C:\Users\is6076\Downloads\merge\09_9780443184529_ind.pdf",
    ]
    output_path = r"C:\Users\is6076\Downloads\merge\merged_with_links_improved.pdf"

    try:
        ok = merge_pdfs_preserve_links(pdf_files, output_path,
                                       sleep_between_files=0.0,
                                       sleep_between_pages=0.0)
        if ok:
            print("\n" + "="*60)
            print("SUCCESS: PDFs merged with hyperlinks preserved/converted.")
            print("="*60)
    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()

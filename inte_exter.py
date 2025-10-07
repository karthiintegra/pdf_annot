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
    return str(value)


def _extract_filespec_filename(fspec):
    """
    Robustly get a filename string from a filespec object which may be:
     - bytes/str
     - IndirectObject
     - dict with /UF or /F
    """
    try:
        if isinstance(fspec, generic.IndirectObject):
            fspec = fspec.get_object()
    except Exception:
        pass

    if isinstance(fspec, dict):
        for key in ("/UF", "/F", "/DOS", "/Mac", "/Unix"):
            if key in fspec:
                return _decode_pdf_string(fspec[key])
        # fallback: if '/F' present but not matched above
        if "/F" in fspec:
            return _decode_pdf_string(fspec["/F"])
        return _decode_pdf_string(str(fspec))

    if isinstance(fspec, (str, bytes)):
        return _decode_pdf_string(fspec)

    return _decode_pdf_string(fspec)


def _resolve_named_dest_to_page(reader, name):
    """
    Try multiple reader APIs to resolve a named destination to a page index.
    Returns int page index or None.
    """
    if name is None:
        return None
    if isinstance(name, bytes):
        name = _decode_pdf_string(name)

    # pypdf style
    try:
        nd = getattr(reader, "named_destinations", None)
        if nd and name in nd:
            dest = nd[name]
            try:
                return reader.get_destination_page_number(dest)
            except Exception:
                try:
                    p = getattr(dest, "page", None)
                    if p is not None:
                        for idx, pp in enumerate(reader.pages):
                            if pp == p:
                                return idx
                except Exception:
                    pass
    except Exception:
        pass

    # PyPDF2 older API
    try:
        get_named = getattr(reader, "getNamedDestinations", None)
        if callable(get_named):
            nd = get_named()
            if name in nd:
                dest = nd[name]
                try:
                    return reader.get_destination_page_number(dest)
                except Exception:
                    pass
    except Exception:
        pass

    return None


def merge_pdfs_preserve_links(pdf_files, output_path, sleep_between_files=0.0, sleep_between_pages=0.0):
    """
    Merge PDFs and preserve/repair internal and external hyperlinks.

    Parameters:
      - pdf_files: list of paths to PDFs (order matters)
      - output_path: path to save merged PDF
      - sleep_between_files: optional delay after processing each input file (seconds)
      - sleep_between_pages: optional delay after adding each page (seconds)

    Returns True on success.
    """
    writer = PdfWriter()
    readers = []   # list of dicts: {fileobj, reader, filename, path, start_page, num_pages}
    total_pages = 0

    # --- Open all input files and create readers, keep file objects open ---
    print("=== Opening input PDFs ===")
    for path in pdf_files:
        path_norm = os.path.abspath(path)
        f = open(path_norm, "rb")
        reader = PdfReader(f)
        filename = os.path.basename(path_norm)
        num_pages = len(reader.pages)
        rinfo = {
            "fileobj": f,
            "reader": reader,
            "filename": filename,
            "path": path_norm,
            "start_page": total_pages,
            "num_pages": num_pages
        }
        readers.append(rinfo)
        total_pages += num_pages
        print(f"  {filename}: {num_pages} pages (path: {path_norm})")

    print(f"Total pages expected: {total_pages}")

    # --- Copy pages into writer and build mappings ---
    print("\n=== Copying pages and building mappings ===")
    # maps to find source page quickly:
    src_page_id_map = {}          # id(source_page_obj) -> (reader_index, page_index)
    src_page_indirect_map = {}    # (reader_index, idnum, gen) -> merged_index
    merged_page_to_source = {}    # merged_index -> (reader_index,page_index)

    merged_index = 0
    for r_idx, rinfo in enumerate(readers):
        reader = rinfo["reader"]
        for p_idx, page in enumerate(reader.pages):
            # store id mapping for quick detection of page objects later
            try:
                src_page_id_map[id(page)] = (r_idx, p_idx)
            except Exception:
                pass

            # store indirect reference idnum/generation if available
            try:
                indir = getattr(page, "indirect_reference", None)
                if isinstance(indir, generic.IndirectObject):
                    key = (r_idx, getattr(indir, "idnum", None), getattr(indir, "generation", None))
                    # We'll map this to the merged page index after add_page.
            except Exception:
                indir = None

            # add to writer (we do manual add_page so we control mapping)
            writer.add_page(page)
            # new merged index
            merged_index = len(writer.pages) - 1
            merged_page_to_source[merged_index] = (r_idx, p_idx)

            # if indirect available, map to merged index
            try:
                if isinstance(indir, generic.IndirectObject):
                    key = (r_idx, getattr(indir, "idnum", None), getattr(indir, "generation", None))
                    src_page_indirect_map[key] = merged_index
            except Exception:
                pass

            if sleep_between_pages:
                time.sleep(sleep_between_pages)

        if sleep_between_files:
            time.sleep(sleep_between_files)

        print(f"  Added {rinfo['num_pages']} pages from {rinfo['filename']} (merged pages {rinfo['start_page']}..{rinfo['start_page'] + rinfo['num_pages'] - 1})")

    print("\n=== Post-processing annotations & actions ===")
    links_updated = 0

    def _find_merged_page_for_source_pageobj(page_obj):
        """Return merged index for a source page object (page_obj) or None."""
        try:
            s = src_page_id_map.get(id(page_obj))
            if s:
                r_idx, p_idx = s
                return readers[r_idx]["start_page"] + p_idx
        except Exception:
            pass
        # fallback: try brute-force scanning across readers.pages
        try:
            for r_idx, rinfo in enumerate(readers):
                for p_idx, p in enumerate(rinfo["reader"].pages):
                    if p == page_obj:
                        return rinfo["start_page"] + p_idx
        except Exception:
            pass
        return None

    def _remap_dest(dest_obj, annot_src_reader_index):
        """
        Convert dest_obj (various forms) into ArrayObject with new page ref
        or return None if not remappable.
        """
        # IndirectObject -> page object reference
        try:
            if isinstance(dest_obj, generic.IndirectObject):
                try:
                    page_obj = dest_obj.get_object()
                except Exception:
                    return None
                merged = _find_merged_page_for_source_pageobj(page_obj)
                if merged is None:
                    return None
                new_ref = writer.pages[merged].indirect_reference
                return generic.ArrayObject([new_ref, generic.NameObject("/Fit")])
        except Exception:
            pass

        # Array/Object like
        try:
            if isinstance(dest_obj, (generic.ArrayObject, list, tuple)):
                arr = list(dest_obj)
                if not arr:
                    return None
                first = arr[0]
                # first is indirect page object
                if isinstance(first, generic.IndirectObject):
                    try:
                        page_obj = first.get_object()
                    except Exception:
                        return None
                    merged = _find_merged_page_for_source_pageobj(page_obj)
                    if merged is None:
                        return None
                    new_ref = writer.pages[merged].indirect_reference
                    return generic.ArrayObject([new_ref] + arr[1:])
                # first is number => index relative to the annotation's source reader
                if isinstance(first, (int, float, generic.NumberObject)):
                    try:
                        dest_index = int(first)
                        rinfo = readers[annot_src_reader_index]
                        merged = rinfo["start_page"] + dest_index
                        new_ref = writer.pages[merged].indirect_reference
                        return generic.ArrayObject([new_ref] + arr[1:]) if len(arr) > 1 else generic.ArrayObject([new_ref, generic.NameObject("/Fit")])
                    except Exception:
                        return None
                # first could be name (named destination)
                if isinstance(first, (generic.NameObject, generic.TextStringObject, str, bytes)):
                    nm = first
                    if isinstance(nm, bytes):
                        nm = _decode_pdf_string(nm)
                    for rr_idx, rr in enumerate(readers):
                        try:
                            page_num = _resolve_named_dest_to_page(rr["reader"], nm)
                            if page_num is not None:
                                merged = rr["start_page"] + page_num
                                new_ref = writer.pages[merged].indirect_reference
                                return generic.ArrayObject([new_ref] + arr[1:])
                        except Exception:
                            continue
                    return None
        except Exception:
            pass

        # Number alone
        try:
            if isinstance(dest_obj, (int, float, generic.NumberObject)):
                dest_index = int(dest_obj)
                rinfo = readers[annot_src_reader_index]
                merged = rinfo["start_page"] + dest_index
                new_ref = writer.pages[merged].indirect_reference
                return generic.ArrayObject([new_ref, generic.NameObject("/Fit")])
        except Exception:
            pass

        # Named dest alone
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
                            new_ref = writer.pages[merged].indirect_reference
                            return generic.ArrayObject([new_ref, generic.NameObject("/Fit")])
                    except Exception:
                        continue
        except Exception:
            pass

        return None

    # Walk every merged page and fix its annotations
    for m_idx in range(len(writer.pages)):
        page = writer.pages[m_idx]
        # which source reader produced this merged page? best-effort:
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

        # ensure iterability
        try:
            annots_list = list(annots)
        except Exception:
            continue

        for a_ref in annots_list:
            try:
                annot = a_ref.get_object() if isinstance(a_ref, generic.IndirectObject) else a_ref
            except Exception:
                continue

            subtype = annot.get("/Subtype")
            if not (subtype == generic.NameObject("/Link") or str(subtype) == "/Link"):
                continue

            # Annot-level /Dest (some links use /Dest instead of /A)
            try:
                if "/Dest" in annot:
                    newd = _remap_dest(annot["/Dest"], src_reader_idx if src_reader_idx is not None else 0)
                    if newd is not None:
                        annot[generic.NameObject("/Dest")] = newd
                        links_updated += 1
                        print(f"Page {m_idx}: fixed annot /Dest")
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

            # normalize action type
            s_val = action.get("/S")
            s_type = str(s_val) if s_val is not None else None

            # Internal GoTo: remap D
            if s_type == "/GoTo":
                try:
                    if "/D" in action:
                        newd = _remap_dest(action["/D"], src_reader_idx if src_reader_idx is not None else 0)
                        if newd is not None:
                            action[generic.NameObject("/D")] = newd
                            links_updated += 1
                            print(f"Page {m_idx}: remapped internal /GoTo")
                except Exception:
                    traceback.print_exc()

            # Remote GoToR: either convert to internal (if target is merged) or normalize filespec for external
            if s_type == "/GoToR":
                try:
                    target_raw = action.get("/F")
                    target_fname = _extract_filespec_filename(target_raw) if target_raw is not None else None
                    if target_fname is None:
                        target_fname = str(target_raw) if target_raw is not None else None

                    # robust matching to see if target is among merged inputs
                    matched_ridx = None
                    if target_fname:
                        target_fname_norm = target_fname.replace("file://", "").strip()
                        # try absolute path match
                        for rr_idx, rr in enumerate(readers):
                            try:
                                if os.path.abspath(target_fname_norm) == rr["path"]:
                                    matched_ridx = rr_idx
                                    break
                            except Exception:
                                pass
                        # try relative to the source pdf directory
                        if matched_ridx is None and isinstance(target_fname_norm, str):
                            # action may originate in this page's source reader; use that reader path to resolve relative
                            srpath = readers[src_reader_idx]["path"] if src_reader_idx is not None else None
                            if srpath:
                                candidate = os.path.abspath(os.path.join(os.path.dirname(srpath), target_fname_norm))
                                for rr_idx, rr in enumerate(readers):
                                    if candidate == rr["path"]:
                                        matched_ridx = rr_idx
                                        break
                        # try basename match (case-insensitive)
                        if matched_ridx is None:
                            tb = os.path.basename(target_fname_norm).lower()
                            for rr_idx, rr in enumerate(readers):
                                if rr["filename"].lower() == tb:
                                    matched_ridx = rr_idx
                                    break
                        # try base name without extension
                        if matched_ridx is None:
                            tb0 = os.path.splitext(os.path.basename(target_fname_norm))[0].lower()
                            for rr_idx, rr in enumerate(readers):
                                if os.path.splitext(rr["filename"])[0].lower() == tb0:
                                    matched_ridx = rr_idx
                                    break

                    # If matched, convert to internal GoTo
                    if matched_ridx is not None:
                        tgt_reader = readers[matched_ridx]
                        # remap the /D relative to the matched reader
                        if "/D" in action:
                            D = action["/D"]
                            # If D is array where first is number or page object -> try remap
                            new_d = None
                            # If D is array-like
                            if isinstance(D, (list, generic.ArrayObject)):
                                first = D[0] if len(D) > 0 else None
                                # numeric index
                                if isinstance(first, (int, float, generic.NumberObject)):
                                    try:
                                        dest_page_index = int(first)
                                        merged_target = tgt_reader["start_page"] + dest_page_index
                                        new_ref = writer.pages[merged_target].indirect_reference
                                        new_d = generic.ArrayObject([new_ref] + list(D[1:]) if len(D) > 1 else [new_ref, generic.NameObject("/Fit")])
                                    except Exception:
                                        new_d = None
                                elif isinstance(first, generic.IndirectObject):
                                    try:
                                        page_obj = first.get_object()
                                        # find index in target reader
                                        for ip, p in enumerate(tgt_reader["reader"].pages):
                                            if p == page_obj:
                                                merged_target = tgt_reader["start_page"] + ip
                                                new_ref = writer.pages[merged_target].indirect_reference
                                                new_d = generic.ArrayObject([new_ref] + list(D[1:]) if len(D) > 1 else [new_ref, generic.NameObject("/Fit")])
                                                break
                                    except Exception:
                                        new_d = None
                                else:
                                    # Fall back to generic remap routine (tells it to use matched reader)
                                    new_d = _remap_dest(D, matched_ridx)
                            else:
                                # D might be a name or number
                                new_d = _remap_dest(D, matched_ridx)

                            if new_d is not None:
                                action[generic.NameObject("/S")] = generic.NameObject("/GoTo")
                                action[generic.NameObject("/D")] = new_d
                                # remove external file reference to avoid dangling indirects
                                if "/F" in action:
                                    try:
                                        del action["/F"]
                                    except Exception:
                                        pass
                                links_updated += 1
                                print(f"Page {m_idx}: converted GoToR -> GoTo (target merged: {tgt_reader['filename']})")
                                continue

                    # Not matched (true external): create a clean filespec dict in the output and keep external behavior
                    if target_fname:
                        fsdict = generic.DictionaryObject()
                        try:
                            fsdict[generic.NameObject("/F")] = generic.TextStringObject(_decode_pdf_string(target_fname))
                        except Exception:
                            fsdict["/F"] = _decode_pdf_string(target_fname)
                        # optional: add /UF if we detected unicode
                        try:
                            if isinstance(target_fname, str):
                                fsdict[generic.NameObject("/UF")] = generic.TextStringObject(target_fname)
                        except Exception:
                            pass
                        # assign the filespec dict (direct object inside output)
                        try:
                            action[generic.NameObject("/F")] = fsdict
                        except Exception:
                            action["/F"] = fsdict
                        print(f"Page {m_idx}: normalized external GoToR /F -> {target_fname}")
                except Exception:
                    traceback.print_exc()

            # URI handling: ensure it's string
            if s_type == "/URI" and "/URI" in action:
                try:
                    uri = action.get("/URI")
                    if isinstance(uri, generic.IndirectObject):
                        uri = uri.get_object()
                    if isinstance(uri, bytes):
                        uri = _decode_pdf_string(uri)
                    if uri is not None:
                        action[generic.NameObject("/URI")] = generic.TextStringObject(str(uri))
                except Exception:
                    traceback.print_exc()

    print(f"\nLinks updated: {links_updated}")

    # --- Write output, then close source file handles ---
    print("\n=== Writing merged PDF ===")
    with open(output_path, "wb") as out_f:
        writer.write(out_f)
    print(f"Saved: {output_path}")

    # Close filehandles we opened
    for rinfo in readers:
        try:
            rinfo["fileobj"].close()
        except Exception:
            pass

    return True


if __name__ == "__main__":
    # Example usage; tune sleep_between_files or sleep_between_pages if you really want intentional delays.
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
    output_path = r"C:\Users\is6076\Downloads\merge\merged_with_links_final.pdf"

    try:
        ok = merge_pdfs_preserve_links(pdf_files, output_path,
                                       sleep_between_files=0.0,  # try 0.01 if you insist on adding small delays
                                       sleep_between_pages=0.0)
        if ok:
            print("\nSUCCESS: merged and tried to preserve/repair links.")
    except Exception as e:
        print("Error:", e)
        traceback.print_exc()

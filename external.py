from PyPDF2 import PdfReader, PdfWriter, generic
import os

def merge_pdfs_preserve_links(pdf_files, output_path):
    """
    Merge PDFs created in InDesign with inter-document hyperlinks.
    Converts external references to internal page references.
    """
    writer = PdfWriter()
    page_mapping = {}  # Maps (filename, page_num) -> merged_page_num
    current_page = 0
    
    print("=== Opening PDFs ===")
    readers = []
    for pdf_path in pdf_files:
        reader = PdfReader(pdf_path)
        filename = os.path.basename(pdf_path)
        num_pages = len(reader.pages)
        
        print(f"{filename}: {num_pages} pages")
        
        # Map pages
        for i in range(num_pages):
            page_mapping[(filename, i)] = current_page + i
        
        readers.append({
            'reader': reader,
            'filename': filename,
            'path': pdf_path,
            'start_page': current_page
        })
        
        current_page += num_pages
    
    print(f"\nTotal pages: {current_page}")
    
    # Copy all pages
    print("\n=== Copying pages ===")
    for reader_info in readers:
        reader = reader_info['reader']
        for page in reader.pages:
            writer.add_page(page)
    
    # Update links
    print("\n=== Processing hyperlinks ===")
    links_updated = 0
    
    for page_num in range(len(writer.pages)):
        page = writer.pages[page_num]
        
        if '/Annots' in page:
            annots = page['/Annots']
            
            if isinstance(annots, generic.IndirectObject):
                annots = annots.get_object()
            
            for annot in annots:
                if isinstance(annot, generic.IndirectObject):
                    annot = annot.get_object()
                
                # Check if it's a link annotation
                if annot.get('/Subtype') == '/Link':
                    if '/A' in annot:
                        action = annot['/A']
                        
                        if isinstance(action, generic.IndirectObject):
                            action = action.get_object()
                        
                        # Check for GoToR (remote go-to) actions
                        if action.get('/S') == '/GoToR':
                            if '/F' in action:
                                # Get target file
                                target_file = action['/F']
                                if isinstance(target_file, dict) and '/F' in target_file:
                                    target_filename = target_file['/F']
                                else:
                                    target_filename = target_file
                                
                                if isinstance(target_filename, bytes):
                                    target_filename = target_filename.decode('utf-8', errors='ignore')
                                elif isinstance(target_filename, str):
                                    pass
                                else:
                                    target_filename = str(target_filename)
                                
                                target_filename = os.path.basename(target_filename)
                                
                                # Get destination page
                                dest_page = 0
                                if '/D' in action:
                                    dest = action['/D']
                                    if isinstance(dest, list) and len(dest) > 0:
                                        first_item = dest[0]

                                        if isinstance(first_item, generic.IndirectObject):
                                            # Resolve indirect object to find actual page index
                                            page_obj = first_item.get_object()
                                            for idx, p in enumerate(reader_info['reader'].pages):
                                                if p == page_obj:
                                                    dest_page = idx
                                                    break
                                        elif isinstance(first_item, (int, float)):
                                            dest_page = int(first_item)
                                        else:
                                            dest_page = 0
                                
                                # Find in mapping
                                for reader_info in readers:
                                    if target_filename in reader_info['filename']:
                                        new_page = reader_info['start_page'] + dest_page
                                        
                                        # Convert to internal link
                                        action[generic.NameObject('/S')] = generic.NameObject('/GoTo')
                                        action[generic.NameObject('/D')] = generic.ArrayObject([
                                            writer.pages[new_page].indirect_reference,
                                            generic.NameObject('/Fit')
                                        ])
                                        
                                        # Remove external file reference
                                        if '/F' in action:
                                            del action['/F']
                                        
                                        print(f"Page {page_num}: Link to {target_filename} -> Page {new_page}")
                                        links_updated += 1
                                        break
    
    print(f"\nLinks updated: {links_updated}")
    
    # Save
    print("\n=== Saving ===")
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)
    
    print(f"Saved to: {output_path}")
    return True


if __name__ == "__main__":
    # First install: pip install PyPDF2
    
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
    
    output_path = r"C:\Users\is6076\Downloads\merge\merged_with_links.pdf"
    
    try:
        success = merge_pdfs_preserve_links(pdf_files, output_path)
        if success:
            print("\n" + "="*60)
            print("SUCCESS: PDFs merged with hyperlinks preserved!")
            print("="*60)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

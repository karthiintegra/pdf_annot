from pdfixsdk import *
import os



def merge_pdfs_with_xobjects(input_pdf1, input_pdf2, output_pdf):
    """
    Alternative: Use XObjects to copy pages
    """
    pdfix = GetPdfix()
    if not pdfix:
        raise Exception("PDFix initialization failed")
    
    doc1 = None
    doc2 = None
    
    try:
        doc1 = pdfix.OpenDoc(input_pdf1, "")
        doc2 = pdfix.OpenDoc(input_pdf2, "")
        
        if not doc1 or not doc2:
            raise Exception("Cannot open documents")
        
        num_pages_doc1 = doc1.GetNumPages()
        num_pages_doc2 = doc2.GetNumPages()
        
        print(f"Document 1: {num_pages_doc1} pages")
        print(f"Document 2: {num_pages_doc2} pages")
        
        # Process doc2 pages one by one
        for i in range(num_pages_doc2):
            print(f"Processing page {i+1}/{num_pages_doc2}...")
            
            # Acquire page from doc2
            page2 = doc2.AcquirePage(i)
            if not page2:
                print(f"Failed to acquire page {i}")
                continue
            
            # Get page dimensions
            media_box = page2.GetMediaBox()
            
            # Create XObject from page
            xobject = doc1.CreateXObjectFromPage(page2)
            if not xobject:
                print(f"Failed to create XObject for page {i}")
                page2.Release()
                continue
            
            # Create new page in doc1
            new_page = doc1.CreatePage(num_pages_doc1 + i, media_box)
            if not new_page:
                print(f"Failed to create page {i}")
                page2.Release()
                continue
            
            # Get content and add the XObject
            content = new_page.GetContent()
            if content:
                matrix = PdfMatrix()
                form = content.AddNewForm(0, xobject, matrix)
                new_page.SetContent()
            
            page2.Release()
            new_page.Release()
        
        # Save
        if not doc1.Save(output_pdf, kSaveFull):
            raise Exception("Save failed")
        
        print(f"Saved to {output_pdf}")
        
        doc2.Close()
        doc1.Close()
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False
    finally:
        pdfix.Destroy()

if __name__ == "__main__":
    # Make sure PDFix is initialized first
    import sys
    
    # Initialize PDFix library (adjust path to your PDFix DLL/SO)
    try:
        Pdfix_init(fr"D:\PDF Accessibility\venv\Lib\site-packages\pdfixsdk\bin\x86_64\pdf.dll")  # Windows
        # Pdfix_init("path/to/libpdfix.so")  # Linux
        # Pdfix_init("path/to/libpdfix.dylib")  # Mac
    except Exception as e:
        print(f"Failed to initialize PDFix: {e}")
        sys.exit(1)
    
    merge_pdfs_with_xobjects(
        fr"C:\Users\is6076\Downloads\merge\05_9780443184529_Ch01.pdf",
        fr"C:\Users\is6076\Downloads\merge\09_9780443184529_ind.pdf",
       
       fr"C:\Users\is6076\Downloads\merge\s1.pdf",
    )
    
    Pdfix_destroy()

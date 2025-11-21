import pypdf


def remove_bookmarks(input_pdf, output_pdf, remove_items=None):
    """
    Remove bookmarks from a PDF without changing its structure.

    Args:
        input_pdf (str): Path to input PDF file
        output_pdf (str): Path to output PDF file
        remove_items (list): List of strings to match. Can be exact titles or partial matches.
                            Example: [".pdf", "Outline placeholder"]
                            Will remove any bookmark containing these strings.
    """
    try:
        # Read the PDF
        reader = pypdf.PdfReader(input_pdf)
        writer = pypdf.PdfWriter()

        # Copy all pages to writer (preserves structure)
        for page in reader.pages:
            writer.add_page(page)

        # Copy metadata
        if reader.metadata:
            writer.add_metadata(reader.metadata)

        # Handle bookmarks
        if remove_items is None:
            # Remove all bookmarks
            print("Removing all bookmarks...")
        else:
            # Copy bookmarks while preserving hierarchy
            if reader.outline:
                copy_bookmarks_recursive(reader.outline, writer, reader, remove_items)
                print(f"Removed bookmarks containing: {remove_items}")

        # Write to output file
        with open(output_pdf, 'wb') as f:
            writer.write(f)
        print(f"PDF saved to {output_pdf}")

    except Exception as e:
        print(f"Error: {e}")


def copy_bookmarks_recursive(outline, writer, reader, remove_items, parent=None):
    """
    Recursively copy bookmarks, skipping those in remove_items list.
    Preserves the hierarchical structure.

    Args:
        outline (list): List of bookmarks from reader
        writer: PdfWriter object
        reader: PdfReader object
        remove_items (list): List of strings - remove any bookmark containing these strings
        parent: Parent bookmark (for nested bookmarks)

    Returns:
        The last added bookmark at this level (needed for parent tracking)
    """
    last_outline_item = parent

    for bookmark in outline:
        # Check if this is a list (nested bookmarks)
        if isinstance(bookmark, list):
            # Recursively process nested bookmarks with current parent
            copy_bookmarks_recursive(bookmark, writer, reader, remove_items, last_outline_item)
        else:
            # Check if bookmark should be removed
            should_remove = False

            # Check if bookmark title contains any of the remove_items strings
            for item in remove_items:
                if item.lower() in bookmark.title.lower():
                    should_remove = True
                    break

            if not should_remove:
                try:
                    # Get the page from bookmark
                    if hasattr(bookmark, 'page'):
                        target_page = bookmark.page

                        # Find the page number in the reader
                        page_num = 0
                        try:
                            page_num = reader.pages.index(target_page)
                        except:
                            # Try to find by page reference
                            for idx, page in enumerate(reader.pages):
                                try:
                                    if page.get_object() == target_page.get_object():
                                        page_num = idx
                                        break
                                except:
                                    pass

                        # Add bookmark using add_outline_item
                        outline_item = writer.add_outline_item(
                            bookmark.title,
                            page_num,
                            parent=parent
                        )

                        # Update last_outline_item for next siblings
                        last_outline_item = outline_item

                except Exception as e:
                    print(f"Could not copy bookmark '{bookmark.title}': {e}")

    return last_outline_item


def list_bookmarks(pdf_path):
    """
    List all bookmarks in a PDF.

    Args:
        pdf_path (str): Path to PDF file
    """
    try:
        reader = pypdf.PdfReader(pdf_path)
        print(f"\nBookmarks in {pdf_path}:")
        print_outline(reader.outline)
    except Exception as e:
        print(f"Error: {e}")


def print_outline(outline, indent=0):
    """
    Recursively print bookmarks with indentation for nesting.
    """
    for bookmark in outline:
        if isinstance(bookmark, list):
            print_outline(bookmark, indent + 2)
        else:
            print("  " * indent + f"- {bookmark.title}")


# Example usage:
if __name__ == "__main__":
    # First, list existing bookmarks
    pdf_file = r"C:\Users\IS12765\Downloads\20-11-2025\booksmark\978-3-032-09127-7_Book_OnlinePDF_Incorrect.pdf"
    list_bookmarks(pdf_file)

    # Remove bookmarks containing ".pdf" or "Outline placeholder"
    remove_bookmarks(
        pdf_file,
        r"C:\Users\IS12765\Downloads\20-11-2025\booksmark\978-3-032-09127-7_Book_OnlinePDF_Incorrect______.pdf",
        remove_items=[".pdf", "Outline placeholder"]
    )

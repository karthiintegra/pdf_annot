from pdfixsdk import *
import json
import ctypes


def int_to_roman(num):
    """Convert integer to Roman numeral"""
    val = [10, 9, 5, 4, 1]
    syms = ['x', 'ix', 'v', 'iv', 'i']
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num


class PageNumberSetter:
    def __init__(self, pdfix):
        self.pdfix = pdfix

    def set_page_labels(self, input_pdf, output_pdf, roman_pages_count=None):
        """
        Set page labels:
        - Page 1: "First cover"
        - Pages 2 to (1+roman_pages_count): Roman numerals (i, ii, iii, ...)
        - Remaining pages: Arabic numerals continuing from (roman_pages_count + 1)

        Args:
            input_pdf: Input PDF file path
            output_pdf: Output PDF file path
            roman_pages_count: Number of pages with Roman numerals (default: auto-detect or use 15)
        """
        # Open the PDF document
        doc = self.pdfix.OpenDoc(input_pdf, "")
        if not doc:
            raise Exception(f"Unable to open PDF: {self.pdfix.GetErrorType()}")

        try:
            num_pages = doc.GetNumPages()

            # If roman_pages_count not specified, default to 15 or total pages - 1
            if roman_pages_count is None:
                roman_pages_count = min(15, num_pages - 1)

            # Calculate where Arabic numerals should start
            arabic_start_page_index = 1 + roman_pages_count  # After cover + roman pages
            arabic_start_number = roman_pages_count + 1  # Continue numbering

            # Get the root object (Catalog)
            root = doc.GetRootObject()
            if not root:
                raise Exception("Unable to get root object")

            # Create or get PageLabels dictionary
            page_labels_dict = root.GetDictionary("PageLabels")
            if not page_labels_dict:
                page_labels_dict = root.PutDict("PageLabels")

            # Create Nums array for page label ranges
            nums_array = page_labels_dict.GetArray("Nums")
            if not nums_array:
                nums_array = page_labels_dict.PutArray("Nums")

            # Clear existing entries
            while nums_array.GetNumObjects() > 0:
                nums_array.RemoveNth(0)

            # First range: Page 0 (index 0) - "First cover"
            nums_array.PutNumber(nums_array.GetNumObjects(), 0)
            cover_dict = nums_array.InsertDict(nums_array.GetNumObjects())
            cover_dict.PutName("Type", "PageLabel")
            cover_dict.PutString("P", "Cover")

            # Second range: Pages after cover - Roman numerals
            nums_array.PutNumber(nums_array.GetNumObjects(), 1)  # Start at page index 1
            roman_dict = nums_array.InsertDict(nums_array.GetNumObjects())
            roman_dict.PutName("Type", "PageLabel")
            roman_dict.PutName("S", "r")  # Lowercase roman numerals

            # Third range: Remaining pages - Arabic numerals (continuing from roman count + 1)
            if arabic_start_page_index < num_pages:
                nums_array.PutNumber(nums_array.GetNumObjects(), arabic_start_page_index)
                arabic_dict = nums_array.InsertDict(nums_array.GetNumObjects())
                arabic_dict.PutName("Type", "PageLabel")
                arabic_dict.PutName("S", "D")  # Decimal Arabic numerals
                arabic_dict.PutNumber("St", arabic_start_number)  # Start from roman_count + 1

            # Save the modified PDF
            if not doc.Save(output_pdf, kSaveFull):
                raise Exception(f"Unable to save PDF: {self.pdfix.GetErrorType()}")

            print(f"✅ Successfully set page numbers:")
            print(f"   - Page 1: 'First cover'")
            print(
                f"   - Pages 2-{roman_pages_count + 1}: Roman numerals (i, ii, iii, ..., {int_to_roman(roman_pages_count)})")
            print(
                f"   - Pages {roman_pages_count + 2}+: Arabic numerals ({arabic_start_number}, {arabic_start_number + 1}, {arabic_start_number + 2}, ...)")
            print(f"   - Total pages in document: {num_pages}")

        finally:
            doc.Close()

    def verify_page_labels(self, pdf_path):
        """Verify the page labels by reading them back"""
        doc = self.pdfix.OpenDoc(pdf_path, "")
        if not doc:
            raise Exception(f"Unable to open PDF: {self.pdfix.GetErrorType()}")

        try:
            num_pages = doc.GetNumPages()
            print(f"\n📄 Document has {num_pages} pages")
            print("\nPage labels configuration:")

            # Read the PageLabels structure
            root = doc.GetRootObject()
            page_labels_dict = root.GetDictionary("PageLabels")

            if page_labels_dict:
                nums_array = page_labels_dict.GetArray("Nums")
                if nums_array:
                    num_entries = nums_array.GetNumObjects()
                    print(f"Number of label ranges: {num_entries // 2}\n")

                    for i in range(0, num_entries, 2):
                        page_index = nums_array.GetInteger(i)
                        label_dict = nums_array.GetDictionary(i + 1)

                        if label_dict:
                            # Get style
                            style_obj = label_dict.Get("S")
                            style = ""
                            if style_obj:
                                style_name = style_obj.GetText() if hasattr(style_obj, 'GetText') else ""
                                style_map = {
                                    "r": "Lowercase Roman (i, ii, iii, ...)",
                                    "R": "Uppercase Roman (I, II, III, ...)",
                                    "D": "Decimal Arabic (1, 2, 3, ...)",
                                    "a": "Lowercase letters (a, b, c, ...)",
                                    "A": "Uppercase letters (A, B, C, ...)"
                                }
                                style = style_map.get(style_name, style_name)

                            # Get prefix
                            prefix_obj = label_dict.Get("P")
                            prefix = ""
                            if prefix_obj:
                                prefix = prefix_obj.GetText() if hasattr(prefix_obj, 'GetText') else ""

                            # Get start value
                            start_value = label_dict.GetInteger("St", 1)

                            print(f"Range {i // 2 + 1} - Starting at page {page_index + 1}:")
                            if prefix:
                                print(f"  - Prefix/Label: '{prefix}'")
                            if style:
                                print(f"  - Style: {style}")
                            if not prefix:  # Only show start value if it's a numbered range
                                print(f"  - Start value: {start_value}")
                            print()

        finally:
            doc.Close()


# Example usage
if __name__ == "__main__":
    pdfix = GetPdfix()

    if not pdfix:
        print("❌ Failed to initialize PDFix")
        exit(1)

    try:
        # Create instance and process PDF
        page_numberer = PageNumberSetter(pdfix)

        input_file = r"C:\Users\IS12765\Downloads\9780443338038chp3_Output.pdf"
        output_file = r"C:\Users\IS12765\Downloads\9780443338038chp3_Output__.pdf"

        # Set the page labels
        # You can specify the number of Roman numeral pages
        # For example, if you want 15 Roman pages (i-xv), next page will be 16
        page_numberer.set_page_labels(input_file, output_file, roman_pages_count=10)

        # Or let it auto-detect (defaults to 15 or total pages - 1)
        # page_numberer.set_page_labels(input_file, output_file)

        # Verify the results
        page_numberer.verify_page_labels(output_file)

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        pdfix.Destroy()

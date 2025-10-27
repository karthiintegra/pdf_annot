import json
import ctypes
from pdfixsdk import *

def jsonToRawData(json_dict):
    json_str = json.dumps(json_dict)
    json_data = bytearray(json_str.encode('utf-8'))
    json_data_size = len(json_str)
    json_data_raw = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
    return json_data_raw, json_data_size


def delete_tags_in_pdf(input_path, output_path):
    # Initialize Pdfix
    pdfix = GetPdfix()
    if pdfix is None:
        raise Exception('❌ Pdfix Initialization failed')

    # Open document
    doc = pdfix.OpenDoc(input_path, "")
    if doc is None:
        raise Exception('❌ Unable to open PDF: ' + pdfix.GetError())

    # JSON commands to delete Story and Lbl tags and promote Figure
    json_dict = {
        "commands": [
            {
                "name": "delete_tags",
                "params": [
                    {"name": "tag_names", "value": "Eq_num"},
                    {"name": "exclude_tag_names", "value": "false"},
                    {"name": "skip_tag_names", "value": ""},
                    {"name": "flags", "value": 255},
                    {"name": "tag_content", "value": "move"}  # move children up
                ]
            },

        ]
    }

    # Convert JSON to raw data for Pdfix
    json_data, json_size = jsonToRawData(json_dict)
    memStm = pdfix.CreateMemStream()
    memStm.Write(0, json_data, json_size)

    # Load and execute the command
    command = doc.GetCommand()
    if not command.LoadParamsFromStream(memStm, kDataFormatJson):
        memStm.Destroy()
        raise Exception("❌ Failed to load JSON command")

    memStm.Destroy()

    if not command.Run():
        raise Exception('❌ Unable to run delete_tags command: ' + str(pdfix.GetError()))

    # Save the modified PDF
    if not doc.Save(output_path, kSaveFull):
        raise Exception('❌ Failed to save PDF: ' + pdfix.GetError())

    doc.Close()
    print(f"✅ Story and Lbl tags deleted successfully. Figure is now root.\n📄 Output: {output_path}")
    return output_path


# Example usage
if __name__ == "__main__":
    input_pdf = r"C:\Users\IS12765\Downloads\11.pdf"
    output_pdf = r"C:\Users\IS12765\Downloads\12.pdf"
    delete_tags_in_pdf(input_pdf, output_pdf)

from pdfixsdk import *
import json, ctypes

input_pdf = r"c:\Users\is6076\Downloads\modify_____.pdf"
output_pdf = r"c:\Users\is6076\Downloads\cleaned_tags.pdf"

pdfix = GetPdfix()

def jsonToRawData(json_dict):
    json_str = json.dumps(json_dict)
    json_data = bytearray(json_str.encode('utf-8'))
    json_data_size = len(json_str)
    json_data_raw = (ctypes.c_ubyte * json_data_size).from_buffer(json_data)
    return json_data_raw, json_data_size


def story_has_only_note(elem):
    """Check if this element is a Story with only one child and that child is Note."""
    if elem.GetType(False) != "Story":
        return False

    if elem.GetNumChildren() == 1 and elem.GetChildType(0) == kPdsStructChildElement:
        child_obj = elem.GetChildObject(0)
        child_elem = elem.GetStructTree().GetStructElementFromObject(child_obj)
        if child_elem and child_elem.GetType(False) == "Note":
            return True
    return False


def collect_story_nodes(elem, targets):
    """Recursively collect Story elements that have only Note as a child."""
    if story_has_only_note(elem):
        targets.append(elem)

    for i in range(elem.GetNumChildren()):
        if elem.GetChildType(i) == kPdsStructChildElement:
            child_obj = elem.GetChildObject(i)
            child_elem = elem.GetStructTree().GetStructElementFromObject(child_obj)
            if child_elem:
                collect_story_nodes(child_elem, targets)


def delete_story_nodes(doc, story_nodes):
    """Run delete_tags command to remove only Story tags we found."""
    if not story_nodes:
        print("ℹ️ No <Story> tags with only <Note> found.")
        return

    # Build command — we still use delete_tags but only for Story
    json_dict = { 
        "commands": [
            {
                "name": "delete_tags",
                "params": [
                    { "name": "tag_names", "value": "Story" },
                    { "name": "exclude_tag_names", "value": "false" },
                    { "name": "flags", "value": 255 },
                    { "name": "tag_content", "value": "move" }
                ]
            }
        ]
    }

    json_data, json_size = jsonToRawData(json_dict)
    memStm = pdfix.CreateMemStream()
    memStm.Write(0, json_data, json_size)

    command = doc.GetCommand()
    command.LoadParamsFromStream(memStm, kDataFormatJson)
    memStm.Destroy()

    if not command.Run():
        raise Exception("❌ Failed to run delete_tags: " + pdfix.GetError())

    print(f"🗑 Deleted {len(story_nodes)} <Story> tags with only <Note>.")


def main():
    if pdfix is None:
        raise Exception("❌ PDFix initialization failed")

    doc = pdfix.OpenDoc(input_pdf, "")
    if doc is None:
        raise Exception("❌ Unable to open PDF: " + pdfix.GetError())

    struct_tree = doc.GetStructTree()
    if not struct_tree:
        raise Exception("❌ No structure tree found in PDF")

    # Step 1: find candidate Story tags
    targets = []
    for i in range(struct_tree.GetNumChildren()):
        obj = struct_tree.GetChildObject(i)
        elem = struct_tree.GetStructElementFromObject(obj)
        if elem:
            collect_story_nodes(elem, targets)

    # Step 2: only delete Story tags if they match the condition
    delete_story_nodes(doc, targets)

    # Step 3: save
    if not doc.Save(output_pdf, kSaveFull):
        raise Exception("❌ Failed to save document: " + pdfix.GetError())

    doc.Close()
    print(f"✅ Cleaned <Story> tags with <Note> children.\n📄 Output: {output_pdf}")


if __name__ == "__main__":
    main()

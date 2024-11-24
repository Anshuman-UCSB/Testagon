import os

def get_file_structure(path: str):
    files = []
    for f in os.listdir(path):
        new_path = os.path.join(path, f)
        if os.path.isfile(new_path):
            files.append({
                'type': 'file', 
                'name': f
            })
        else:
            files.append({
                'type': 'dir', 
                'name': f, 
                'items': get_file_structure(new_path)
            })
    return files

def output_project_structure(files: list, spaces=0):
    out = ""
    for f in files:
        out += " "*spaces + "- " + f["name"] + "\n"
        if f["type"] == "dir":
            out += output_project_structure(f["items"], spaces + 2)
    return out
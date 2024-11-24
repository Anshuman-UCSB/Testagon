import os

def get_project_structure(path: str="."):
    files = []
    dir = os.path.realpath(os.path.join(os.getcwd(), path))
    for f in os.listdir(dir):
        new_path = os.path.join(path, f)
        if f.startswith("."): continue
        if os.path.isfile(new_path):
            files.append(new_path)
        elif os.path.isdir(new_path):
            files += get_project_structure(new_path)
    return files
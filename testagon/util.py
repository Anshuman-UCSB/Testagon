import os
import typing
import libcst as cst

def get_project_structure(path: str="."):
    """Lists all files (using their path relative to the project root) recursively in the project directory"""
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

class DocstringEditor(cst.CSTTransformer):
    """Transformer class to visit a target function and apply an update function to its docstring"""
    def __init__(self, function_name: str, updater: typing.Callable[[str], str]):
        self.function_name = function_name
        self.updater = updater

    def leave_FunctionDef(self, original_node, updated_node):
        if original_node.name.value == self.function_name:
            if original_node.get_docstring():
                # Update the docstring
                new_docstring = self.updater(original_node.get_docstring())
                docstring_node = cst.SimpleStatementLine(
                    [cst.Expr(cst.SimpleString(f'"""{new_docstring}"""'))]
                )
                # Replace the first statement (the existing docstring)
                body = [docstring_node] + list(updated_node.body.body[1:])
            else:
                # Add the new docstring as the first statement
                new_docstring = self.updater("")
                docstring_node = cst.SimpleStatementLine(
                    [cst.Expr(cst.SimpleString(f'"""{new_docstring}"""'))]
                )
                body = [docstring_node] + list(updated_node.body.body)
            return updated_node.with_changes(body=cst.IndentedBlock(body))
        return updated_node

# TODO: May want to have this take in an AST/CST directly so we can disambiguate conflicting function names ahead of time
def update_docstring(source: str, function_name: str, updater: typing.Callable[[str], str]):
    """Updates `function_name`'s docstring in the `source` Python code using the `updater` function"""
    tree = cst.parse_module(source)
    transformer = DocstringEditor(function_name, updater)
    new_tree = tree.visit(transformer)
    return new_tree.code()
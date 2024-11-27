import os
import typing
import ast
import traceback
import json
import libcst as cst
from openai import OpenAI
from textwrap import dedent
from testagon.logger import logger

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


def is_valid_syntax(source: str):
    """
    Checks if the syntax of a Python program from `source` is valid
    """
    try:
        ast.parse(source)
        return True, None
    except SyntaxError:
        return False, traceback.format_exc()
  

def validate_syntax(client: OpenAI, source: str, max_iter=10):
    """
    Verify `source` has correct syntax; iterates with the LLM until the syntax is valid or `max_iter` is reached

    We don't expect the LLM to output invalid code, but we should try to rectify it just in case
    """
    (valid, err) = is_valid_syntax(source)
    if valid: return source

    updated_source = source
    last_err = err
    fixed = False

    for i in range(0, max_iter):
        completion = client.chat.completions.create(
        model=os.getenv("MODEL"),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "validate_syntax",
                "schema": {
                    "type": "object",
                    "properties": {
                        # Explanation of the syntax error
                        "explanation": {"type": "string"},
                        # Explanation of the fix to implement
                        "fix": {"type": "string"},
                        # The source file with the fix implemented
                        "updated_file": {"type": "string"}
                    },
                    "required": ["explanation", "fix", "updated_file"],
                    "additionalProperties": False
                },
                "strict": True
            }
        },
        messages=[
            {
            "role": "system",
            "content": dedent("""
                The user will provide a Python file that is syntactically incorrect. They will also
                provide a traceback of the syntax error, informing you where it is. `explanation` is
                where you should describe the syntax error, `fix` is where you should describe how
                to fix it, and `updated_file` is the entire file content with the syntax error fixed. 
                Do not change the behavior of the program except to fix the syntax error. You should
                output your response as a JSON object.
            """)
            },
            {
            "role": "user",
            "content": dedent(f"""
                # File #
                ```python
                {updated_source}
                ```

                # Error information #
                `{last_err}`
            """)
            }
        ]
        )

        response = json.loads(completion.choices[0].message.content)
        updated_source = response["updated_file"]
        (valid, err) = validate_syntax(updated_source)
        last_err = err

        if valid:
            fixed = True
            logger.debug("Syntax correction completed after %i iterations", i + 1)
            break

    if not fixed:
        logger.error("Syntax correction not successful")

    return updated_source


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
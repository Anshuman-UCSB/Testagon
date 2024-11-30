import os
import typing
import ast
import traceback
import json
import libcst as cst
import platformdirs
from configparser import ConfigParser
from openai import OpenAI
from textwrap import dedent
from testagon.logger import logger


def get_project_structure(path: str = "."):
    """Lists all files (using their path relative to the project root) recursively in the project directory"""
    files = []
    dir = os.path.realpath(os.path.join(os.getcwd(), path))
    for f in os.listdir(dir):
        new_path = os.path.join(path, f)
        if f.startswith("."):
            continue
        if os.path.isfile(new_path):
            files.append(new_path)
        elif os.path.isdir(new_path):
            files += get_project_structure(new_path)
    return files


def get_source_programs():
    """Filters all files in the project directory and returns only those that are non-test Python files"""
    files = get_project_structure()
    python_files = []
    for path in files:
        if path.startswith("./tests/"):
            continue
        if not path.endswith(".py"):
            continue
        if "test_" in path:
            continue
        python_files.append(path)
    return python_files


def read_config():
    """Reads the Testagon config file into a parser"""
    dir = platformdirs.user_config_dir(appname="Testagon")
    os.makedirs(dir, exist_ok=True)
    config = ConfigParser()
    config.read(os.path.join(dir, "config.ini"))
    if "DEFAULT" not in config:
        config["DEFAULT"] = {}
        config["DEFAULT"]["model"] = "oai-gpt-4o-structured"
    return config


def get_model():
    config = read_config()
    return config["DEFAULT"].get("model", "oai-gpt-4o-structured")


def write_config(config: ConfigParser):
    """Write a config parser to the Testagon config file"""
    dir = platformdirs.user_config_dir(appname="Testagon")
    os.makedirs(dir, exist_ok=True)
    with open(os.path.join(dir, "config.ini"), "w") as f:
        config.write(f)


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
    if valid:
        return source

    updated_source = source
    last_err = err
    fixed = False

    for i in range(0, max_iter):
        completion = client.chat.completions.create(
            model=get_model(),
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
                            "updated_file": {"type": "string"},
                        },
                        "required": ["explanation", "fix", "updated_file"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": dedent(
                        """
                The user will provide a Python file that is syntactically incorrect. They will also
                provide a traceback of the syntax error, informing you where it is. `explanation` is
                where you should describe the syntax error, `fix` is where you should describe how
                to fix it, and `updated_file` is the entire file content with the syntax error fixed. 
                Do not change the behavior of the program except to fix the syntax error. You should
                output your response as a JSON object.
            """
                    ),
                },
                {
                    "role": "user",
                    "content": dedent(
                        f"""
                # File #
                ```python
                {updated_source}
                ```

                # Error information #
                `{last_err}`
            """
                    ),
                },
            ],
        )

        response = json.loads(completion.choices[0].message.content)
        updated_source = response["updated_file"]
        (valid, err) = is_valid_syntax(updated_source)
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
        # Temp CST FunctionDef node for function_name
        temp = cst.parse_module(self.function_name + "\n    pass").body[0]

        # Comparator for two CST FunctionDef nodes
        def is_same_func(original_node, temp):
            if original_node.name.value != temp.name.value:
                return False
            if len(original_node.params.params) != len(temp.params.params):
                return False
            for i in range(len(original_node.params.params)):
                arg1 = original_node.params.params[i].name.value
                arg2 = temp.params.params[i].name.value
                if arg1 != arg2:
                    return False
            return True

        if is_same_func(original_node, temp):
            if original_node.get_docstring():
                # Update the docstring
                new_docstring = self.updater(original_node.get_docstring())
                docstring_node = cst.SimpleStatementLine(
                    [cst.Expr(cst.SimpleString(f'"""\n{new_docstring}\n"""'))]
                )
                # Replace the first statement (the existing docstring)
                body = [docstring_node] + list(updated_node.body.body[1:])
            else:
                # Add the new docstring as the first statement
                new_docstring = self.updater("")
                docstring_node = cst.SimpleStatementLine(
                    [cst.Expr(cst.SimpleString(f'"""\n{new_docstring}\n"""'))]
                )
                body = [docstring_node] + list(updated_node.body.body)
            return updated_node.with_changes(body=cst.IndentedBlock(body))
        return updated_node


# TODO: May want to have this take in an AST/CST directly so we can disambiguate conflicting function names ahead of time
def update_docstring(
    source: str, function_name: str, updater: typing.Callable[[str], str]
):
    """Updates `function_name`'s docstring in the `source` Python code using the `updater` function"""
    tree = cst.parse_module(source)
    transformer = DocstringEditor(function_name, updater)
    new_tree = tree.visit(transformer)
    return new_tree.code


def get_all_dirs(dirname):
    subfolders = [f.path for f in os.scandir(dirname) if f.is_dir()]
    for dirname in list(subfolders):
        subfolders.extend(get_all_dirs(dirname))
    return subfolders

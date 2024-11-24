import os
import json
import util
import ast
import traceback
from openai import OpenAI
from textwrap import dedent

def validate_syntax(source: str):
  """
  Validates the syntax of a Python program from `source`
  """
  try:
    ast.parse(source)
    return True, None
  except SyntaxError:
    return False, traceback.format_exc()
  

def iterate_syntax(client: OpenAI, source: str, first_err: str, max_iter=10):
  """
  Verify `source` has correct syntax; iterates with the LLM until the syntax is valid or `max_iter` is reached
  """
  updated_source = source
  last_err = first_err

  for _ in range(0, max_iter):
    completion = client.chat.completions.create(
      model='oai-gpt-4o-mini' if os.getenv("USE_MINI_MODEL", False) else 'oai-gpt-4o-structured',
      response_format={
        "type": "json_schema",
        "json_schema": {
          "name": "validate_syntax",
          "schema": {
            "type": "object",
            "properties": {
              "explanation": {"type": "string"},
              "fix": {"type": "string"},
              "updated_file": {"type": "string"}
            },
            "required": ["explanation", "fix", "updated_file"],
            "additionalProperties": False
          }
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
            Do not change the behavior of the program except to fix the syntax error.
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
    if valid: break
    last_err = err

  return updated_source



def generate_initial(client: OpenAI, file_path: str, test_path: str):
  """
  Given a `file_path` inside the target project with the invariants listed in the docstring,
  generate a test file at `test_path` which will provide a comprehensive set of unit tests for
  each function, attempting to take into account any sources of logical vulnerabilities.
  """
  file_structure = "\n".join(util.get_project_structure())

  with open(file_path, "r") as f:
    content = f.read()
    completion = client.chat.completions.create(
      model='oai-gpt-4o-mini' if os.getenv("USE_MINI_MODEL", False) else 'oai-gpt-4o-structured',
      response_format={
        "type": "json_schema",
        "json_schema": {
          "name": "initial_generation",
          "schema": {
            "type": "object",
            "properties": {
              # Reasoning for each function in the source file
              "functions": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    # Declaration line as written in source file
                    "declaration": {"type": "string"},
                    # List of library/other files in project dependencies
                    "dependencies": {
                      "type": "array",
                      "items": {"type": "string"}
                    },
                    # Logical reasoning through function/listed invariants
                    "reasoning": {"type": "string"},
                    # Cases to test in final result; not expected to be Python code
                    "cases": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          # Explicitly state goal of the test case to reinforce proper generation
                          "justification": {"type": "string"},
                          # Input value
                          "input": {"type": "string"},
                          # Natural language for conditions to check on output
                          "output_properties": {
                            "type": "array",
                            "items": {"type": "string"}
                          },
                        },
                        "required": ["justification", "input", "output_properties"],
                        "additionalProperties": False
                      }
                    },
                  },
                  "required": ["declaration", "dependencies", "reasoning", "cases"],
                  "additionalProperties": False
                }
              },
              # Final output
              "pytest_file_content": {"type": "string"},
            },
            "required": ["functions", "pytest_file_content"],
            "additionalProperties": False
          },
          "strict": True
        }
      },
      messages=[
        {
          "role": "system",
          "content": dedent("""
            The user will provide the directory structure of their project, the canonical path to a Python file, 
            the content of the file, and the canonical path of the pytest test script location. Your job is to 
            generate a comprehensive set of pytest unit tests for each function, taking into account edge cases 
            and areas where the programmer's logic may have been faulty. In particular, pay close attention to 
            cases where an output could lead to a logic-based security vulnerability.

            Every function will be labeled with a list of invariants held by variables in the function.
            These invariants will describe arithmetic and logical relationships between inputs, control, loops,
            and outputs. The programmer was responsible for listing these invariants, so they may
            not be comprehensive or correctly capture the actual semantics of the program.

            Your output for every function should proceed as follows:

            ---
            `declaration`: Function declaration, exactly as written in the source file

            `dependencies`: Examine the code of the function, looking at external dependencies and calls to other files in the
            project. List these external services that the function relies on to execute. These will likely need to be mocked in unit tests.

            `reasoning`: Reason about what the function is doing logically. How are the invariants provided supposed to help
            accomplish the goal of this function? Think of this as a scratchpad for working through the functions.
            If helpful, go through the function and invariants line by line. 
            
            What would constitute a "valid" set of inputs for the function? What are some "invalid" inputs, and what should
            happen when these inputs are used? Are the invariants still satisfied when these invalid inputs are passed?
            What are some ways you can bypass the invariants to give unexpected output? Jot down some ideas for
            possible inputs and outputs to answer these questions.

            `cases`: Given the reasoning above, give a list of several concrete inputs and expected output properties. For each test
            case, justify the input/output by considering what behavior you are trying to enforce or ensure is non-exploitable.
            Make sure to provide cases that could expose logical security vulnerabilities if handled incorrectly.

            Attempt to provide enough tests such that every line in the function code receives coverage. Make sure branches and other
            variable constraints are tested thoroughly.
            ---

            Once you have processed every function in this way, provide a complete Python file using Pytest that will
            format the test cases for each function as a proper test case, running with the inputs and comparing them
            to the expected outputs. Make sure any services used in the functions are properly mocked. 
            This output goes in `pytest_file_content`. Output the entire answer as a JSON object.
          """)
        },
        {
          "role": "user",
          "content": dedent(f"""
            # Project structure #
            ```
            {file_structure}
            ```         
            
            # File path #
            `{file_path}`

            # Pytest script location #
            `{test_path}`

            # File content # 
            ```python
            {content}
            ```
          """)
        }
      ]
    )

    # Ensure correct syntax of the test file
    response = json.loads(completion.choices[0].message.content)
    pytest_content = response["pytest_file_content"]
    (valid, err) = validate_syntax(pytest_content)
    if not valid:
      pytest_content = iterate_syntax(client, pytest_content, err)

    # Dump result for target file to test script
    with open(test_path, "w") as test_file:
      test_file.write(pytest_content)
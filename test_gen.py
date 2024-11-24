import sys
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from textwrap import dedent

load_dotenv()

client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))

def generate_initial_tests(path):
  file_path = os.path.realpath(path)
  dir = os.path.dirname(path)

  filename = os.path.basename(path)
  test_file_path = f"{dir}/test_{filename}"

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
              "functions": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "declaration": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "cases": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "input": {"type": "string"},
                          "output_properties": {
                            "type": "array",
                            "items": {"type": "string"}
                          },
                          "justification": {"type": "string"},
                          "dependencies": {
                            "type": "array",
                            "items": {"type": "string"}
                          }
                        },
                        "required": ["input", "output_properties", "justification", "dependencies"],
                        "additionalProperties": False
                      }
                    },
                  },
                  "required": ["declaration", "reasoning", "cases"],
                  "additionalProperties": False
                }
              },
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
            The user will provide the canonical path to a Python file, the content of the file, and the canonical
            path of the pytest test script location. Your job is to generate a comprehensive set
            of pytest unit tests for each function, taking into account edge cases and areas where the programmer's
            logic may have been faulty. In particular, pay close attention to cases where an output could lead to
            a logic-based security vulnerability.

            Every function will be labeled with a list of invariants held by variables in the function.
            These invariants will describe arithmetic and logical relationships between inputs, control, loops,
            and outputs. The programmer was responsible for listing these invariants, so they may
            not be comprehensive or correctly capture the actual semantics of the program.

            Your output for every function should proceed as follows:

            ---
            `declaration`: Function declaration, exactly as written in the source file

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

            `dependencies`: Examine the code of the function, looking at external dependencies and library calls. List these 
            external services that the function relies on to execute. These will likely need to be mocked in unit tests.
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
            # File path #
            `{file_path}`

            # Pytest script location #
            `{test_file_path}`

            # File content # 
            ```python
            {content}
            ```
          """)
        }
      ]
    )

    response = json.loads(completion.choices[0].message.content)
    with open(test_file_path, "w") as test_file:
      test_file.write(response["pytest_file_content"])
  
if __name__ == "__main__":
  generate_initial_tests(sys.argv[1])
import os
import json
from openai import OpenAI
from textwrap import dedent
from util import update_docstring

def generate_invariants(client: OpenAI, file_path: str):
    """
    Generates invariants for each function in the Python file located at `file_path`
    and inserts them into the docstring of each function using the DocstringEditor.
    """
    # Read the content of the target file
    with open(file_path, "r") as file:
        content = file.read()

    # Call the LLM to analyze the file and generate invariants
    completion = client.chat.completions.create(
        model=os.getenv("MODEL"),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "generate_invariants",
                "schema": {
                    "type": "object",
                    "properties": {
                        "functions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    # Declaration line as written in source file
                                    "declaration": {
                                        "type": "string",
                                        "description": "The name of the function for which invariants are being generated."
                                    },
                                    "invariants": {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "description": "Each invariant describes a condition that must hold true during the execution of the function."
                                        }
                                    }
                                },
                                "required": ["declaration", "invariants"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["functions"],
                    "additionalProperties": False
                }
            }
        },
        messages=[
            {
                "role": "system",
                "content": dedent("""
                    You will be provided with a Python source code file.
                    Your task is to analyze each function in the file and generate a list of logical invariants for each function.
                    The invariants should describe conditions that should always hold true during the execution of the function.
                    Invariants should describe the properties of the function's inputs, outputs, and internal logic. 
                    
                    Format the output for each function as follows:
                    
                    -- INVARIANTS --
                    1. Argument `inp` is a string
                    2. etc...
                    
                    Only generate relevant and meaningful invariants that pertain to function arguments, control flow, data types, 
                    and logical relationships between inputs and outputs. The invariants should be as concise and specific as possible.
                """)
            },
            {
                "role": "user",
                "content": dedent(f"""
                    # File Content #
                    ```python
                    {content}
                    ```
                """)
            }
        ]
    )

    # Parse the response from the LLM
    response = json.loads(completion.choices[0].message.content)

    # Insert the generated invariants into the docstrings of the target file
    for function_info in response.get('functions', []):
        function_name = function_info['declaration']
        invariants = function_info['invariants']

        # Create a formatted invariants string
        invariants_string = "\n".join([f"{i + 1}. {inv}" for i, inv in enumerate(invariants)])
        formatted_invariants = f"-- INVARIANTS --\n{invariants_string}"

        # Function to update the docstring with the new invariants
        def updater(existing_docstring: str):
            if "-- INVARIANTS --" in existing_docstring:
                # Replace existing invariants
                return existing_docstring.split("-- INVARIANTS --")[0].strip() + "\n\n" + formatted_invariants
            else:
                # Add invariants to the end of the existing docstring
                return existing_docstring.strip() + "\n\n" + formatted_invariants

        # Update the docstring in the source content
        content = update_docstring(content, function_name, updater)

    # Write the updated content back to the target file
    with open(file_path, "w") as file:
        file.write(content)

    print("Invariants successfully inserted into docstrings.")

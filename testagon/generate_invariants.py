import os
import json
from openai import OpenAI
from textwrap import dedent
from testagon.logger import logger
from testagon.util import update_docstring, get_model

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
            model=get_model(),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "generate_invariants",
                    "schema": {
                        "type": "object",
                        "properties": {
                            # Reasoning for each function in source file for generating invariants
                            "functions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        # Declaration line as written in source file
                                        "declaration": { "type": "string" },
                                        # Logical reasoning for different invariants generated
                                        "reasoning": {"type": "string"},
                                        # List of invariant objects
                                        "invariants": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    # Invariant condition which must hold true
                                                    "condition": {"type": "string"},
                                                    # Explicitly state goal of the each invariant to reinforce proper generation
                                                    "justification": {"type": "string"}
                                                },
                                                "required": ["condition", "justification"],
                                                "additionalProperties": False
                                            },
                                        },
                                        "formatted_output": {"type": "string"},
                                    },
                                    "required": ["declaration", "reasoning", "invariants", "formatted_output"],
                                    "additionalProperties": False
                                },
                            },
                        },
                        "required": ["functions"],
                        "additionalProperties": False
                    },
                    "strict": True
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": dedent("""
                        You will be provided with a Python source code file.
                        Your task is to analyze each function in the file and generate a list of logical invariants for each function.
                        The invariants should describe conditions that should always hold true before, after, and during the program.
                        These invariants should accurately test the correctness of each function that is provided in the file. Pay close
                        attention to what the purpose of each function is, and give a list of assertions which ensure the correctness
                        of the function.

                        Your output for every function should proceed as follows:

                        ___
                        'declaration': Function declaration, exactly as written in the source file

                        'reasoning': Reason about what the function is doing logically. Think about what type of assertions can be made
                        for the function so that the intended functionality is fully tested, and the correctness of the function is ensured.
                        Think about what the correct behavior of the program is and reason about what type of asssertions can help catch
                        common programming errors.

                        'invariants': Given the reasoning above, give a list of invariants in the form of assertions. For every condition, provide
                        a justification for why this invariant is valid for testing the correctness of the function.
                        ___
                        
                        Here is a list which provides some examples of invariants that can be considered:

                        ___
                        'name': orig
                        'description': variable modified after function exits
                        'example': list[] != orig(list[])

                        'name': null
                        'description': whether variable is null/zero/empty
                        'example': n != null

                        'name': one_val
                        'description': whether variable always has only one value
                        'example': a has one value

                        'name': comp
                        'description': compare variables with (in)equalities
                        'example': i < 10

                        'name': val_set
                        'description': variable has value-set
                        'example': i one of {0, 1, 2}

                        'name': arith
                        'description': comp involving arithmetic operators
                        'example':i + j == 10

                        'name': pow
                        'description': variable is the power of another
                        'example': res is a power of 2

                        'name': div
                        'description': variable divides another
                        'example': people % i == 0

                        'name': sqr
                        'description': variable is the square of another
                        'example': max(b[]) == sum(b[])**2

                        'name': elt_comp
                        'description': comp on each element
                        'example': l[] elements < 7

                        'name': elt_val_set
                        'description': val_set for each element
                        'example': visit[] elements one of {0,1}

                        'name': pairwise
                        'description': comp neighboring elements pair
                        'example': arr[] sorted by <=

                        'name': member
                        'description': variable is a member of array
                        'example': p in people [j...i-1]

                        'name': sub
                        'description': one variable/array is subset of another
                        'example': a[] is a subset of b[j..]

                        'name': seqseq
                        'description': comp each element between arrays
                        'example': s[i..] >= t[0..count-1]

                        'name': reverse
                        'description': array is the reverse of another
                        'example': a[] is the reverse of c[i..]

                        'name': agg_check
                        'description': comparison on the aggregated values
                        'example': sum(l[] < 10)

                        'name': cond
                        'description': properties that rely on other properties
                        'example': (r == false) ==> (B.x >= 0)
                        ___

                        Once you have processed every function in this way, format the output for each function as follows:
                        
                        -- INVARIANTS --
                        1. Argument `inp` is a string
                        2. etc..
                        
                        Only generate relevant and meaningful invariants that pertain to function arguments, control flow, data types, 
                        and logical relationships between inputs and outputs. The invariants should be as concise and specific as possible.
                        For each function, put the formatted output in the `final_output` property of each corresponding `functions` object.
                        Output the entire answer as a JSON object.
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

        # Parse LLM response
        raw_res = completion.choices[0].message.content
        logger.debug("[LLM response]\n%s", raw_res)
        response = json.loads(raw_res)

        # Insert the generated invariants into the docstrings of the target file
        for func in response['functions']:
            name = func['declaration']
            invariants = func['invariants']
            formatted_invariants = func['formatted_output']

            def updater(existing_docstring: str):
                return formatted_invariants

            # Update the docstring in the source content
            content = update_docstring(content, name, updater)

        # Write the updated content back to the target file
        with open(file_path, "w") as file:
            file.write(content)

import os
import json
import subprocess
from openai import OpenAI
from textwrap import dedent
import testagon.util as util
from testagon.logger import logger

def run_tests(test_file_path: str):
    """
    Runs the pytest tests located at `test_file_path` and captures the results.
    """
    try:
        # Execute pytest and capture output
        result = subprocess.run(
            ["pytest", test_file_path, "--json-report", "--json-report-file=report.json"],
            capture_output=True,
            text=True
        )
        # Check if pytest executed successfully
        if result.returncode == 0:
            logger.debug("All tests passed successfully!")
            return None, True
        else:
            logger.debug("Some tests failed. See details below:")
            with open("report.json") as report_file:
                report = json.load(report_file)
            return report, False
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        return None, False

def get_failed_tests(report):
    """
    Analyze the pytest report to understand failures and unexpected behavior.
    """
    failed_tests = []
    for test in report.get("tests", []):
        if test["outcome"] == "failed":
            test_name = test["nodeid"]
            failure_message = test.get("call", {}).get("longrepr", "No failure details")
            
            # Store failure information
            failed_tests.append({
                "test_name": test_name,
                "failure_message": failure_message
            })
    return failed_tests

def generate_feedback(client: OpenAI, source_path: str, test_code: str, failed_tests: list[dict]):
    """
    Uses the LLM to generate feedback on failed tests and suggest corrections.
    """
    file_structure = "\n".join(util.get_project_structure())

    completion = client.chat.completions.create(
        model=os.getenv("MODEL"),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "suggest_test_fixes",
                "schema": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "test_name": {"type": "string"},
                            "explanation": {"type": "string"},
                            "problem_source": {"type": "string", "enum": ["source", "test"]},
                            "suggestion": {"type": "string"}
                        },
                        "required": ["test_name", "explanation", "problem_source", "suggestion"],
                        "additionalProperties": False
                    }
                },
                "strict": True
            }
        },
        messages=[
            {
                "role": "system",
                "content": dedent("""
                    You will be provided the source code of a Python file, the code of a pytest file performing unit tests
                    on that file, and the file structure of the Python project the source is part of. After running pytest,
                    some of the unit tests have failed. The user will provide the name of each unit test followed by the report
                    detailing how it failed.
                                    
                    It is possible that the user wrote the unit test incorrectly, but it is also possible that the intended 
                    logic of the source program does not match the code. Given your reasoning, determine whether the source 
                    of the failed test is due to an error in the source code or an error in the unit test itself.
                                    
                    If the cause of the problem was the source code, suggest how the source code could be fixed in the future.
                    If the unit test was the problem, suggest how to fix the unit test.
                """)
            },
            {
                "role": "user",
                "content": dedent(f"""
                    # Source file #
                    ```python
                    {source_path}
                    ```

                    # Unit tests #
                    ```python
                    {test_code}
                    ```

                    # Project directory structure #
                    `{file_structure}`

                    # Failed tests #
                    {"\n\n".join(
                        f"## {t.get("test_name")} ##\n```\n{t.get("failure_message")}\n```" 
                        for t in failed_tests
                    )}
                """)
            }
        ]
    )
        
    response = json.loads(completion.choices[0].message.content)
    tests_to_fix = list(filter(lambda x: x.get("problem_source") == "test", response))
    if len(tests_to_fix) == 0:
        return
    
    # TODO: Pass feedback to actor

def critic_process(client: OpenAI, test_file_path: str):
    """
    Executes the entire critic process: running tests, analyzing failures, and providing feedback.
    """
    report, success = run_tests(test_file_path)
    if not success and report:
        analysis = get_failed_tests(report)
        generate_feedback(client, analysis)
    elif report is None:
        logger.error("Tests were unable to execute!")
    else:
        logger.info("All tests passed, no feedback needed!")

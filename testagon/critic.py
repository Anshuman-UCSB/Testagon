import os
import tempfile
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
        (f, report_path) = tempfile.mkstemp()
        logger.debug("Creating temporary file for pytest report at %s", report_path)
        result = subprocess.run(
            [
                "pytest",
                test_file_path,
                "--json-report",
                f"--json-report-file={report_path}",
            ],
            capture_output=True,
            text=True,
        )
        # Check if pytest executed successfully
        if result.returncode == 0:
            logger.debug("All tests passed successfully!")
            os.remove(report_path)
            return None, True
        else:
            logger.debug("Some tests failed. See details below:")
            with open(report_path) as f:
                report = json.load(f)
            os.remove(report_path)
            return report, False
    except Exception as e:
        logger.error(f"Error running tests: {e}")
        os.remove(report_path)
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
            failed_tests.append(
                {"test_name": test_name, "failure_message": failure_message}
            )
    return failed_tests


def generate_feedback(
    client: OpenAI, source_path: str, test_path: str, failed_tests: list[dict]
):
    """
    Uses the LLM to generate feedback on failed tests and suggest corrections.
    """
    file_structure = "\n".join(util.get_project_structure())

    with open(source_path, "r") as sf, open(test_path, "r") as tf:
        source_code = sf.read()
        test_code = tf.read()

        test_summary = "\n\n".join(
            "\n".join(
                [
                    f"## Test: {t.get('test_name')} ##",
                    "```",
                    t.get("failure_message"),
                    "```",
                ]
            )
            for t in failed_tests
        )

        completion = client.chat.completions.create(
            model=util.get_model(),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "suggest_test_fixes",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "problems": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        # The name of the test function
                                        "test_name": {"type": "string"},
                                        # Explanation of the problem with the unit test
                                        "explanation": {"type": "string"},
                                        # Whether the problem is attributed to bad source code or a unit test issue
                                        "problem_source": {
                                            "type": "string",
                                            "enum": ["source", "test"],
                                        },
                                        # Suggestion for how to fix the problem
                                        "suggestion": {"type": "string"},
                                    },
                                    "required": [
                                        "test_name",
                                        "explanation",
                                        "problem_source",
                                        "suggestion",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["problems"],
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
                        You will be provided the source code of a Python file, the code of a pytest script performing unit tests
                        on that file, and the file structure of the Python project the source is part of. After running pytest,
                        some of the unit tests have failed. The user will provide the name of each unit test followed by the report
                        detailing how it failed.
                                      
                        For each failed test, put the test's name in `test_name`, then reason about why the test failed. Was
                        the function expecting inputs that it did not expect? Were the listed invariants violated? Was some edge
                        case missed? Consider all of these ideas when providing the `explanation` of what went wrong.
                                        
                        It is possible that the source code failed to account for certain issues, but it is also possible that
                        the unit test itself is flawed. Given your reasoning, determine whether the `problem_source`
                        of the failed test is due to an error in the source code or an error in the unit test itself.
                                        
                        If the cause of the problem was the source code, suggest how the source code could be fixed in the future.
                        If the unit test was the problem, suggest how to fix the unit test. This is placed in `suggestion` as
                        natural language.
                        
                        Your output should be a JSON object.
                    """
                    ),
                },
                {
                    "role": "user",
                    "content": dedent(
                        f"""
                        # Source file #
                        ```python
                        {source_code}
                        ```

                        # Unit tests #
                        ```python
                        {test_code}
                        ```

                        # Project directory structure #
                        `{file_structure}`

                        # Failed tests #
                        {test_summary}
                    """
                    ),
                },
            ],
        )

        raw_res = completion.choices[0].message.content
        logger.debug("[LLM response]\n%s", raw_res)
        response = json.loads(raw_res)
        return response["problems"]


def integrate_feedback(
    client: OpenAI,
    source_path: str,
    test_path: str,
    critic_feedback: list[dict],
    syntax_iterations: int,
):
    tests_to_fix = list(
        filter(lambda x: x.get("problem_source") == "test", critic_feedback)
    )
    if len(tests_to_fix) == 0:
        logger.info("(%s) All unit tests are correct", test_path)
        return True

    logger.info("(%s) %i test(s) are fixable", test_path, len(tests_to_fix))

    with open(source_path, "r") as sf, open(test_path, "r") as tf:
        source_code = sf.read()
        test_code = tf.read()

        suggested_fixes = "\n\n".join(
            "\n".join(
                [
                    f"# {t.get('test_name')} #" "## Explanation ##",
                    t.get("explanation"),
                    "## Suggested Fix ##",
                    t.get("suggestion"),
                ]
            )
            for t in tests_to_fix
        )

        completion = client.chat.completions.create(
            model=util.get_model(),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "test_feedback",
                    "schema": {
                        "type": "object",
                        "properties": {
                            # All output that is not part of the resulting file
                            "scratchpad": {"type": "string"},
                            # The unit test with the fix implemented
                            "updated_file": {"type": "string"},
                        },
                        "required": ["scratchpad", "updated_file"],
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
                        You are a programmer writing unit tests for a Python module. You have sent your source code
                        and unit testing to be reviewed by another person, who has run the unit tests and noticed that
                        some tests have failed.
                                      
                        This person will provide the source file and the test code for reference, then go through each
                        erroneous test function and suggest fixes. Your job is to update the test file with these changes.
                                      
                        Your response should be output in JSON, with `updated_file` containing only the full updated test script.
                    """
                    ),
                },
                {
                    "role": "user",
                    "content": dedent(
                        f"""
                        It looks like some of the tests have failed. For reference, here is your source code:
                        ```python
                        {source_code}
                        ```

                        And here is the Pytest test code you submitted to me:
                        ```python
                        {test_code}
                        ```

                        Here are the tests that failed, and my suggested fixes:
                        {suggested_fixes}
                    """
                    ),
                },
            ],
        )

        # Parse LLM response
        raw_res = completion.choices[0].message.content
        logger.debug("[LLM response]\n%s", raw_res)
        response = json.loads(raw_res)
        new_file = response["updated_file"]

        # Ensure correct syntax of the test file
        logger.info("(%s) Testing for valid response syntax", test_path)
        new_file = util.validate_syntax(client, new_file, syntax_iterations)
        logger.info("(%s) Received valid response syntax, writing to file", test_path)

        # Dump result for target file to test script
        with open(test_path, "w") as test_file:
            test_file.write(new_file)

    return False


def critic_process(
    client: OpenAI, source_path: str, test_path: str, max_iter=10, syntax_iterations=10
):
    """
    Executes the entire critic process: running tests, analyzing failures, and providing feedback.
    """
    for i in range(0, max_iter):
        report, success = run_tests(test_path)
        if not success and report:
            analysis = get_failed_tests(report)
            feedback = generate_feedback(client, source_path, test_path, analysis)
            finished = integrate_feedback(
                client, source_path, test_path, feedback, syntax_iterations
            )
            if finished:
                break
        elif report is None:
            logger.error("Tests were unable to execute!")
            return

    logger.info("(%s) Unit test iteration completed", test_path)

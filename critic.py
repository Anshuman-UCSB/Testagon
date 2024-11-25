import os
import json
import subprocess
from openai import OpenAI
from textwrap import dedent

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
            print("All tests passed successfully!")
            return None, True
        else:
            print("Some tests failed. See details below:")
            with open("report.json") as report_file:
                report = json.load(report_file)
            return report, False
    except Exception as e:
        print(f"Error running tests: {e}")
        return None, False

def analyze_report(report):
    """
    Analyze the pytest report to understand failures and unexpected behavior.
    """
    analysis = {
        "failed_tests": [],
        "suggestions": []
    }
    for test in report.get("tests", []):
        if test["outcome"] == "failed":
            test_name = test["nodeid"]
            failure_message = test.get("call", {}).get("longrepr", "No failure details")
            
            # Store failure information
            analysis["failed_tests"].append({
                "test_name": test_name,
                "failure_message": failure_message
            })
            
            # Create feedback for the LLM to generate better tests
            analysis["suggestions"].append({
                "test_name": test_name,
                "suggestion": dedent(f"""
                    The test `{test_name}` failed. Here is the failure message:
                    {failure_message}
                    
                    Please provide an explanation of why this failure might occur and suggest improved invariants or test conditions.
                    Consider if there are any logic flaws in the source code that could cause this failure.
                """)
            })
    return analysis

def feedback_loop(client: OpenAI, analysis):
    """
    Uses the LLM to generate feedback on failed tests and suggest corrections.
    """
    for suggestion in analysis["suggestions"]:
        completion = client.chat.completions.create(
            model='oai-gpt-4o-mini' if os.getenv("USE_MINI_MODEL", False) else 'oai-gpt-4o-structured',
            messages=[
                {
                    "role": "system",
                    "content": dedent("""
                        You will be provided with details of a failed unit test case.
                        Your task is to explain why this failure might have occurred and suggest how the test or the 
                        source code could be adjusted to handle it properly. Make sure any changes do not alter the intended behavior of the program.
                    """)
                },
                {
                    "role": "user",
                    "content": suggestion["suggestion"]
                }
            ]
        )
        
        response = json.loads(completion.choices[0].message.content)
        print(f"Feedback for {suggestion['test_name']}: {response.get('explanation')}")
        print(f"Suggested Fix: {response.get('fix')}")
        
        # Optionally, apply fixes directly to the test file or code (actor correction step)
        # ...

def critic_process(client: OpenAI, test_file_path: str):
    """
    Executes the entire critic process: running tests, analyzing failures, and providing feedback.
    """
    report, success = run_tests(test_file_path)
    if not success and report:
        analysis = analyze_report(report)
        feedback_loop(client, analysis)
    else:
        print("All tests passed, no feedback needed!")

# Example usage
if __name__ == "__main__":
    # Initialize OpenAI client with API key
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Path to the generated test file by the actor LLM
    test_file_path = "generated_test_file.py"  # Adjust to the correct file location
    
    # Run the critic process
    critic_process(client, test_file_path)
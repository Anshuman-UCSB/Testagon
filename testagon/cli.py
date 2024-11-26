import argparse
import os
import threading
from openai import OpenAI
from dotenv import load_dotenv
import testagon.unit_tests as unit_tests
import testagon.util as util

# Initialize OpenAI client
load_dotenv()
client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))


def init_project():
    print("Initializing a new project...")
    try:
        os.makedirs("tests", exist_ok=False)
        print("Created 'tests' folder in the current directory.")
    except FileExistsError:
        print("'tests' folder already exists in the current directory.")
        return


def generate_tests(auto: bool):
    print("Generating invariants...")
    # generate_invariants(client, ...)

    print("Generating initial unit tests...")
    unit_test_threads: list[threading.Thread] = []

    # Spawn threads to generate tests for each file concurrently
    for path in util.get_project_structure():
        if path.startswith("./tests/"): continue
        if not path.endswith(".py"): continue
        test_dir = os.path.relpath(os.path.join("tests", os.path.dirname(path)), os.getcwd())
        os.makedirs(os.path.join("tests", os.path.dirname(path)), exist_ok=True)
        test_path = os.path.join(test_dir, os.path.basename(path))
        thread = threading.Thread(target=unit_tests.generate_initial, args=(client, path, test_path))
        thread.start()
        unit_test_threads.append(thread)

    # Wait for all generation to finish
    for thread in unit_test_threads:
        thread.join()

def run_tests():
    import pytest
    pytest.main()

def main():
    parser = argparse.ArgumentParser(
        description="A tool to determine logic invariants, and generate tests for them."
    )
    subparsers = parser.add_subparsers(dest="command")

    # Subcommand for 'init'
    init_parser = subparsers.add_parser("init", help="Initialize a new project.")

    # Subcommand for 'generate'
    generate_parser = subparsers.add_parser(
        "generate", help="Generate tests for the project."
    )

    # Subcommand for 'init'
    test_parser = subparsers.add_parser("test", help="Run testagon tests.")

    generate_parser.add_argument(
        "-a",
        "--auto",
        type=str,
        help="Automatically run E2E without human interaction.",
    )

    args = parser.parse_args()

    if args.command == "init":
        init_project()
    elif args.command == "generate":
        generate_tests(args.auto)
    elif args.command == "test":
        run_tests()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

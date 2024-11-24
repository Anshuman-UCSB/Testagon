import argparse
import os
import threading
from openai import OpenAI
from dotenv import load_dotenv
import unit_tests
import util


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
        # TODO: Get correct test file path and pass to generate_initial
        thread = threading.Thread(target=unit_tests.generate_initial, args=(client, path, None))
        thread.start()
        unit_test_threads.append(thread)

    # Wait for all generation to finish
    for thread in unit_test_threads:
        thread.join()

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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

import argparse
import os
from openai import OpenAI
from dotenv import load_dotenv
import unit_tests


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
    # unit_tests.generate_initial(client)

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

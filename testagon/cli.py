import argparse
import os
import threading
from openai import OpenAI
import testagon.unit_tests as unit_tests
import testagon.util as util
import testagon.critic as critic
import logging
from testagon.generate_invariants import generate_invariants
from testagon.logger import logger, configure_logger


def configure(api_key: str | None, base_url: str | None, model: str | None):
    config = util.read_config()
    if api_key is not None:
        config["DEFAULT"]["api_key"] = api_key
    if base_url is not None:
        config["DEFAULT"]["base_url"] = base_url
    if model is not None:
        config["DEFAULT"]["model"] = model
    util.write_config(config)


def init_project():
    logger.info("Initializing a new project...")
    try:
        os.makedirs("tests/testagon", exist_ok=False)
        logger.info("Created 'tests/testagon' folder in the current directory.")
    except FileExistsError:
        logger.error("'tests/testagon' folder already exists in the current directory.")
        return


def generate_tests(auto: bool, syntax_iterations: int, critic_iterations: int):
    TESTDIR_STRUCTURE = "tests/testagon"
    config = util.read_config()
    client = OpenAI(
        api_key=config["DEFAULT"].get("api_key"),
        base_url=config["DEFAULT"].get("base_url"),
    )

    # Spawn threads to generate invariants for each Python source file
    logger.info("Generating invariants...")
    invariant_threads: list[threading.Thread] = []
    for path in util.get_source_programs():
        logger.info("Generating invariants for file %s", path)
        thread = threading.Thread(target=generate_invariants, args=(client, path))
        thread.start()
        invariant_threads.append(thread)

    logger.info("Waiting for all threads to finish...")
    for thread in invariant_threads:
        thread.join()
    logger.info("Complete!")

    # Spawn threads to generate tests for each file concurrently
    logger.info("Generating initial unit tests...")
    unit_test_threads: list[threading.Thread] = []
    for path in util.get_source_programs():
        logger.info("Generating tests for file %s", path)

        # Find and create file path in tests/testagon
        test_dir = os.path.relpath(
            os.path.join(TESTDIR_STRUCTURE, os.path.dirname(path)), os.getcwd()
        )
        os.makedirs(test_dir, exist_ok=True)

        test_path = os.path.join(test_dir, "test_" + os.path.basename(path))
        thread = threading.Thread(
            target=unit_tests.generate_initial,
            args=(client, path, test_path, syntax_iterations),
        )
        thread.start()
        unit_test_threads.append(thread)

    logger.info("Waiting for all threads to finish...")
    for thread in unit_test_threads:
        thread.join()
    logger.info("Complete!")

    # Must add __init__.py to each directory to avoid naming conflicts from duplicates
    logger.debug(
        "Adding __init__.py to each directory to avoid naming conflicts from duplicates"
    )
    BASE_INIT_PATH = os.path.join(TESTDIR_STRUCTURE, "__init__.py")
    logger.info("Creating init at %s", BASE_INIT_PATH)
    open(BASE_INIT_PATH, "w").close()

    for path in util.get_all_dirs(TESTDIR_STRUCTURE):
        init_file_path = os.path.join(path, "__init__.py")
        logger.info("Creating init at %s", init_file_path)
        open(init_file_path, "w").close()

    # Spawn threads to iterate on each test file concurrently
    logger.info("Running critic feedback loop on test files...")
    critic_threads: list[threading.Thread] = []
    for path in util.get_source_programs():
        test_dir = os.path.relpath(
            os.path.join(TESTDIR_STRUCTURE, os.path.dirname(path)), os.getcwd()
        )
        test_path = os.path.join(test_dir, "test_" + os.path.basename(path))

        logger.info("Evaluating test file %s", test_path)
        thread = threading.Thread(
            target=critic.critic_process,
            args=(client, path, test_path, critic_iterations, syntax_iterations),
        )
        thread.start()
        critic_threads.append(thread)

    logger.info("Waiting for all threads to finish...")
    for thread in critic_threads:
        thread.join()
    logger.info("Complete!")


def run_tests():
    import subprocess

    subprocess.run("python3 -m pytest tests/testagon".split())


def main():
    configure(None, None, None)

    parser = argparse.ArgumentParser(
        description="A tool to determine logic invariants, and generate tests for them."
    )

    parser.add_argument(
        "-l",
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand for 'init'
    init_parser = subparsers.add_parser("init", help="Initialize a new project.")

    # Subcommand for 'generate'
    generate_parser = subparsers.add_parser(
        "generate", help="Generate tests for the project."
    )

    generate_parser.add_argument(
        "-a",
        "--auto",
        action="store_true",
        help="Automatically run E2E without human interaction.",
    )

    generate_parser.add_argument(
        "-s",
        "--syntax-iterations",
        type=int,
        default=10,
        help="The maximum number of times the LLM should iterate to correct syntax errors.",
    )

    generate_parser.add_argument(
        "-c",
        "--critic-iterations",
        type=int,
        default=10,
        help="The maximum number of times to iterate the actor-critic feedback loop on each unit test file.",
    )

    # Subcommand for 'init'
    test_parser = subparsers.add_parser("test", help="Run testagon tests.")

    # Subcommand for 'config'
    api_key_parser = subparsers.add_parser(
        "config", help="Modifies the config options for Testagon."
    )

    api_key_parser.add_argument(
        "-k", "--key", type=str, help="The OpenAI API key to use."
    )

    api_key_parser.add_argument(
        "-u", "--url", type=str, help="The base URL to send all OpenAI queries to."
    )

    api_key_parser.add_argument("-m", "--model", type=str, help="The LLM model to use.")

    args = parser.parse_args()
    configure_logger(getattr(logging, args.log_level))

    if args.command == "init":
        init_project()
    elif args.command == "generate":
        generate_tests(args.auto, args.syntax_iterations, args.critic_iterations)
    elif args.command == "test":
        run_tests()
    elif args.command == "config":
        configure(args.key, args.url, args.model)
        logger.info("Updated config file.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

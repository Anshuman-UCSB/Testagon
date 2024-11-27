import argparse
import os
import threading
from openai import OpenAI
from dotenv import load_dotenv
import testagon.unit_tests as unit_tests
import testagon.util as util
import logging
from testagon.logger import logger, configure_logger

# Initialize OpenAI client
load_dotenv()
client = OpenAI(api_key=os.getenv("API_KEY"), base_url=os.getenv("BASE_URL"))


def init_project():
	logger.info("Initializing a new project...")
	try:
		os.makedirs("tests/testagon", exist_ok=False)
		logger.info("Created 'tests/testagon' folder in the current directory.")
	except FileExistsError:
		logger.error("'tests/testagon' folder already exists in the current directory.")
		return


def generate_tests(auto: bool):
	TESTDIR_STRUCTURE = "tests/testagon"

	logger.info("Generating invariants...")
	# generate_invariants(client, ...)

	logger.info("Generating initial unit tests...")
	unit_test_threads: list[threading.Thread] = []

	# Spawn threads to generate tests for each file concurrently
	logger.info("Scanning files...")
	for path in util.get_project_structure():
		if path.startswith("./tests/"): continue
		if not path.endswith(".py"): continue
		if path.startswith("test"): continue # Skip test files
		logger.info("Found file %s",path)

		# Find and create file path in tests/testagon
		test_dir = os.path.relpath(os.path.join(TESTDIR_STRUCTURE, os.path.dirname(path)), os.getcwd())
		os.makedirs(os.path.join(TESTDIR_STRUCTURE, os.path.dirname(path)), exist_ok=True)

		test_path = os.path.join(test_dir, "test_"+os.path.basename(path))
		thread = threading.Thread(target=unit_tests.generate_initial, args=(client, path, test_path))
		thread.start()
		unit_test_threads.append(thread)

	logger.info("Waiting for all threads to finish...")
	# Wait for all generation to finish
	for thread in unit_test_threads:
		thread.join()
	logger.info("Complete!")

def run_tests():
	import subprocess
	subprocess.run("python3 -m pytest tests/testagon".split())

def main():
	parser = argparse.ArgumentParser(
		description="A tool to determine logic invariants, and generate tests for them."
	)

	parser.add_argument(
		"-l",
		"--log-level", 
		type=str,
		choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
		default="INFO",
		help="Set the logging level (default: INFO)"
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

	# Subcommand for 'init'
	test_parser = subparsers.add_parser("test", help="Run testagon tests.")

	args = parser.parse_args()
	configure_logger(getattr(logging, args.log_level))

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

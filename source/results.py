
import json
import os



GEN_DIR = "/autograder/source/gen"
SOL_DIR = "/autograder/source/sol"
RESULT_DIR = "/autograder/results"



POINTS_PER_FILE = 0.25


def compare_binaries(generated_path, solution_path):
    """Compare two binary files exactly."""
    try:
        with open(generated_path, 'rb') as f1:
            generated = f1.read()
        with open(solution_path, 'rb') as f2:
            solution = f2.read()
        return generated == solution
    except Exception as e:
        print(f"Error comparing binaries: {e}")
        return False


def compare_text_files(generated_path, solution_path):
    """
    Compare text files while ignoring harmless formatting differences:
    - Windows vs Linux line endings
    - blank lines
    - leading/trailing spaces
    - uppercase/lowercase hex letters
    """
    try:
        with open(generated_path, 'r', newline=None) as f1:
            generated = [
                line.strip().lower()
                for line in f1
                if line.strip()
            ]

        with open(solution_path, 'r', newline=None) as f2:
            solution = [
                line.strip().lower()
                for line in f2
                if line.strip()
            ]

        return generated == solution
    except Exception as e:
        print(f"Error comparing text files: {e}")
        return False

def get_text_mismatch_message(generated_path, solution_path, max_mismatches=10):
    """
    Creates a clean line-by-line mismatch message for text files.
    Uses the same normalization as compare_text_files().
    """
    try:
        with open(generated_path, 'r', newline=None) as f1:
            generated = [
                line.strip().lower()
                for line in f1
                if line.strip()
            ]

        with open(solution_path, 'r', newline=None) as f2:
            solution = [
                line.strip().lower()
                for line in f2
                if line.strip()
            ]

        lines = []
        lines.append("Line mismatches:")

        max_len = max(len(generated), len(solution))
        mismatch_count = 0

        for i in range(max_len):
            gen_line = generated[i] if i < len(generated) else "<missing line>"
            sol_line = solution[i] if i < len(solution) else "<extra generated line>"

            if gen_line != sol_line:
                mismatch_count += 1

                if mismatch_count <= max_mismatches:
                    lines.append(f"Line {i + 1}:")
                    lines.append(f"  Expected:  {sol_line}")
                    lines.append(f"  Generated: {gen_line}")

        if mismatch_count == 0:
            return ""

        if mismatch_count > max_mismatches:
            lines.append(
                f"... {mismatch_count - max_mismatches} more mismatched line(s) not shown."
            )

        lines.append(f"Total mismatched lines: {mismatch_count}")

        return "\n".join(lines) + "\n"

    except Exception as e:
        return f"Could not generate line mismatch details: {e}\n"

def gen_path(filename):
    return os.path.join(GEN_DIR, filename)


def sol_path(filename):
    return os.path.join(SOL_DIR, filename)


def make_check_result(name, generated_filename, solution_filename):
    """Create the standard check result dictionary."""
    return {
        "name": name,
        "passed": False,
        "points": 0,
        "error_type": None,
        "details": {},
        "generated_filename": generated_filename,
        "solution_filename": solution_filename,
        "generated_path": gen_path(generated_filename),
        "solution_path": sol_path(solution_filename)
    }


def missing_file_message(result):
    """Create a helpful message when a generated file is missing."""
    generated_path = result["generated_path"]
    generated_filename = result["generated_filename"]
    gen_folder = os.path.dirname(generated_path)

    message = (
        f"Missing file: {generated_filename}\n"
        f"Expected your assembler to create this exact file:\n"
        f"{generated_path}\n"
    )

    if os.path.exists(gen_folder):
        found_files = sorted(os.listdir(gen_folder))

        if found_files:
            message += "\nFiles found in output folder:\n"
            for filename in found_files:
                message += f"- {filename}\n"
        else:
            message += "\nThe output folder exists, but it is empty.\n"
    else:
        message += "\nThe output folder does not exist.\n"

    message += (
        "\nCheck that the filename matches exactly, including underscores, "
        "extensions, and .hex.txt endings.\n"
    )

    return message

def get_text_line_mismatches(generated_path, solution_path, max_mismatches=10):
    """
    Return line-by-line mismatch details for text files.
    Uses the same normalization rules as compare_text_files().
    """
    try:
        with open(generated_path, 'r', newline=None) as f1:
            generated = [
                line.strip().lower()
                for line in f1
                if line.strip()
            ]

        with open(solution_path, 'r', newline=None) as f2:
            solution = [
                line.strip().lower()
                for line in f2
                if line.strip()
            ]

        mismatches = []
        max_len = max(len(generated), len(solution))

        for i in range(max_len):
            gen_line = generated[i] if i < len(generated) else "<missing line>"
            sol_line = solution[i] if i < len(solution) else "<extra generated line>"

            if gen_line != sol_line:
                mismatches.append({
                    "line": i + 1,
                    "expected": sol_line,
                    "generated": gen_line
                })

                if len(mismatches) >= max_mismatches:
                    break

        return mismatches

    except Exception as e:
        return [
            {
                "line": "unknown",
                "expected": "could not read expected file",
                "generated": f"could not read generated file: {e}"
            }
        ]

def run_file_check(
    name,
    generated_filename,
    solution_filename,
    compare_func,
    show_line_mismatches=False
):
    """
    Run one file check and return structured check data.
    This function detects the problem but does not format the student message.
    """
    result = make_check_result(name, generated_filename, solution_filename)

    if not os.path.exists(result["generated_path"]):
        result["error_type"] = "missing_file"
        result["details"] = {
            "missing_file": generated_filename
        }
        return result

    if not os.path.exists(result["solution_path"]):
        result["error_type"] = "missing_solution"
        result["details"] = {
            "missing_file": solution_filename
        }
        return result

    if compare_func(result["generated_path"], result["solution_path"]):
        result["passed"] = True
        result["points"] = POINTS_PER_FILE
        result["error_type"] = None
        result["details"] = {}
        return result

    result["error_type"] = "content_mismatch"

    details = {
        "generated_file": generated_filename,
        "solution_file": solution_filename,
        "show_line_mismatches": show_line_mismatches
    }

    if show_line_mismatches:
        details["line_mismatches"] = get_text_line_mismatches(
            result["generated_path"],
            result["solution_path"]
        )

    result["details"] = details

    return result


def build_test_checks(test_name):
    """
    Build the six standard file checks for one test case.
    Example test_name: 'add_shift' or 'test'
    """
    return [
        run_file_check(
            "Instruction Binary",
            f"{test_name}.bin",
            f"{test_name}_sol.bin",
            compare_binaries
        ),
        run_file_check(
            "Instruction Hex",
            f"{test_name}.hex.txt",
            f"{test_name}_sol.hex.txt",
            compare_text_files,
            show_line_mismatches=True
        ),
        run_file_check(
            "Data Binary",
            f"{test_name}_data.bin",
            f"{test_name}_sol_data.bin",
            compare_binaries
        ),
        run_file_check(
            "Data Hex",
            f"{test_name}_data.hex.txt",
            f"{test_name}_sol_data.hex.txt",
            compare_text_files,
            show_line_mismatches=True
        ),
        run_file_check(
            "Instruction Addresses",
            f"{test_name}_instruction_addresses.txt",
            f"{test_name}_sol_instruction_addresses.txt",
            compare_text_files,
            show_line_mismatches=True
        ),
        run_file_check(
            "Data Addresses",
            f"{test_name}_data_addresses.txt",
            f"{test_name}_sol_data_addresses.txt",
            compare_text_files,
            show_line_mismatches=True
        )
    ]

def format_error_message(check, detailed=False):
    """Format a structured error into a clean student-facing message."""
    if check["passed"]:
        return ""

    error_type = check["error_type"]
    details = check["details"]

    if error_type == "missing_file":
        return (
            f"Missing output file: {details['missing_file']}\n"
            "Your assembler did not generate this required file.\n"
        )

    if error_type == "missing_solution":
        return (
            "Internal autograder error: missing solution file.\n"
            f"Missing solution file: {details['missing_file']}\n"
        )

    if error_type == "content_mismatch":
        if not detailed:
            return "The file contents did not match the expected output.\n"

        lines = []
        lines.append("The file was generated, but its contents are incorrect.")

        mismatches = details.get("line_mismatches", [])

        if mismatches:
            lines.append("")
            lines.append("Mismatched lines:")

            for mismatch in mismatches:
                lines.append(f"Line {mismatch['line']}:")
                lines.append(f"  Expected : {mismatch['expected']}")
                lines.append(f"  Generated: {mismatch['generated']}")

        return "\n".join(lines) + "\n"

    return "Unknown error.\n"

def format_check_results(checks, detailed=False):
    """
    Format check results for Gradescope output.
    detailed=True gives students more information, useful for public tests.
    detailed=False gives only a summary, useful for hidden tests.
    """
    output = ""

    passed_count = sum(1 for check in checks if check["passed"])
    total_count = len(checks)
    score = sum(check["points"] for check in checks)
    max_score = total_count * POINTS_PER_FILE

    output += f"Score: {score:.2f} / {max_score:.2f}\n"
    output += f"Passed {passed_count} / {total_count} file checks.\n"
    output += f"Each file is worth {POINTS_PER_FILE:.2f} points.\n\n"

    output += "File check summary:\n"

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        output += f"- {check['name']}: {status} ({check['points']:.2f} / {POINTS_PER_FILE:.2f})\n"

        if not check["passed"]:
            error_message = format_error_message(check, detailed=detailed)

            if error_message:
                output += "\n"
                output += error_message
                output += "\n"

    if detailed:
        output += (
            "\nNote: text-file comparisons ignore extra blank lines, "
            "leading/trailing spaces, uppercase/lowercase hex letters, "
            "and Windows/Linux line-ending differences.\n"
        )

    return output


def debug_print_checks():
    add_shift_checks = build_test_checks("add_shift")
    test_checks = build_test_checks("test")

    print("===== ADD_SHIFT CHECKS =====")
    for check in add_shift_checks:
        print(f"{check['name']}: {check['passed']}")

    print("\n===== TEST CHECKS =====")
    for check in test_checks:
        print(f"{check['name']}: {check['passed']}")


def generate_results_json(result_dir=RESULT_DIR):
    """Generate results.json with test scores."""
    add_shift_checks = build_test_checks("add_shift")
    test_checks = build_test_checks("test")

    add_shift_score = sum(check["points"] for check in add_shift_checks)
    test_score = sum(check["points"] for check in test_checks)

    # add_shift is the public/given test, so give detailed feedback.
    add_shift_details = format_check_results(add_shift_checks, detailed=True)

    # test is hidden/private, so give less specific feedback.
    test_details = format_check_results(test_checks, detailed=False)

    output_json = {
        "score": 0,
        "output": "Phase 2 Autograder",
        "tests": [
            {
                "name": "add_shift",
                "score": add_shift_score,
                "max_score": 1.5,
                "output": add_shift_details,
                "visibility": "visible"
            },
            {
                "name": "test",
                "score": test_score,
                "max_score": 1.5,
                "output": test_details,
                "visibility": "visible"
            }
        ]
    }

    output_json['score'] = add_shift_score + test_score

    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    with open(os.path.join(result_dir, 'results.json'), 'w') as f:
        json.dump(output_json, f, indent=4)

    return output_json


if __name__ == "__main__":
    #debug_print_checks()
    results = generate_results_json()
    print("\n===== add_shift =====\n")
    print(results["tests"][0]["output"])

    print("\n===== test =====\n")
    print(results["tests"][1]["output"])

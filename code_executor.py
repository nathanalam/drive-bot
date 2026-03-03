import os
import sys
import tempfile
import subprocess

# Absolute path to the project directory so the subprocess can import
# drive_bot_tools, google_auth_doc, and the rest of the project modules.
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_code(code: str, timeout: int = 30) -> tuple[str, str, int]:
    """
    Execute a Python snippet in a sandboxed subprocess.

    The subprocess runs with the project's Python interpreter (same venv),
    with PROJECT_DIR prepended to PYTHONPATH so that drive_bot_tools and
    all other project modules are importable.

    Returns (stdout, stderr, returncode).
    Stdout and stderr are strings. returncode is 0 on success.
    On timeout, returns ("", "Code execution timed out after N seconds.", 1).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir=PROJECT_DIR, delete=False
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{PROJECT_DIR}:{existing_pythonpath}"
            if existing_pythonpath
            else PROJECT_DIR
        )

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_DIR,
            env=env,
        )
        return result.stdout, result.stderr, result.returncode

    except subprocess.TimeoutExpired:
        return "", f"Code execution timed out after {timeout} seconds.", 1

    finally:
        os.unlink(tmp_path)

import subprocess
import os
import shutil
import tempfile
from typing import Annotated, Optional, List, Dict, Any
from pydantic import Field

def run_command(cmd: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Executes a command using subprocess and returns output and errors."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -2,
            "stdout": "",
            "stderr": "Error: Execution timed out"
        }


def install_dependencies(packages: Optional[List[str]], install_cmd_path: str = "npm") -> Dict[str, Any]:
    """
    Installs Node.js packages using the specified npm executable.

    Args:
        packages: A list of npm package names to install.
        install_cmd_path: Path to the npm executable to use.

    Returns:
        The result of the package installation command, or a no-op result if no install is needed.
    """
    if not packages:
        return {"returncode": 0, "stdout": "", "stderr": ""}  # No installation needed

    cmd = [install_cmd_path, "install"] + packages
    return run_command(cmd)

def run_in_tempdir(code: str, packages: Optional[List[str]]) -> Dict[str, Any]:
    """
    Runs Node.js code in a temporary directory after installing optional npm packages.

    Note that this does NOT mean the code is fully isolated or secure - it just means the npm installations
    are isolated.

    Args:
        code: The code to run.
        packages: Optional npm packages to install before execution.

    Returns:
        Dictionary of returncode, stdout, and stderr.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        # Initialize a package.json to avoid warnings from npm
        with open(os.path.join(temp_dir, "package.json"), "w") as f:
            f.write('{"type": "module"}')  # Enables top-level await if needed

        install_result = install_dependencies(packages, install_cmd_path="npm")
        if install_result["returncode"] != 0:
            return {
                "returncode": install_result["returncode"],
                "stdout": install_result["stdout"],
                "stderr": f"Dependency install failed:\n{install_result['stderr']}"
            }

        temp_path = os.path.join(temp_dir, "script.js")
        with open(temp_path, "w") as f:
            f.write(code)

        return run_command(["node", temp_path], cwd=temp_dir)

    finally:
        shutil.rmtree(temp_dir)


def code_exec_node(
    code: Annotated[
        str,
        Field(description="The Node.js code to execute as a string.")
    ],
    packages: Annotated[
        Optional[List[str]],
        Field(description="Optional list of npm package names to install before execution.")
    ] = None,
    use_temp_dir: Annotated[
        bool,
        Field(description="Use a temporary working directory for code execution and npm installs.")
    ] = False
) -> Dict[str, Any]:
    """Executes a Node.js code snippet with optional npm dependencies.

    The Node.js runtime has access to networking, the filesystem, and can use top-level await.
    A non-zero exit code is an error and should be fixed.

    Returns:
        JSON containing:
            - 'returncode': Exit status of the execution.
            - 'stdout': Captured standard output.
            - 'stderr': Captured standard error or install failure messages.
    """
    if use_temp_dir:
        return run_in_tempdir(code, packages)

    install_result = install_dependencies(packages, install_cmd_path="npm")
    if install_result["returncode"] != 0:
        return {
            "returncode": install_result["returncode"],
            "stdout": install_result["stdout"],
            "stderr": f"Dependency install failed:\n{install_result['stderr']}"
        }

    return run_command(["node", "-e", code])

import subprocess

def run_in_docker(container_id, command, return_exit_code=False):
    """Executes a command inside a running Docker container, detecting available shell.

    If return_exit_code is True, returns (success, message) where success is True iff
    the command exited with status 0 (aligns with pytest / runtests exit semantics).
    """
    # Check if bash is available, fallback to sh
    check_shell = f"docker exec {container_id} which bash"
    has_bash = subprocess.run(check_shell, shell=True, capture_output=True).returncode == 0
    shell_path = "bash" if has_bash else "sh"
    
    full_command = f"docker exec {container_id} {shell_path} -c \"{command}\""
    print(f"[DOCKER] Executing via {shell_path}: {command} in {container_id}")
    
    try:
        result = subprocess.run(
            full_command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=300
        )
        # ... rest of the logic
        output = result.stdout or ""
        error = result.stderr or ""
        
        if result.returncode == 0:
            msg = f"SUCCESS: Command executed.\nOUTPUT:\n{output}"
            ok = True
        else:
            msg = f"FAILURE: Command returned error code {result.returncode}.\nERROR:\n{error}\nOUTPUT:\n{output}"
            ok = False
        if return_exit_code:
            return ok, msg
        return msg
            
    except subprocess.TimeoutExpired:
        msg = "ERROR: Command timed out after 300 seconds."
        if return_exit_code:
            return False, msg
        return msg
    except Exception as e:
        msg = f"ERROR: Unexpected error while running docker command: {e}"
        if return_exit_code:
            return False, msg
        return msg

def check_container_exists(container_id):
    """Checks if a Docker container with the given ID exists and is running."""
    try:
        result = subprocess.run(
            f"docker inspect -f '{{{{.State.Running}}}}' {container_id}",
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip() == "true"
    except:
        return False

if __name__ == "__main__":
    # Test with a dummy container if possible
    # This requires a running container named 'liara-test'
    test_container = "liara-test"
    if check_container_exists(test_container):
        print(run_in_docker(test_container, "ls -la"))
    else:
        print(f"Container {test_container} not found. Skipping real-world test.")

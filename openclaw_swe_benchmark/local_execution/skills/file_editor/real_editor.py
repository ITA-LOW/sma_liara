import os

def read_file(file_path):
    """Reads the content of a file."""
    if not os.path.exists(file_path):
        return f"ERROR: File {file_path} not found."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"ERROR: Could not read file {file_path}: {e}"

def write_file(file_path, content):
    """Writes content to a file, creating directories if necessary."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"SUCCESS: File {file_path} updated."
    except Exception as e:
        return f"ERROR: Could not write to file {file_path}: {e}"

def apply_edit(file_path, old_str, new_str):
    """Simple string replacement in a file."""
    content = read_file(file_path)
    if content.startswith("ERROR:"):
        return content
    
    if old_str not in content:
        return f"ERROR: Target string not found in {file_path}."
    
    updated_content = content.replace(old_str, new_str)
    return write_file(file_path, updated_content)

if __name__ == "__main__":
    # Test simple write/read
    test_file = "test_skill.txt"
    print(write_file(test_file, "Hello LIARA"))
    print(read_file(test_file))
    print(apply_edit(test_file, "LIARA", "LIARA Framework"))
    print(read_file(test_file))
    os.remove(test_file)

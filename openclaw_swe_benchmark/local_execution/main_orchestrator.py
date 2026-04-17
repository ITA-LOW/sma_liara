import json
import urllib.request
import urllib.error
import os
import subprocess
import re
from datetime import datetime

# Import de Skills Reais do LIARA
try:
    from skills.file_editor.real_editor import read_file, apply_edit, write_file
    from skills.bash_executor.docker_qa import run_in_docker
except ImportError:
    print("[AVISO] Skills reais não encontradas.")

# Configuração Base
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = os.environ.get("LIARA_MODEL", "llama3.1")
REPOS_DIR = "repos"
MAX_RETRIES = int(os.environ.get("LIARA_RETRIES", "2"))  # Vera pode guiar Codey N vezes
os.makedirs("data", exist_ok=True)
LOG_FILE = f"data/agent_dialogue_{datetime.now().strftime('%m%d_%H%M')}.txt"

def log_dialogue(role, content):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n[{role}] {datetime.now()}\n{content}\n")

def prompt_agent(role_prompt, user_content):
    """Interação com o Ollama local."""
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": user_content}
        ],
        "stream": False
    }
    req = urllib.request.Request(OLLAMA_URL, json.dumps(data).encode('utf-8'), {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            content = result['message']['content']
            log_dialogue("SYSTEM: " + role_prompt[:50] + "...", user_content[:200] + "...")
            log_dialogue("AGENT RESPONSE", content)
            return content
    except Exception as e:
        return f"ERROR: {e}"

def extract_function_context(content, function_name):
    """Extrai o bloco de uma função específica do arquivo para dar contexto focado ao Codey."""
    if not function_name:
        return content[:4000]
    lines = content.split('\n')
    start = None
    for i, line in enumerate(lines):
        if f'def {function_name}' in line or f'class {function_name}' in line:
            start = max(0, i - 2)
            break
    if start is None:
        return content[:4000]
    end = min(len(lines), start + 80)
    return '\n'.join(lines[start:end])

def extract_test_failure(test_output):
    """Extrai apenas as linhas de falha relevantes do output dos testes — economiza contexto."""
    lines = test_output.split('\n')
    failure_lines = []
    capture = False
    for line in lines:
        if any(k in line for k in ['FAILED', 'ERROR', 'AssertionError', 'Traceback', 'File "', '>>>']):
            capture = True
        if capture:
            failure_lines.append(line)
        if len(failure_lines) > 30:  # Máximo 30 linhas de erro
            break
    return '\n'.join(failure_lines) if failure_lines else test_output[:800]

def apply_codey_patch(codey_response, target_abs):
    """Extrai e aplica o patch SEARCH/REPLACE do Codey. Retorna True se aplicou."""
    search_block = re.search(r"SEARCH:\n(.*?)\nREPLACE:", codey_response, re.DOTALL)
    replace_block = re.search(r"REPLACE:\n(.*?)$", codey_response, re.DOTALL)
    if search_block and replace_block:
        old_str = search_block.group(1).strip().replace("```python", "").replace("```", "").strip()
        new_str = replace_block.group(1).strip().replace("```python", "").replace("```", "").strip()
        result = apply_edit(target_abs, old_str, new_str)
        print(f"[CODEY] {result}")
        return "SUCCESS" in result.upper() or "applied" in result.lower()
    return False

def clone_and_checkout(repo_full_name, commit_id):
    """Clona o repositório e faz checkout no commit da issue."""
    repo_name = repo_full_name.split("/")[-1]
    local_path = os.path.abspath(os.path.join(REPOS_DIR, repo_name))
    if not os.path.exists(REPOS_DIR): os.makedirs(REPOS_DIR)
    if not os.path.exists(local_path):
        subprocess.run(["git", "clone", f"https://github.com/{repo_full_name}.git", local_path], check=True)
    subprocess.run(["git", "-C", local_path, "reset", "--hard", "HEAD"], check=True)
    try:
        subprocess.run(["git", "-C", local_path, "clean", "-fdx"], check=True)
    except:
        uid, gid = os.getuid(), os.getgid()
        subprocess.run(["docker", "run", "--rm", "-v", f"{local_path}:/app", "alpine", "chown", "-R", f"{uid}:{gid}", "/app"], check=True)
        subprocess.run(["git", "-C", local_path, "clean", "-fdx"], check=True)
    subprocess.run(["git", "-C", local_path, "checkout", commit_id], check=True)
    return local_path

def run_swe_benchmark_loop(issue_data):
    """Loop de Reparação Científica LIARA v3.4.0 (Retry + Smart Context)."""
    instance_id = issue_data['instance_id']
    repo_name = issue_data['repo']
    base_commit = issue_data['base_commit']
    test_script = issue_data['test']
    test_patch = issue_data['test_patch']

    print(f"\n[LIARA] Iniciando Reparo Científico: {instance_id}")

    try:
        repo_path = clone_and_checkout(repo_name, base_commit)
        patch_path = os.path.join(REPOS_DIR, f"{instance_id}.patch")
        with open(patch_path, "w") as f: f.write(test_patch)
        subprocess.run(["git", "-C", repo_path, "apply", os.path.abspath(patch_path)], check=True)

        container_name = f"liara-{instance_id.replace('__', '-').replace('.', '-')}"
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        subprocess.run(["docker", "run", "-d", "--name", container_name, "-v", f"{repo_path}:/app", "-w", "/app",
                        "python:3.9-slim", "tail", "-f", "/dev/null"], check=True)
        run_in_docker(container_name, "pip install -e .")
    except Exception as e:
        print(f"[ERRO] {e}"); return False

    # === FASE 1: Reprodução do Bug ===
    pre_results = run_in_docker(container_name, test_script)
    bug_detected = any(k in pre_results.lower() for k in ['fail', 'error', 'traceback'])
    print(f"[REPRO] {'BUG DETECTADO (OK)' if bug_detected else 'PASSOU (INESPERADO)'}")

    # === FASE 2: Sully — Identificação do Arquivo e Função ===
    file_list = run_in_docker(container_name, "find . -maxdepth 2 -not -path '*/.*'")
    architect_plan = prompt_agent(
        "You are Sully. Analyze this bug. Output ONLY:\n1) FILE: <relative/path/to/file.py>\n2) FUNCTION: <function_name_to_edit>",
        f"Bug: {issue_data['problem_statement'][:2000]}\n\nTest output:\n{extract_test_failure(pre_results)}\n\nFiles available:\n{file_list}"
    )

    file_match = (
        re.search(r"`([^`]*\.py)`", architect_plan) or
        re.search(r"\*\*([^*]*\.py)\*\*", architect_plan) or
        re.search(r"'([^']*\.py)'", architect_plan) or
        re.search(r"\b([a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-\.]+)+\.py)\b", architect_plan) or
        re.search(r"([a-zA-Z0-9_\-\.\/]+\.py)", architect_plan)
    )
    if not file_match:
        print("[AVISO] Sully não identificou o arquivo. Resposta:")
        print(architect_plan[:500])
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    target_rel = file_match.group(1)
    for prefix in ["/app/", "./"]:
        if target_rel.startswith(prefix):
            target_rel = target_rel[len(prefix):]

    func_match = re.search(r"FUNCTION:\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?", architect_plan, re.IGNORECASE)
    function_name = func_match.group(1) if func_match else None

    target_abs = os.path.join(repo_path, target_rel)
    print(f"[CODEY] Arquivo alvo: {target_rel} | Função: {function_name}")
    current_content = read_file(target_abs)
    if current_content.startswith("ERROR:"):
        print(f"[CODEY] {current_content}")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    code_context = extract_function_context(current_content, function_name)

    # === FASE 3: Loop Codey + Vera (com retry guiado) ===
    codey_prompt = """You are Codey, a code editor. Your ONLY job is to output a SEARCH/REPLACE block.
Do NOT explain. ONLY output the block.

EXACT FORMAT:
SEARCH:
<exact existing code lines to replace>
REPLACE:
<new code lines>"""

    previous_error = ""
    for attempt in range(1, MAX_RETRIES + 2):  # +2 para ter pelo menos 1 tentativa + N retries
        if attempt == 1:
            user_msg = f"File: {target_rel}\n\nSully's Plan:\n{architect_plan}\n\nCode section:\n{code_context}"
        else:
            # Vera guia Codey com o erro específico — mais eficiente que remandar o arquivo inteiro
            user_msg = f"File: {target_rel}\n\nYour previous fix FAILED. Test error:\n{previous_error}\n\nOriginal plan:\n{architect_plan}\n\nCode section:\n{code_context}\n\nTry a DIFFERENT approach."

        print(f"[CODEY] Tentativa {attempt}/{MAX_RETRIES + 1}...")

        # Restaura o arquivo original antes de cada tentativa (exceto a primeira)
        if attempt > 1:
            subprocess.run(["git", "-C", repo_path, "checkout", "--", target_rel], check=False)
            current_content = read_file(target_abs)
            code_context = extract_function_context(current_content, function_name)

        codey_response = prompt_agent(codey_prompt, user_msg)
        patch_applied = apply_codey_patch(codey_response, target_abs)

        if not patch_applied:
            print(f"[AVISO] Codey falhou no formato SEARCH/REPLACE na tentativa {attempt}.")
            previous_error = "Patch format invalid."
            continue

        # Testa no Docker após cada tentativa
        post_results = run_in_docker(container_name, test_script)
        failure_keywords = ['failed', 'error', 'traceback', 'exception']
        passed = not any(k in post_results.lower() for k in failure_keywords)
        log_dialogue(f"VERA tentativa {attempt}", f"PASSED={passed}\n{post_results[:500]}")

        if passed:
            print(f"-> [ORDEM] {instance_id} RESOLVIDA na tentativa {attempt}! 🎉")
            os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
            return True
        else:
            previous_error = extract_test_failure(post_results)
            print(f"[VERA] Tentativa {attempt} falhou. {'Próxima tentativa...' if attempt <= MAX_RETRIES else 'Esgotadas.'}")

    os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
    print(f"-> [ORDEM] {instance_id} REJEITADA após {MAX_RETRIES + 1} tentativas.")
    return False

if __name__ == "__main__":
    sample_file = os.environ.get("LIARA_SAMPLE", "data/swebench_sample_5.json")
    with open(sample_file, "r") as f: issues = json.load(f)
    print(f"=== LIARA: SCIENTIFIC REPAIR v3.4.0 (Retry + Smart Context) ===")
    print(f"Modelo: {MODEL} | Retries: {MAX_RETRIES} | Issues: {len(issues)}")
    res = {"sucesso": 0, "falha": 0}
    for issue in issues:
        if run_swe_benchmark_loop(issue): res["sucesso"] += 1
        else: res["falha"] += 1
        print("-" * 60)
    total = res["sucesso"] + res["falha"]
    pct = (res["sucesso"] / total * 100) if total > 0 else 0
    print(f"\n[RESULTADO] Sucesso: {res['sucesso']}/{total} ({pct:.1f}%) | Falha: {res['falha']}/{total}")
    print(f"[FIM] Logs em: {LOG_FILE}")

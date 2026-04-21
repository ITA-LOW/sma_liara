import json
import urllib.request
import urllib.error
import os
import subprocess
import re
import ast as python_ast
from datetime import datetime

# Import de Skills Reais do LIARA
try:
    from skills.file_editor.real_editor import read_file, apply_edit, write_file
    from skills.bash_executor.docker_qa import run_in_docker
except ImportError:
    print("[AVISO] Skills reais não encontradas.")

# ====================== CONFIG ======================
OLLAMA_URL = "http://localhost:11434/api/chat"
EMBED_URL  = "http://localhost:11434/api/embeddings"
MODEL      = os.environ.get("LIARA_MODEL", "llama3.1")
REPOS_DIR  = "repos"
MAX_RETRIES = int(os.environ.get("LIARA_RETRIES", "2"))
os.makedirs("data", exist_ok=True)
LOG_FILE = f"data/agent_dialogue_{datetime.now().strftime('%m%d_%H%M')}.txt"

# LIARA v4.1: Versão atual
VERSION = "4.1.0"

# Heurísticas determinísticas: padrão de erro → dica de reparo
ERROR_PATTERNS = [
    (r'IndexError',               'Check list/array index bounds and loop ranges'),
    (r'AttributeError.*None',     'Add None check before accessing attribute'),
    (r'KeyError',                 'Verify dict key existence with .get() or key-in-dict check'),
    (r'TypeError.*argument',      'Check function argument count and types'),
    (r'TypeError.*NoneType',      'A function is returning None unexpectedly — check return statements'),
    (r'ValueError',               'Check input validation and type conversion logic'),
    (r'RecursionError',           'Check base case in recursive function'),
    (r'StopIteration',            'Check iterator exhaustion handling'),
    (r'ZeroDivisionError',        'Add zero-check before division operation'),
    (r'ImportError|ModuleNotFound','Check module name and import path'),
    (r'AssertionError',           'Check the assertion condition and surrounding logic'),
    (r'NameError',                'Check variable is defined before use'),
]

# ====================== LOGGING ======================
def log_dialogue(role, content):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n[{role}] {datetime.now()}\n{content}\n")

# ====================== LLM INTERACTION ======================
def prompt_agent(role_prompt, user_content):
    """Interação com o Ollama local."""
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": role_prompt},
            {"role": "user",   "content": user_content}
        ],
        "stream": False
    }
    req = urllib.request.Request(
        OLLAMA_URL, json.dumps(data).encode('utf-8'),
        {'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            result  = json.loads(response.read().decode())
            content = result['message']['content']
            log_dialogue(f"SYSTEM: {role_prompt}", user_content)
            log_dialogue("AGENT RESPONSE", content)
            return content
    except Exception as e:
        return f"ERROR: {e}"

def get_embedding(text, model="nomic-embed-text"):
    """Obtém embedding local via Ollama. Retorna None se modelo não disponível."""
    data = {"model": model, "prompt": text[:4000]}
    req  = urllib.request.Request(
        EMBED_URL, json.dumps(data).encode('utf-8'),
        {'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())['embedding']
    except:
        return None

# ====================== PATCH APPLICATION ======================
def fuzzy_apply_edit(file_path, old_str, new_str):
    """Aplica patch com correspondência flexível de whitespace (2 passes)."""
    content = read_file(file_path)
    if content.startswith("ERROR:"):
        return content

    # Pass 1: match exato
    if old_str in content:
        return write_file(file_path, content.replace(old_str, new_str, 1))

    # Pass 2: normaliza tabs/espaços linha a linha
    def normalize(s):
        return re.sub(r'[ \t]+', ' ', s.strip())

    content_lines = content.split('\n')
    search_lines  = [normalize(l) for l in old_str.strip().split('\n')]
    n = len(search_lines)

    for i in range(len(content_lines) - n + 1):
        window = [normalize(l) for l in content_lines[i:i+n]]
        if window == search_lines:
            new_lines = new_str.split('\n')
            patched   = content_lines[:i] + new_lines + content_lines[i+n:]
            return write_file(file_path, '\n'.join(patched))

    return f"ERROR: Patch não encontrado em {file_path} (nem com fuzzy match)."

def validate_patch_syntax(file_path):
    """Valida sintaxe Python localmente (sem Docker). Retorna (ok, error_msg)."""
    if not file_path.endswith('.py'):
        return True, ""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        python_ast.parse(source)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError na linha {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def apply_codey_patch(codey_response, target_abs):
    """Extrai, aplica e pré-valida sintaticamente o patch SEARCH/REPLACE."""
    search_block = re.search(r"SEARCH:\n(.*?)\nREPLACE:", codey_response, re.DOTALL)
    replace_block = re.search(r"REPLACE:\n(.*?)$",        codey_response, re.DOTALL)
    if search_block and replace_block:
        old_str = search_block.group(1).strip().replace("```python", "").replace("```", "").strip()
        new_str = replace_block.group(1).strip().replace("```python", "").replace("```", "").strip()
        result  = fuzzy_apply_edit(target_abs, old_str, new_str)
        print(f"[CODEY] {result}")
        if "SUCCESS" not in result.upper():
            return False
        # Pré-validação estática (sem Docker — rápido)
        ok, err = validate_patch_syntax(target_abs)
        if not ok:
            print(f"[VALIDA] ✗ Sintaxe inválida — {err}. Descartando.")
            return False
        print(f"[VALIDA] ✓ Sintaxe OK")
        return True
    return False

# ====================== STATE MANAGEMENT ======================
def state_path(instance_id):
    return f"data/state_{instance_id.replace('/', '_').replace(':', '_')}.json"

def load_state(instance_id):
    p = state_path(instance_id)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"patches_tried": [], "errors": [], "sully_file": None, "sully_function": None, "resolved": False}

def save_state(instance_id, state):
    with open(state_path(instance_id), "w") as f:
        json.dump(state, f, indent=2)

# ====================== ERROR ANALYSIS ======================
def classify_error(test_output):
    """Classifica tipo de erro e retorna dica determinística para o Codey."""
    for pattern, hint in ERROR_PATTERNS:
        if re.search(pattern, test_output, re.IGNORECASE):
            return hint
    return ""

def extract_test_failure(test_output):
    """Extrai apenas as linhas de falha relevantes do output dos testes."""
    lines = test_output.split('\n')
    failure_lines, capture = [], False
    for line in lines:
        if any(k in line for k in ['FAILED', 'ERROR', 'AssertionError', 'Traceback', 'File "', '>>>']):
            capture = True
        if capture:
            failure_lines.append(line)
        if len(failure_lines) > 30:
            break
    return '\n'.join(failure_lines) if failure_lines else test_output[:800]

# ====================== AST ANALYSIS ======================
def build_ast_map(repo_path):
    """Mapeia function_name → [(arquivo_relativo, lineno)] para todos os .py do repo."""
    func_map = {}
    skip_dirs = {'.', '__pycache__', 'vendor', 'node_modules', '.git', 'dist', 'build'}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        for fname in files:
            if not fname.endswith('.py') or fname.startswith('test_'):
                continue
            fpath = os.path.join(root, fname)
            rel   = os.path.relpath(fpath, repo_path)
            if 'test' in rel.lower():
                continue
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    tree = python_ast.parse(f.read(), filename=fpath)
                for node in python_ast.walk(tree):
                    if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                        func_map.setdefault(node.name, []).append((rel, node.lineno))
            except:
                continue
    return func_map

def localize_from_traceback(test_output, func_map, repo_path):
    """Usa o traceback do teste para identificar arquivos-fonte candidatos."""
    func_names = re.findall(r'in ([a-zA-Z_][a-zA-Z0-9_]+)\s*$', test_output, re.MULTILINE)
    file_hints  = re.findall(r'File "([^"]+\.py)"', test_output)
    candidates  = []

    for fn in func_names:
        if fn in func_map:
            for (rel, _) in func_map[fn]:
                if 'test' not in rel.lower() and rel not in candidates:
                    candidates.append(rel)

    for fh in file_hints:
        rel = os.path.relpath(fh, repo_path) if os.path.isabs(fh) else fh
        if 'test' not in rel.lower() and rel not in candidates:
            candidates.append(rel)

    return candidates[:5]

def cosine_similarity(a, b):
    dot   = sum(x*y for x, y in zip(a, b))
    mag_a = sum(x**2 for x in a) ** 0.5
    mag_b = sum(x**2 for x in b) ** 0.5
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0

def find_relevant_files_by_embedding(repo_path, problem_statement, func_map, top_n=5):
    """Rank semântico de arquivos via embedding (nomic-embed-text). Opcional."""
    query_emb = get_embedding(problem_statement[:2000])
    if query_emb is None:
        return []

    scored, seen = [], set()
    for _, locations in func_map.items():
        for (rel, _) in locations:
            if rel in seen:
                continue
            seen.add(rel)
            fpath = os.path.join(repo_path, rel)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    snippet = f.read(3000)
                file_emb = get_embedding(snippet)
                if file_emb:
                    scored.append((cosine_similarity(query_emb, file_emb), rel))
            except:
                continue

    scored.sort(reverse=True)
    return [rel for _, rel in scored[:top_n]]

# ====================== CONTEXT EXTRACTION (PROGRESSIVA) ======================
def get_context_for_attempt(content, function_name, attempt):
    """Escalada progressiva de contexto: cada tentativa adiciona mais informação.
    Attempt 1 → assinatura + docstring
    Attempt 2 → corpo completo da função
    Attempt 3+ → função + contexto ao redor
    """
    lines = content.split('\n')

    if not function_name:
        sizes = [3000, 6000, 10000]
        return content[:sizes[min(attempt - 1, 2)]]

    start = None
    for i, line in enumerate(lines):
        if f'def {function_name}' in line or f'class {function_name}' in line:
            start = max(0, i - 2)
            break

    if start is None:
        sizes = [3000, 6000, 10000]
        return content[:sizes[min(attempt - 1, 2)]]

    if attempt == 1:
        end = min(len(lines), start + 20)           # só assinatura + docstring
    elif attempt == 2:
        end = min(len(lines), start + 100)          # corpo completo
    else:
        start = max(0, start - 30)                  # contexto ao redor
        end   = min(len(lines), start + 230)

    return '\n'.join(lines[start:end])

def synthesize_repro_test(problem_statement):
    """Extrai script mínimo de reprodução do bug report (sem LLM)."""
    code_blocks = re.findall(r'```python\n(.*?)```', problem_statement, re.DOTALL)
    if code_blocks:
        return code_blocks[0][:2000]
    doctest = re.findall(r'>>>\s+(.+)', problem_statement)
    if doctest:
        return '\n'.join(doctest[:10])
    return None

# ====================== GIT/DOCKER SETUP ======================
def clone_and_checkout(repo_full_name, commit_id):
    repo_name  = repo_full_name.split("/")[-1]
    local_path = os.path.abspath(os.path.join(REPOS_DIR, repo_name))
    if not os.path.exists(REPOS_DIR):
        os.makedirs(REPOS_DIR)
    if not os.path.exists(local_path):
        subprocess.run(["git", "clone", f"https://github.com/{repo_full_name}.git", local_path], check=True)
    subprocess.run(["git", "-C", local_path, "reset", "--hard", "HEAD"], check=True)
    try:
        subprocess.run(["git", "-C", local_path, "clean", "-fdx"], check=True)
    except:
        uid, gid = os.getuid(), os.getgid()
        subprocess.run(["docker", "run", "--rm", "-v", f"{local_path}:/app",
                        "alpine", "chown", "-R", f"{uid}:{gid}", "/app"], check=True)
        subprocess.run(["git", "-C", local_path, "clean", "-fdx"], check=True)
    subprocess.run(["git", "-C", local_path, "checkout", commit_id], check=True)
    return local_path

# ====================== MAIN REPAIR LOOP ======================
def run_swe_benchmark_loop(issue_data):
    """Loop de Reparação Científica LIARA v4.0 (Hybrid Intelligence)."""
    instance_id = issue_data['instance_id']
    repo_name   = issue_data['repo']
    base_commit = issue_data['base_commit']
    test_script = issue_data['test']
    test_patch  = issue_data['test_patch']

    print(f"\n[LIARA v4.0] {instance_id}")
    state = load_state(instance_id)

    # --- Setup ---
    try:
        repo_path   = clone_and_checkout(repo_name, base_commit)
        patch_path  = os.path.join(REPOS_DIR, f"{instance_id}.patch")
        with open(patch_path, "w") as f:
            f.write(test_patch)
        subprocess.run(["git", "-C", repo_path, "apply", os.path.abspath(patch_path)], check=True)

        container_name = f"liara-{instance_id.replace('__', '-').replace('.', '-')}"
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        subprocess.run(["docker", "run", "-d", "--name", container_name,
                        "-v", f"{repo_path}:/app", "-w", "/app",
                        "python:3.9-slim", "tail", "-f", "/dev/null"], check=True)
        # LIARA v4.1: Instalação robusta de dependências
        print("[SETUP] Instalando dependências de projeto e teste...")
        run_in_docker(container_name, "pip install -e . -q")
        run_in_docker(container_name, "pip install pytest pytest-django pytest-mock tox -q")
    except Exception as e:
        print(f"[ERRO] {e}")
        return False

    # === FASE 0: Análise AST local (ANTES de qualquer LLM) ===
    print("[AST] Mapeando repositório...")
    func_map = build_ast_map(repo_path)
    print(f"[AST] {len(func_map)} funções mapeadas")

    # === FASE 1: Reprodução do Bug ===
    pre_results  = run_in_docker(container_name, test_script)
    bug_detected = any(k in pre_results.lower() for k in ['fail', 'error', 'traceback'])
    print(f"[REPRO] {'BUG DETECTADO ✓' if bug_detected else 'PASSOU (inesperado)'}")

    # Análise determinística do erro
    error_hint = classify_error(pre_results)
    if error_hint:
        print(f"[PATTERN] {error_hint}")

    # Localização via traceback (AST-based)
    ast_candidates = localize_from_traceback(pre_results, func_map, repo_path)
    if ast_candidates:
        print(f"[AST] Candidatos: {ast_candidates}")

    # Localização semântica via embedding (opcional, requer nomic-embed-text)
    emb_candidates = find_relevant_files_by_embedding(repo_path, issue_data['problem_statement'], func_map)
    if emb_candidates:
        print(f"[EMB] Candidatos semânticos: {emb_candidates}")

    # Síntese de teste de reprodução
    repro_script = synthesize_repro_test(issue_data['problem_statement'])
    if repro_script:
        print(f"[REPRO] Script de reprodução extraído do bug report ✓")

    # Combina candidatos (traceback first, embedding second)
    all_candidates = list(dict.fromkeys(ast_candidates + emb_candidates))

    # === FASE 2: Sully — Identificação do Arquivo e Função ===
    # LIARA v4.1: Redução drástica de ruído no contexto do Sully
    if all_candidates:
        file_context = "Top relevant files identified by static analysis:\n" + "\n".join(all_candidates[:15])
    else:
        # Fallback para find limitado se AST falhar
        file_context = "Files in repository:\n" + run_in_docker(container_name, "find . -maxdepth 3 -name '*.py' | head -n 50")

    sully_context = (
        f"Bug Report: {issue_data['problem_statement'][:2500]}\n\n"
        f"Test Failure Traceback:\n{extract_test_failure(pre_results)}"
    )
    if error_hint:
        sully_context += f"\n\nAnalyzed Bug Pattern: {error_hint}"
    if repro_script:
        sully_context += f"\n\nReproduction script extracted:\n{repro_script[:500]}"
    
    sully_context += f"\n\n{file_context}"

    # LIARA v4.1: STRICT JSON MODE
    sully_prompt = """You are Sully, a software architect. Analyze the bug and output ONLY a JSON object.
Do NOT explain. Do NOT chatter.

FORMAT:
{
  "file": "relative/path/to/file.py",
  "function": "function_name"
}

RULES:
- Preferred files for fix: the ones listed in 'relevant files'
- NEVER target test files
- The file MUST exist in the provided list."""

    architect_plan = "{}"
    for _ in range(2): # Retry parsing if model is chatty
        raw_res = prompt_agent(sully_prompt, sully_context)
        try:
            # Tenta limpar lixo antes/depois do JSON
            json_match = re.search(r'(\{.*?\})', raw_res, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group(1))
                target_rel = plan_data.get("file")
                function_name = plan_data.get("function")
                if target_rel:
                    architect_plan = raw_res
                    break
        except:
            continue
    
    if not target_rel:
        print("[ERRO] Sully falhou em fornecer um JSON válido.")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    state["sully_response"] = architect_plan

    file_match = (
        re.search(r"`([^`]*\.py)`",                                    architect_plan) or
        re.search(r"\*\*([^*]*\.py)\*\*",                             architect_plan) or
        re.search(r"'([^']*\.py)'",                                    architect_plan) or
        re.search(r"\b([a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-\.]+)+\.py)\b", architect_plan) or
        re.search(r"([a-zA-Z0-9_\-\./]+\.py)",                        architect_plan)
    )
    if not file_match:
        print("[AVISO] Sully não identificou o arquivo.")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    target_rel = file_match.group(1)
    for prefix in ["/app/", "./"]:
        if target_rel.startswith(prefix):
            target_rel = target_rel[len(prefix):]

    func_match    = re.search(r"FUNCTION:\s*`?([a-zA-Z_][a-zA-Z0-9_]*)`?", architect_plan, re.IGNORECASE)
    function_name = func_match.group(1) if func_match else None

    target_abs = os.path.join(repo_path, target_rel)
    print(f"[SULLY] Arquivo: {target_rel} | Função: {function_name}")

    state["sully_file"]     = target_rel
    state["sully_function"] = function_name
    save_state(instance_id, state)

    current_content = read_file(target_abs)
    if current_content.startswith("ERROR:"):
        print(f"[CODEY] {current_content}")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    # === FASE 3: Loop Codey + Vera (escalada progressiva de contexto) ===
    # LIARA v4.1: FEW-SHOT PROMPTING
    codey_prompt = """You are Codey, a code editor. Your ONLY job is to output a SEARCH/REPLACE block.
Do NOT explain. 

EXAMPLE:
SEARCH:
def old_func():
    return True
REPLACE:
def old_func():
    return False

EXACT FORMAT:
SEARCH:
<exact code lines>
REPLACE:
<new code lines>"""

    previous_error = ""
    for attempt in range(1, MAX_RETRIES + 2):
        # Escalada progressiva: mais contexto a cada tentativa
        code_context = get_context_for_attempt(current_content, function_name, attempt)

        if attempt == 1:
            user_msg = (
                f"File: {target_rel}\n\nSully's Plan:\n{architect_plan}\n\n"
                f"Code section (signature):\n{code_context}"
            )
        else:
            user_msg = (
                f"File: {target_rel}\n\nPrevious fix FAILED. Test error:\n{previous_error}\n\n"
                f"Original plan:\n{architect_plan}\n\n"
                f"Code section (expanded level {attempt}):\n{code_context}\n\nTry a DIFFERENT approach."
            )

        if error_hint:
            user_msg += f"\n\nHint: {error_hint}"

        print(f"[CODEY] Tentativa {attempt}/{MAX_RETRIES + 1} — contexto nível {attempt}...")

        # Restaura arquivo antes de cada retry
        if attempt > 1:
            subprocess.run(["git", "-C", repo_path, "checkout", "--", target_rel], check=False)
            current_content = read_file(target_abs)

        codey_response = prompt_agent(codey_prompt, user_msg)
        patch_applied  = apply_codey_patch(codey_response, target_abs)

        if not patch_applied:
            previous_error = "Patch format invalid or syntax error."
            state["errors"].append({"attempt": attempt, "error": previous_error})
            save_state(instance_id, state)
            continue

        # Testa no Docker
        post_results = run_in_docker(container_name, test_script)
        passed = not any(k in post_results.lower() for k in ['failed', 'error', 'traceback', 'exception'])
        log_dialogue(f"VERA tentativa {attempt}", f"PASSED={passed}\n{post_results[:500]}")

        if passed:
            print(f"-> [ORDEM] {instance_id} RESOLVIDA na tentativa {attempt}! 🎉")
            state["resolved"] = True
            state["attempts"] = attempt
            save_state(instance_id, state)
            os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
            return True
        else:
            previous_error = extract_test_failure(post_results)
            state["errors"].append({"attempt": attempt, "error": previous_error[:300]})
            save_state(instance_id, state)
            print(f"[VERA] Tentativa {attempt} falhou. {'Próxima...' if attempt <= MAX_RETRIES else 'Esgotadas.'}")

    os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
    print(f"-> [ORDEM] {instance_id} REJEITADA após {MAX_RETRIES + 1} tentativas.")
    return False

# ====================== ENTRY POINT ======================
if __name__ == "__main__":
    sample_file = os.environ.get("LIARA_SAMPLE", "data/swebench_sample_5.json")
    with open(sample_file, "r") as f:
        issues = json.load(f)
    print(f"=== LIARA: SCIENTIFIC REPAIR v{VERSION} (Hybrid Intelligence) ===")
    print(f"Modelo: {MODEL} | Retries: {MAX_RETRIES} | Issues: {len(issues)}")
    res = {"sucesso": 0, "falha": 0}
    for issue in issues:
        if run_swe_benchmark_loop(issue):
            res["sucesso"] += 1
        else:
            res["falha"] += 1
        print("-" * 60)
    total = res["sucesso"] + res["falha"]
    pct   = (res["sucesso"] / total * 100) if total > 0 else 0
    print(f"\n[RESULTADO] Sucesso: {res['sucesso']}/{total} ({pct:.1f}%) | Falha: {res['falha']}/{total}")
    print(f"[FIM] Logs em: {LOG_FILE}")

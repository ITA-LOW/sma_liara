import json
import urllib.request
import urllib.error
import os
import subprocess
import re
import ast as python_ast
from datetime import datetime

# Import de Skills Reais do LIARA
from skills.file_editor.real_editor import read_file, apply_edit, write_file
from skills.bash_executor.docker_qa import run_in_docker

# ====================== CONFIG ======================
OLLAMA_URL = "http://localhost:11434/api/chat"
EMBED_URL  = "http://localhost:11434/api/embeddings"
MODEL      = os.environ.get("LIARA_MODEL", "llama3.1")
REPOS_DIR  = "repos"
MAX_RETRIES = int(os.environ.get("LIARA_RETRIES", "2"))
MAX_FUNC_CONTEXT_LINES = int(os.environ.get("LIARA_MAX_FUNC_LINES", "420"))
os.makedirs("data", exist_ok=True)
LOG_FILE = f"data/agent_dialogue_{datetime.now().strftime('%m%d_%H%M')}.txt"

# LIARA v4.4.1 — núcleo benchmark-agnóstico: localização híbrida + contexto AST + patch + testes.
# Extensões por domínio: prefira acrescentar entradas em ERROR_PATTERNS / EXPERT_HINTS (dados),
# ou variáveis de ambiente, em vez de lógica ad-hoc no loop principal.
VERSION = "4.4.3"

# Prefixo estável no prompt: detecta modo de contexto sem acoplar a texto natural de um benchmark.
AST_CONTEXT_MARKER = "# LIARA:AST_FUNCTION_SCOPE\n"

# Tabela genérica: saída de teste / traceback → dica curta (qualquer benchmark que exponha o mesmo texto).
ERROR_PATTERNS = [
    (r'IndexError',               'Check list/array index bounds and loop ranges'),
    (r'AttributeError.*None',     'Add None check before accessing attribute'),
    (r'KeyError',                 'Verify dict key existence with .get() or key-in-dict check'),
    (r'AssertionError',           'Compare expected vs actual; fix edge case or off-by-one'),
    (r'TypeError',                'Check operand types, None where an object is required, or wrong arity'),
    (r'ValueError',               'Validate inputs, ranges, and argument combinations'),
    (r'RecursionError',           'Add a base case or replace deep recursion with iteration'),
    (r'UnboundLocalError',        'Ensure the variable is assigned on every execution path before it is read'),
]

# Dicas um pouco mais ricas por tipo de exceção (genéricas; não cite um único repositório ou bug).
EXPERT_HINTS = {
    "IndexError": "EXPERT TIP: Re-check index bounds and sequence length at the failing line; if the sequence changes size inside a loop, indices computed earlier may become invalid.",
    "AttributeError": "EXPERT TIP: Ensure the object is not None before access. Use: 'if obj is not None:'",
    "TypeError": "EXPERT TIP: Check if you are trying to iterate over a None value or if a function is missing a 'return' statement.",
    "AssertionError": "EXPERT TIP: Reproduce the minimal failing assertion; check boundary conditions and type coercion.",
    "ValueError": "EXPERT TIP: Trace which argument triggers the error; validate preconditions before the failing call.",
    "UnboundLocalError": "EXPERT TIP: A name is read before assignment on some paths; check branching/loops and that every path defines the variable before use.",
}

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
        "stream": False,
    }
    opts = {}
    if os.environ.get("LIARA_NUM_PREDICT"):
        opts["num_predict"] = int(os.environ["LIARA_NUM_PREDICT"])
    if os.environ.get("LIARA_NUM_CTX"):
        opts["num_ctx"] = int(os.environ["LIARA_NUM_CTX"])
    if opts:
        data["options"] = opts
    req = urllib.request.Request(
        OLLAMA_URL, json.dumps(data).encode('utf-8'),
        {'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        result  = json.loads(response.read().decode())
        content = result['message']['content']
        log_dialogue(f"SYSTEM: {role_prompt}", user_content)
        log_dialogue("AGENT RESPONSE", content)
        return content

def get_embedding(text, model="nomic-embed-text"):
    """Obtém embedding local via Ollama (falhas de rede/API propagam)."""
    data = {"model": model, "prompt": text[:4000]}
    req  = urllib.request.Request(
        EMBED_URL, json.dumps(data).encode('utf-8'),
        {'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())['embedding']


def extract_first_json_object(text):
    """Primeiro objeto JSON bem formado no texto (raw_decode); falha com JSONDecodeError se inválido."""
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    return json.JSONDecoder().raw_decode(text, start)[0]

# ====================== PATCH APPLICATION ======================
def fuzzy_apply_edit(file_path, old_str, new_str):
    """Aplica SEARCH/REPLACE: substituição literal se possível; senão casamento por conteúdo + indentação.

    Exige que cada linha não vazia do SEARCH tenha a mesma indentação (nº de espaços à esquerda)
    que a linha correspondente no arquivo — evita casar o mesmo texto em outro nível do AST.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def get_indent(line):
        return len(line) - len(line.lstrip())

    if old_str in content:
        new_content = content.replace(old_str, new_str, 1)
        return write_file(file_path, new_content)

    content_lines = content.split('\n')
    search_lines  = old_str.split('\n')
    clean_search  = [ln.strip() for ln in search_lines if ln.strip()]
    nonblank_tpl  = [ln for ln in search_lines if ln.strip()]
    n_search      = len(clean_search)

    if not clean_search:
        return "ERROR: Bloco SEARCH vazio."

    for i in range(len(content_lines)):
        if content_lines[i].strip() != clean_search[0]:
            continue

        matched_idx, match_count, k, lines_to_replace = [], 0, i, 0
        ok = True
        while k < len(content_lines) and match_count < n_search:
            if content_lines[k].strip():
                if content_lines[k].strip() == clean_search[match_count]:
                    matched_idx.append(k)
                    match_count += 1
                else:
                    ok = False
                    break
            k += 1
            lines_to_replace += 1

        if not ok or match_count != n_search:
            continue

        if len(matched_idx) != len(nonblank_tpl):
            continue
        if any(get_indent(content_lines[fk]) != get_indent(tpl) for fk, tpl in zip(matched_idx, nonblank_tpl)):
            continue

        orig_anchor_indent = get_indent(content_lines[i])
        new_split = new_str.split('\n')
        model_anchor_indent = 0
        for nl in new_split:
            if nl.strip():
                model_anchor_indent = get_indent(nl)
                break

        final_lines = []
        for nl in new_split:
            if not nl.strip():
                final_lines.append("")
                continue
            drift = get_indent(nl) - model_anchor_indent
            final_lines.append(" " * (orig_anchor_indent + drift) + nl.lstrip())

        patched = content_lines[:i] + final_lines + content_lines[i + lines_to_replace :]
        return write_file(file_path, "\n".join(patched))

    return "ERROR: Patch não encontrado (strip+indent ou substring exata)."

def validate_patch_syntax(file_path):
    """Valida sintaxe Python localmente (sem Docker). Retorna (ok, error_msg)."""
    if not file_path.endswith('.py'):
        return True, ""
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        python_ast.parse(source)
    except SyntaxError as e:
        return False, f"{e.msg} (line {e.lineno})"
    return True, ""


def sanitize_patch_block(raw):
    """Remove cercas ``` e linhas vazias só no início/fim do bloco; preserva indentação do código."""
    s = raw.replace("```python", "").replace("```", "").replace("\r\n", "\n")
    lines = s.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def apply_codey_patch(codey_response, target_abs):
    """Extrai, aplica e pré-valida sintaticamente o patch SEARCH/REPLACE (v4.3.4)."""
    # Scalpel: Isolar apenas o conteúdo real entre as tags, ignorando duplicatas
    parts = re.split(r"SEARCH:|REPLACE:", codey_response)
    if len(parts) < 3:
        return False, "SEARCH/REPLACE block not found or malformed."

    # O conteúdo do SEARCH está entre a 1ª e 2ª tag, o REPLACE depois da 2ª
    old_str = sanitize_patch_block(parts[1])
    # O REPLACE pode ter lixo depois se o modelo continuou falando, pegamos apenas até o próximo bloco ou fim
    new_str = sanitize_patch_block(parts[2].split("SEARCH:")[0].split("REPLACE:")[0])

    result  = fuzzy_apply_edit(target_abs, old_str, new_str)
    print(f"[CODEY] {result}")
    if "SUCCESS" not in result.upper():
        return False, result

    ok, err = validate_patch_syntax(target_abs)
    if not ok:
        print(f"[VALIDA] ✗ Sintaxe inválida — {err}. Descartando e resetando.")
        # Auto-Rollback v4.3.5
        repo_parts = target_abs.split("/repos/")
        if len(repo_parts) > 1:
            repo_path = repo_parts[0] + "/repos/" + repo_parts[1].split("/")[0]
            rollback_file(repo_path, target_abs)
        return False, err
    print(f"[VALIDA] ✓ Sintaxe OK")
    return True, ""

def rollback_file(repo_path, file_abs):
    """Reseta o arquivo para o estado original estável (v4.3.5)."""
    file_rel = os.path.relpath(file_abs, repo_path)
    subprocess.run(["git", "-C", repo_path, "checkout", file_rel], check=True, capture_output=True)
    print(f"[RE-SET] Arquivo {file_rel} resetado para o estado estável.")
    return True

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


def resolve_innermost_function_at_line(content, line_1based):
    """Menor def/async que contém a linha 1-based (local típico da exceção no traceback)."""
    if line_1based is None or not (content or "").strip():
        return None
    try:
        tree = python_ast.parse(content)
    except SyntaxError:
        return None
    best = None  # (span, name)
    for node in python_ast.walk(tree):
        if not isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        lo, hi = node.lineno, end
        if lo <= line_1based <= hi:
            span = hi - lo
            if best is None or span < best[0]:
                best = (span, node.name)
    return best[1] if best else None


def extract_ast_function_scope(content, function_name, line_hint_1based=None, max_lines=None):
    """Extrai o trecho de arquivo da função `function_name` usando lineno/end_lineno do AST.

    Prioriza o menor escopo AST que contém line_hint (ex.: método vs função externa homônima).
    Retorna None se o arquivo não parseia, a função não existe, ou line_hint está fora desse def.
    """
    if max_lines is None:
        max_lines = MAX_FUNC_CONTEXT_LINES
    if not function_name or not content.strip():
        return None
    try:
        tree = python_ast.parse(content)
    except SyntaxError:
        return None
    file_lines = content.splitlines()
    candidates = []
    for node in python_ast.walk(tree):
        if not isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
            continue
        if node.name != function_name:
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        candidates.append((node.lineno, end))

    if not candidates:
        return None

    if line_hint_1based is not None:
        inside = [c for c in candidates if c[0] <= line_hint_1based <= c[1]]
        if inside:
            lo, hi = min(inside, key=lambda lh: lh[1] - lh[0])
        else:
            # Não escolher "função mais próxima": isso puxa contexto errado (ex.: caller vs callee).
            return None
    else:
        lo, hi = min(candidates, key=lambda lh: lh[1] - lh[0])

    segment = file_lines[lo - 1 : hi]
    if len(segment) > max_lines:
        if line_hint_1based is not None:
            mid0 = line_hint_1based - 1
            half = max_lines // 2
            a = max(lo - 1, mid0 - half)
            b = min(hi, a + max_lines)
            a = max(lo - 1, b - max_lines)
            segment = file_lines[a:b]
        else:
            segment = segment[:max_lines]

    return "\n".join(segment)

def extract_test_failure(test_output, max_lines=72):
    """Extrai trecho útil da falha (traceback Python tem prioridade sobre ruído do runner)."""
    if not test_output:
        return ""
    marker = "Traceback (most recent call last):"
    idx = test_output.find(marker)
    if idx >= 0:
        chunk = test_output[idx:]
        lines = chunk.split("\n")
        return "\n".join(lines[:max_lines])
    lines = test_output.split("\n")
    failure_lines, capture = [], False
    triggers = (
        "FAILED",
        "AssertionError",
        "Traceback",
        'File "',
        ">>>",
        "[FAIL]",
        "E   ",
        "Error:",
    )
    for line in lines:
        if any(k in line for k in triggers):
            capture = True
        if capture:
            failure_lines.append(line)
        if len(failure_lines) >= max_lines:
            break
    return "\n".join(failure_lines) if failure_lines else test_output[:2000]

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
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                tree = python_ast.parse(f.read(), filename=fpath)
            for node in python_ast.walk(tree):
                if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                    func_map.setdefault(node.name, []).append((rel, node.lineno))
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
        # LIARA v4.2.3: Limpeza de caminhos de traceback (Docker -> Host)
        clean_fh = fh
        for prefix in ["/app/", "app/"]:
            if clean_fh.startswith(prefix):
                clean_fh = clean_fh[len(prefix):]
                break
        
        rel = clean_fh if not os.path.isabs(clean_fh) else os.path.relpath(clean_fh, repo_path)
        
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

    scored, seen = [], set()
    for _, locations in func_map.items():
        for (rel, _) in locations:
            if rel in seen:
                continue
            seen.add(rel)
            fpath = os.path.join(repo_path, rel)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                snippet = f.read(3000)
            file_emb = get_embedding(snippet)
            if file_emb:
                scored.append((cosine_similarity(query_emb, file_emb), rel))

    scored.sort(reverse=True)
    return [rel for _, rel in scored[:top_n]]

# ====================== CONTEXT EXTRACTION (PROGRESSIVA) ======================
def get_context_for_attempt(content, function_name, line_hint, attempt):
    """Contexto para o Codey: preferência pelo corpo completo da função (AST), senão janela deslizante."""
    # v4.4.0: escopo completo da função alvo → SEARCH não corta no meio de if/for
    if function_name:
        ast_block = extract_ast_function_scope(content, function_name, line_hint, MAX_FUNC_CONTEXT_LINES)
        if ast_block:
            nlines = ast_block.count("\n") + 1
            print(f"[CTX] AST function `{function_name}` ({nlines} lines, cap {MAX_FUNC_CONTEXT_LINES})")
            note = (
                f"# Function `{function_name}` — SEARCH must match below with IDENTICAL leading whitespace.\n\n"
            )
            return AST_CONTEXT_MARKER + note + ast_block

    lines = content.split('\n')

    start = None
    if line_hint is not None:
        start = max(0, line_hint - 1)

    if function_name and start is None:
        for i, line in enumerate(lines):
            if f'def {function_name}' in line or f'class {function_name}' in line:
                start = i
                break

    if start is None:
        return content[:3000]

    if line_hint is not None:
        win_size = [56, 88, 120][min(attempt - 1, 2)]
    else:
        win_size = [24, 56, 88][min(attempt - 1, 2)]

    s_idx = max(0, start - (win_size // 2))
    e_idx = min(len(lines), start + (win_size // 2))

    return "\n".join(lines[s_idx:e_idx])

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
    
    # LIARA v4.2.1: Proativamente corrige permissões antes do clean
    # Isso evita o erro de "Permissão negada" em arquivos criados pelo Docker
    uid, gid = os.getuid(), os.getgid()
    subprocess.run(["docker", "run", "--rm", "-v", f"{local_path}:/app",
                    "alpine", "chown", "-R", f"{uid}:{gid}", "/app"], check=True)
    
    subprocess.run(["git", "-C", local_path, "reset", "--hard", "HEAD"], check=True)
    subprocess.run(["git", "-C", local_path, "clean", "-fdx"], check=True)
    subprocess.run(["git", "-C", local_path, "checkout", commit_id], check=True)
    return local_path

# ====================== MAIN REPAIR LOOP ======================
def run_swe_benchmark_loop(issue_data):
    """Loop de reparação LIARA: localização híbrida + escopo AST + Codey/Vera (testes reais)."""
    instance_id = issue_data['instance_id']
    repo_name   = issue_data['repo']
    base_commit = issue_data['base_commit']
    test_script = issue_data['test']
    test_patch  = issue_data['test_patch']

    print(f"\n[LIARA v{VERSION}] {instance_id}")
    state = load_state(instance_id)

    # --- Setup ---
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

    # === FASE 0: Análise AST local (ANTES de qualquer LLM) ===
    print("[AST] Mapeando repositório...")
    func_map = build_ast_map(repo_path)
    print(f"[AST] {len(func_map)} funções mapeadas")

    # === FASE 1: Reprodução do Bug ===
    pre_ok, pre_results = run_in_docker(container_name, test_script, return_exit_code=True)
    # Exit code do runner reflete falhas de teste; heurística leve cobre runners ruidosos
    bug_detected = (not pre_ok) or any(
        t in pre_results.lower() for t in ("failed", "traceback", "assertionerror", "errors=")
    )
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
        msg = f"[EMB] Candidatos semânticos: {emb_candidates}"
        print(msg)
        log_dialogue("HYBRID ANALYZER", msg)
    else:
        log_dialogue("HYBRID ANALYZER", "[EMB] Nenhum candidato semântico encontrado ou modelo offline.")

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

    sully_context = f"Bug Report: {issue_data['problem_statement']}\n\n"
    repro_traceback = extract_test_failure(pre_results)
    if repro_traceback:
        sully_context += f"Test Failure Traceback:\n{repro_traceback}\n\n"
    
    sully_context += f"Analyzed Bug Pattern: {error_hint}\n\n"
    sully_context += "Top relevant files identified by static analysis:\n"
    for f in ast_candidates + emb_candidates:
        sully_context += f"{f}\n"

    # LIARA v4.2.5: Injeção de dicas de funções do traceback
    func_hints = re.findall(r'in ([a-zA-Z_][a-zA-Z0-9_]+)\s*$', pre_results, re.MULTILINE)
    if func_hints:
        sully_context += "\nSuspected functions identified in traceback:\n"
        for fn in sorted(list(set(func_hints))):
            sully_context += f"- {fn}\n"

    if repro_script:
        sully_context += f"\nReproduction script extracted:\n{repro_script[:500]}"
    
    sully_context += f"\n\n{file_context}"

    # LIARA v4.1: STRICT JSON MODE
    sully_prompt = """You are Sully, a software architect. Analyze the bug and output ONLY a JSON object.
Do NOT explain. Do NOT chatter.

FORMAT:
{
  "file": "relative/path/to/file.py",
  "function": "python_function_or_method_name"
}

RULES:
- The "function" key is REQUIRED: the most specific function or method in the traceback where the bug occurs.
- ONLY output the relative path from the root of the repository.
- NEVER include prefixes like '/app/', 'app/', 'repos/' or absolute paths.
- NEVER target test files.
- The file MUST exist in the provided list."""

    architect_plan = "{}"
    plan_data = None
    target_rel = None
    function_name = None
    for _ in range(2):  # Retry se o modelo vier com texto extra ou JSON inválido
        raw_res = prompt_agent(sully_prompt, sully_context)
        plan_data = extract_first_json_object(raw_res)
        if isinstance(plan_data, dict):
            target_rel = (plan_data.get("file") or "").strip()
            function_name = plan_data.get("function")
            if target_rel:
                architect_plan = raw_res
                break
    
    if not target_rel:
        print("[ERRO] Sully falhou em fornecer um JSON válido.")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    state["sully_response"] = architect_plan

    # Limpeza de caminhos (v4.2.2 logic)
    for prefix in ["/app/", "app/", "./", "../"]:
        if target_rel.startswith(prefix):
            target_rel = target_rel[len(prefix):]
    target_rel = target_rel.lstrip("/")

    if not target_rel:
        print("[ERRO] Sully falhou em identificar o arquivo.")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    target_abs = os.path.join(repo_path, target_rel)
    if not os.path.isfile(target_abs):
        fallback_chain = list(dict.fromkeys(ast_candidates + emb_candidates))
        for cand in fallback_chain:
            if cand == target_rel:
                continue
            cand_abs = os.path.join(repo_path, cand)
            if os.path.isfile(cand_abs):
                print(f"[HYBRID] Caminho de Sully inexistente ({target_rel}); usando candidato {cand}")
                target_rel, target_abs = cand, cand_abs
                break
    if not os.path.isfile(target_abs):
        print(f"[ERRO] Arquivo alvo inexistente após fallback: {target_rel}")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    # LIARA v4.3.0: linha do traceback (última ", line N" → frame mais interno na prática)
    line_hints = re.findall(r', line (\d+)', pre_results)
    line_hint  = int(line_hints[-1]) if line_hints else None

    if not function_name and func_hints:
        function_name = func_hints[-1]
        print(f"[HYBRID] Forçando função do traceback: {function_name}")

    current_content = read_file(target_abs)
    if current_content.startswith("ERROR:"):
        print(f"[CODEY] {current_content}")
        os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
        return False

    # Linha do erro + AST prevalecem sobre o nome vindo do LLM (caller vs callee no mesmo .py).
    if line_hint is not None:
        ast_fn = resolve_innermost_function_at_line(current_content, line_hint)
        if ast_fn:
            if ast_fn != function_name:
                print(f"[HYBRID] Linha {line_hint} do traceback → AST `{ast_fn}` (Sully tinha `{function_name}`)")
            function_name = ast_fn

    print(f"[SULLY] Arquivo: {target_rel} | Função: {function_name}")

    state["sully_file"]     = target_rel
    state["sully_function"] = function_name
    save_state(instance_id, state)

    # === FASE 3: Loop Codey + Vera (escalada progressiva de contexto) ===
    # LIARA v4.1: FEW-SHOT PROMPTING
    codey_prompt = """You are Codey, a code editor. Your ONLY job is to output a SEARCH/REPLACE block.
Do NOT explain. Do NOT chatter.
Do NOT perform cosmetic cleanups or unrelated refactors.

Rules:
1. The SEARCH block MUST match the provided code EXACTLY (same leading spaces on every line as in the Code section).
2. SEARCH must cover complete statements: if you include a line with "if/for/while/try:", you MUST include the whole body you intend to change through its dedented end (never stop SEARCH mid-block).
3. ONLY fix the bug implied by the problem statement and test failure; avoid unrelated refactors or comment-only edits unless they are required for correctness.
4. If you cannot find the bug in the provided context, output 'ERROR: Bug not found in context'.
5. Do not truncate the REPLACE block; finish every string, bracket, and line you opened.
6. Every non-empty SEARCH line must match the file with the SAME leading whitespace as in the Code section; otherwise the patch is rejected.

EXACT FORMAT:
SEARCH:
<exact code lines>
REPLACE:
<new code lines>"""

    previous_error = ""
    for attempt in range(1, MAX_RETRIES + 2):
        # Escalada progressiva (centrada na linha/função — v4.3.0)
        code_context = get_context_for_attempt(current_content, function_name, line_hint, attempt)

        if attempt == 1:
            user_msg = (
                f"File: {target_rel}\n\nSully's Plan:\n{architect_plan}\n\n"
                f"Code section:\n{code_context}"
            )
        else:
            user_msg = (
                f"File: {target_rel}\n\nPrevious fix FAILED. Test error:\n{previous_error}\n\n"
                f"Original plan:\n{architect_plan}\n\n"
                f"Code section (retry {attempt}):\n{code_context}\n\nTry a different fix consistent with the failure output."
            )

        if error_hint:
            user_msg += f"\n\nHint: {error_hint}"

        fail_excerpt = extract_test_failure(pre_results)
        err_basket = (previous_error or "") + "\n" + (error_hint or "") + "\n" + fail_excerpt[:2500]
        for err_type, expert_tip in EXPERT_HINTS.items():
            if err_type in err_basket:
                user_msg += f"\n\n{expert_tip}"
                break

        ctx_mode = (
            "AST full function"
            if function_name and code_context.startswith(AST_CONTEXT_MARKER)
            else f"sliding window (attempt {attempt})"
        )
        print(f"[CODEY] Tentativa {attempt}/{MAX_RETRIES + 1} — {ctx_mode}...")

        # Restaura arquivo antes de cada retry
        if attempt > 1:
            subprocess.run(["git", "-C", repo_path, "checkout", "--", target_rel], check=False)
            current_content = read_file(target_abs)

        codey_response = prompt_agent(codey_prompt, user_msg)
        patch_applied, err_msg = apply_codey_patch(codey_response, target_abs)

        if not patch_applied:
            previous_error = f"Patch failed: {err_msg}"
            state["errors"].append({"attempt": attempt, "error": previous_error})
            save_state(instance_id, state)
            continue

        # Testa no Docker — Vera usa exit code do processo (pytest / Django runtests / bin/test)
        post_ok, post_results = run_in_docker(container_name, test_script, return_exit_code=True)
        passed = post_ok
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
            # Auto-Rollback v4.3.5 (Reset após falha nos testes)
            rollback_file(repo_path, target_abs)
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

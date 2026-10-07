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
VERSION = "4.5.0"

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
    # LIARA v4.6: Defaults seguros — evita truncamento por contexto curto
    opts["num_predict"] = int(os.environ.get("LIARA_NUM_PREDICT", "2048"))
    opts["num_ctx"] = int(os.environ.get("LIARA_NUM_CTX", "16384"))
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

# ====================== ANTI-LEAKAGE / PATH VALIDATION ======================
def is_test_path(path_str):
    """Determina se o caminho aponta para arquivos de teste (anti-leakage).
    
    Exclui caminhos contendo /test, /tests, test_, _test.py para evitar
    desqualificação no benchmark por modificação indevida de testes.
    """
    if not path_str:
        return False
    norm = path_str.replace("\\", "/").lower().strip()
    for prefix in ["/app/", "app/", "./"]:
        if norm.startswith(prefix):
            norm = norm[len(prefix):]
    norm = "/" + norm.lstrip("/")
    
    parts = [p for p in norm.split("/") if p]
    if not parts:
        return False
    filename = parts[-1]
    dirnames = parts[:-1]
    
    # Exclui se algum diretório intermediário for de teste
    for d in dirnames:
        if d in ("test", "tests", "testing"):
            return True
        if d.startswith("test_") or d.startswith("tests_") or d.endswith("_test") or d.endswith("_tests"):
            return True
    
    # Exclui se o arquivo for de teste
    if filename in ("test.py", "tests.py"):
        return True
    if filename.startswith("test_") or filename.endswith("_test.py") or filename.endswith("_tests.py"):
        return True
    if re.search(r'(^|_)test(s)?(_|\.py$)', filename):
        return True
        
    return False

def filter_production_files(candidates):
    """Filtra lista de candidatos excluindo qualquer caminho de teste."""
    return [c for c in candidates if c and not is_test_path(c)]

# ====================== PATCH APPLICATION (THE SCALPEL) ======================
def validate_patch_syntax(content_or_path, is_content=False):
    """Valida sintaxe Python localmente via ast.parse (sem Docker). Retorna (ok, error_msg)."""
    if is_content:
        source = content_or_path
    else:
        if not content_or_path.endswith('.py'):
            return True, ""
        with open(content_or_path, 'r', encoding='utf-8') as f:
            source = f.read()
    try:
        python_ast.parse(source)
    except SyntaxError as e:
        return False, f"SyntaxError: {e.msg} (line {e.lineno})"
    except Exception as e:
        return False, f"ParseError: {e}"
    return True, ""

def sanitize_patch_block(raw):
    """Remove cercas ``` e linhas vazias no início/fim; normaliza quebras de linha preservando indentação."""
    s = raw.replace("```python", "").replace("```", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = s.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)

def fuzzy_apply_edit(file_path, old_str, new_str):
    """Aplica SEARCH/REPLACE: normaliza CRLF/LF e espaços iniciais no The Scalpel.
    
    Valida sintaxe via ast.parse() em memória antes de persistir alterações ou subir container.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalização rigorosa de quebras de linha (\r\n vs \n)
    content_norm = content.replace("\r\n", "\n").replace("\r", "\n")
    old_str_norm = old_str.replace("\r\n", "\n").replace("\r", "\n")
    new_str_norm = new_str.replace("\r\n", "\n").replace("\r", "\n")

    def get_indent(line):
        return len(line) - len(line.lstrip())

    # 1. Tentativa: Substituição exata de substring
    if old_str_norm in content_norm:
        patched = content_norm.replace(old_str_norm, new_str_norm, 1)
        if file_path.endswith('.py'):
            ok, err = validate_patch_syntax(patched, is_content=True)
            if not ok:
                return f"ERROR: Sintaxe inválida no patch direto: {err}"
        return write_file(file_path, patched)

    # 2. Tentativa: The Scalpel - Casamento fuzzy com tolerância a drift de indentação
    content_lines = content_norm.split('\n')
    search_lines  = old_str_norm.split('\n')
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

        # Preserva a estrutura de indentação relativa (não exige indentação absoluta idêntica)
        anchor_file_indent = get_indent(content_lines[matched_idx[0]])
        anchor_tpl_indent  = get_indent(nonblank_tpl[0])
        indent_delta       = anchor_file_indent - anchor_tpl_indent

        if any((get_indent(content_lines[fk]) - get_indent(tpl)) != indent_delta
               for fk, tpl in zip(matched_idx, nonblank_tpl)):
            continue

        orig_anchor_indent = get_indent(content_lines[i])
        new_split = new_str_norm.split('\n')
        model_anchor_indent = 0
        for nl in new_split:
            if nl.strip():
                model_anchor_indent = get_indent(nl)
                break

        final_lines = []
        if any(nl.strip() for nl in new_split):
            for nl in new_split:
                if not nl.strip():
                    final_lines.append("")
                    continue
                drift = get_indent(nl) - model_anchor_indent
                final_lines.append(" " * max(0, orig_anchor_indent + drift) + nl.lstrip())
        else:
            # Bloco REPLACE vazio (remoção intencional de linhas)
            final_lines = []

        patched_lines = content_lines[:i] + final_lines + content_lines[i + lines_to_replace :]
        patched = "\n".join(patched_lines)

        # Pré-validação em memória via ast.parse antes de tocar o disco
        if file_path.endswith('.py'):
            ok, err = validate_patch_syntax(patched, is_content=True)
            if not ok:
                return f"ERROR: Sintaxe inválida no patch fuzzy: {err}"

        return write_file(file_path, patched)

    return "ERROR: Patch não encontrado (strip+indent ou substring exata)."

def rollback_file(repo_path, file_abs):
    """Reseta deterministicamente o arquivo para o estado original estável e valida com git status."""
    file_rel = os.path.relpath(file_abs, repo_path) if os.path.isabs(file_abs) else file_abs
    subprocess.run(["git", "-C", repo_path, "checkout", "--", file_rel], check=True, capture_output=True)
    status_proc = subprocess.run(
        ["git", "-C", repo_path, "status", "--porcelain", "--", file_rel],
        capture_output=True,
        text=True
    )
    status_out = status_proc.stdout.strip()
    if status_out:
        print(f"[RE-SET WARN] Arquivo {file_rel} ainda com status '{status_out}'. Forçando checkout limpo.")
        subprocess.run(["git", "-C", repo_path, "checkout", "-f", "--", file_rel], check=True, capture_output=True)
    print(f"[RE-SET] Arquivo {file_rel} resetado para o estado estável.")
    return True

def clean_block_fences(block_text):
    """Remove cercas ``` e descarta chatter pós-cerca (ex: ```\nHope this helps!)."""
    text = block_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r'^\s*```[a-zA-Z]*\n', '', text)
    if "```" in text:
        text = text.split("```")[0]
    return sanitize_patch_block(text)

def apply_codey_patch(codey_response, target_abs, repo_path=None):
    """Extrai, aplica e pré-valida sintaticamente o patch SEARCH/REPLACE (The Scalpel)."""
    clean_resp = codey_response.replace("\r\n", "\n").replace("\r", "\n")

    # LIARA v4.6: Normaliza variantes comuns de delimitadores antes do parsing
    # O modelo às vezes gera "REPLACE WITH:" em vez de "REPLACE:"
    clean_resp = re.sub(r'REPLACE\s+WITH\s*:', 'REPLACE:', clean_resp, flags=re.IGNORECASE)
    # Normaliza **SEARCH**: ou *SEARCH*: para SEARCH:
    clean_resp = re.sub(r'\*{1,2}(SEARCH|REPLACE)\*{1,2}\s*:', r'\1:', clean_resp)

    parts = re.split(r"(?:^|\n)\s*(?:```[a-zA-Z]*\n)?\s*SEARCH:", clean_resp)
    if len(parts) < 2:
        return False, "SEARCH/REPLACE block not found or malformed (missing SEARCH:)."

    # LIARA v4.6: Se há múltiplos blocos SEARCH:, usa o primeiro válido
    results = []
    for block_idx, search_rest in enumerate(parts[1:], 1):
        replace_parts = re.split(r"(?:^|\n)\s*REPLACE:", search_rest)
        if len(replace_parts) < 2:
            continue

        old_str = clean_block_fences(replace_parts[0])
        raw_replace = replace_parts[1].split("SEARCH:")[0]
        new_str = clean_block_fences(raw_replace)

        if not old_str.strip():
            continue

        result = fuzzy_apply_edit(target_abs, old_str, new_str)
        print(f"[CODEY] Bloco {block_idx}: {result}")
        if "SUCCESS" in result.upper():
            ok, err = validate_patch_syntax(target_abs)
            if ok:
                print(f"[VALIDA] ✓ Sintaxe OK (bloco {block_idx})")
                return True, ""
            else:
                print(f"[VALIDA] ✗ Bloco {block_idx} gerou sintaxe inválida: {err}. Tentando próximo bloco...")
                if repo_path:
                    rollback_file(repo_path, target_abs)
                results.append((False, err))
                continue
        results.append((False, result))

    # Nenhum bloco funcionou
    if repo_path:
        rollback_file(repo_path, target_abs)
    error_summary = "; ".join(r[1] for r in results) if results else "Nenhum bloco SEARCH/REPLACE válido encontrado."
    return False, f"Patch format invalid: {error_summary}"

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
            if is_test_path(rel):
                continue
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                tree = python_ast.parse(f.read(), filename=fpath)
            for node in python_ast.walk(tree):
                if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef)):
                    func_map.setdefault(node.name, []).append((rel, node.lineno))
    return func_map

def localize_from_traceback(test_output, func_map, repo_path):
    """Usa o traceback do teste para identificar arquivos-fonte candidatos (excluindo testes)."""
    func_names = re.findall(r'in ([a-zA-Z_][a-zA-Z0-9_]+)\s*$', test_output, re.MULTILINE)
    file_hints  = re.findall(r'File "([^"]+\.py)"', test_output)
    candidates  = []

    for fn in func_names:
        if fn in func_map:
            for (rel, _) in func_map[fn]:
                if not is_test_path(rel) and rel not in candidates:
                    candidates.append(rel)

    for fh in file_hints:
        # LIARA v4.2.3: Limpeza de caminhos de traceback (Docker -> Host)
        clean_fh = fh
        for prefix in ["/app/", "app/"]:
            if clean_fh.startswith(prefix):
                clean_fh = clean_fh[len(prefix):]
                break
        
        rel = clean_fh if not os.path.isabs(clean_fh) else os.path.relpath(clean_fh, repo_path)
        
        if not is_test_path(rel) and rel not in candidates:
            candidates.append(rel)

    return [c for c in candidates if not is_test_path(c)][:5]

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
            if rel in seen or is_test_path(rel):
                continue
            seen.add(rel)
            fpath = os.path.join(repo_path, rel)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                snippet = f.read(3000)
            file_emb = get_embedding(snippet)
            if file_emb:
                scored.append((cosine_similarity(query_emb, file_emb), rel))

    scored.sort(reverse=True)
    return [rel for _, rel in scored if not is_test_path(rel)][:top_n]

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
                    "liara-sandbox:3.9", "tail", "-f", "/dev/null"], check=True)
    # LIARA v4.6: Output verboso para diagnosticar falhas de instalação
    install_result = run_in_docker(container_name, "pip install -e . 2>&1 | tail -n 30")
    print(f"[SETUP] pip install -e . resultado: {install_result[:500]}")
    run_in_docker(container_name, "pip install pytest pytest-django pytest-mock tox 2>&1 | tail -n 10")

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

    # === LIARA v4.6: Guarda contra Feedback Poisoning (Env-Guard) ===
    # Detecta se o teste falhou por erro de AMBIENTE (dependência faltante)
    # e não pelo bug real da issue. Se sim, tenta instalar e re-rodar.
    ENV_ERROR_PATTERNS = [
        (r"ModuleNotFoundError: No module named '([^']+)'", "ModuleNotFoundError"),
        (r"ImportError: No module named '([^']+)'", "ImportError"),
        (r"ImportError: cannot import name '([^']+)'", "ImportError"),
    ]

    max_env_fixes = 3  # Limite de auto-fix para evitar loop infinito
    for env_fix_attempt in range(max_env_fixes):
        env_error_found = False
        for pattern, err_type in ENV_ERROR_PATTERNS:
            match = re.search(pattern, pre_results)
            if match:
                missing_mod = match.group(1).split('.')[0]  # Pega módulo raiz
                print(f"[ENV-GUARD] {err_type} detectado: '{missing_mod}' — "
                      f"Isso é erro de AMBIENTE, não o bug da issue. "
                      f"Tentando auto-fix ({env_fix_attempt + 1}/{max_env_fixes})...")
                log_dialogue("ENV-GUARD", f"Auto-instalando módulo faltante: {missing_mod}")
                run_in_docker(container_name, f"pip install {missing_mod} 2>&1 | tail -5")
                # Re-executa o teste
                pre_ok, pre_results = run_in_docker(container_name, test_script, return_exit_code=True)
                env_error_found = True
                break  # Reinicia o loop for para checar novos erros
        if not env_error_found:
            break  # Nenhum erro de ambiente restante

    # Recalcula bug_detected após possíveis auto-fixes de ambiente
    bug_detected = (not pre_ok) or any(
        t in pre_results.lower() for t in ("failed", "traceback", "assertionerror", "errors=")
    )

    # Se AINDA houver ModuleNotFoundError após auto-fix, abortar a issue
    if re.search(r"ModuleNotFoundError|ImportError", pre_results):
        remaining = re.findall(r"No module named '([^']+)'", pre_results)
        if remaining:
            print(f"[ENV-GUARD] ⚠ Dependência irrecuperável: {remaining}. "
                  f"Abortando issue para evitar Feedback Poisoning.")
            log_dialogue("ENV-GUARD", f"Issue abortada: dependência {remaining} não instalável.")
            state["errors"].append({"attempt": 0, "error": f"Env dependency failure: {remaining}"})
            save_state(instance_id, state)
            os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
            return False

    print(f"[REPRO] {'BUG DETECTADO ✓' if bug_detected else 'PASSOU (inesperado)'} (pós env-guard)")

    # Análise determinística do erro
    error_hint = classify_error(pre_results)
    if error_hint:
        print(f"[PATTERN] {error_hint}")

    # Localização via traceback (AST-based)
    # Localização via traceback (AST-based, excluindo testes)
    ast_candidates = filter_production_files(localize_from_traceback(pre_results, func_map, repo_path))
    if ast_candidates:
        print(f"[AST] Candidatos de produção: {ast_candidates}")

    # Localização semântica via embedding (opcional, requer nomic-embed-text)
    emb_candidates = filter_production_files(find_relevant_files_by_embedding(repo_path, issue_data['problem_statement'], func_map))
    if emb_candidates:
        msg = f"[EMB] Candidatos semânticos de produção: {emb_candidates}"
        print(msg)
        log_dialogue("HYBRID ANALYZER", msg)
    else:
        log_dialogue("HYBRID ANALYZER", "[EMB] Nenhum candidato semântico encontrado ou modelo offline.")

    # Síntese de teste de reprodução
    repro_script = synthesize_repro_test(issue_data['problem_statement'])
    if repro_script:
        print(f"[REPRO] Script de reprodução extraído do bug report ✓")

    # Combina candidatos (traceback first, embedding second - 100% filtrados contra testes)
    all_candidates = filter_production_files(list(dict.fromkeys(ast_candidates + emb_candidates)))

    # === FASE 2: Sully — Identificação do Arquivo e Função ===
    # Tarefa 1: Blindagem Anti-Leakage do Sully (Fase 1.1)
    if all_candidates:
        file_context = "Top relevant PRODUCTION files identified by static analysis:\n" + "\n".join(all_candidates[:15])
    else:
        # Fallback para find limitado se AST falhar (filtrando qualquer caminho de teste)
        raw_find = run_in_docker(container_name, "find . -maxdepth 3 -name '*.py' | head -n 50")
        find_lines = [ln.strip().lstrip("./") for ln in raw_find.splitlines() if ln.strip()]
        prod_find = filter_production_files(find_lines)
        file_context = "Production files in repository:\n" + "\n".join(prod_find[:30])

    sully_context = f"Bug Report: {issue_data['problem_statement']}\n\n"
    repro_traceback = extract_test_failure(pre_results)
    if repro_traceback:
        sully_context += f"Test Failure Traceback:\n{repro_traceback}\n\n"
    
    sully_context += f"Analyzed Bug Pattern: {error_hint}\n\n"
    sully_context += "Top relevant files identified by static analysis (PRODUCTION ONLY):\n"
    for f in all_candidates:
        sully_context += f"{f}\n"

    # Dicas de funções do traceback (excluindo funções de teste para evitar que o Sully foque em testes)
    raw_func_hints = re.findall(r'in ([a-zA-Z_][a-zA-Z0-9_]+)\s*$', pre_results, re.MULTILINE)
    func_hints = [fn for fn in raw_func_hints if not fn.startswith("test_") and not fn.startswith("test")]
    if func_hints:
        sully_context += "\nSuspected production functions identified in traceback:\n"
        for fn in sorted(list(set(func_hints))):
            sully_context += f"- {fn}\n"

    if repro_script:
        sully_context += f"\nReproduction script extracted:\n{repro_script[:500]}"
    
    sully_context += f"\n\n{file_context}"

    # Tarefa 1: Sully Prompt com regra explícita de blindagem anti-leakage
    sully_prompt = """You are Sully, a software architect. Analyze the bug and output ONLY a JSON object.
Do NOT explain. Do NOT chatter.

FORMAT:
{
  "file": "relative/path/to/file.py",
  "function": "python_function_or_method_name"
}

RULES:
- The "function" key is REQUIRED: the most specific function or method where the bug occurs.
- ONLY output the relative path from the root of the repository.
- NEVER include prefixes like '/app/', 'app/', 'repos/' or absolute paths.
- STRICT ANTI-LEAKAGE RULE: NEVER target test files (paths containing '/test', '/tests', 'test_', or '_test.py'). Modifying tests is strictly forbidden and causes immediate disqualification.
- Target PRODUCTION source code files ONLY.
- The file MUST exist in the provided list of production files."""

    architect_plan = "{}"
    plan_data = None
    target_rel = None
    function_name = None
    sully_retries = 3
    current_sully_context = sully_context

    for sully_attempt in range(1, sully_retries + 1):
        raw_res = prompt_agent(sully_prompt, current_sully_context)
        plan_data = extract_first_json_object(raw_res)
        if isinstance(plan_data, dict):
            cand_rel = (plan_data.get("file") or "").strip()
            cand_fn = plan_data.get("function")

            # Limpeza de prefixos (Docker -> Host)
            for prefix in ["/app/", "app/", "./", "../"]:
                if cand_rel.startswith(prefix):
                    cand_rel = cand_rel[len(prefix):]
            cand_rel = cand_rel.lstrip("/")

            # Tarefa 1: Validação Anti-Leakage no retorno do modelo
            if is_test_path(cand_rel):
                print(f"[ANTI-LEAKAGE] Rejeitado: Sully sugeriu arquivo de teste ({cand_rel}). Tentativa {sully_attempt}/{sully_retries}.")
                current_sully_context += (
                    f"\n\nREJECTION ERROR: '{cand_rel}' is a TEST file. Modifying test files is strictly forbidden. "
                    f"Select a valid PRODUCTION source code file from the provided list."
                )
                continue

            if cand_rel:
                target_rel = cand_rel
                function_name = cand_fn
                architect_plan = raw_res
                break
        else:
            print(f"[SULLY] Resposta inválida na tentativa {sully_attempt}/{sully_retries}.")

    # Tarefa 1: Fallback determinístico para o candidato de produção do AST se Sully falhou ou escolheu teste
    production_candidates = filter_production_files(ast_candidates + emb_candidates)
    if not target_rel or is_test_path(target_rel):
        print("[ANTI-LEAKAGE] Sully não forneceu arquivo de produção válido. Ativando fallback determinístico do AST.")
        if production_candidates:
            target_rel = production_candidates[0]
            print(f"[ANTI-LEAKAGE] Fallback selecionado do AST: {target_rel}")
            architect_plan = json.dumps({"file": target_rel, "function": function_name or ""})
        else:
            print("[ERRO] Nenhum arquivo de produção disponível para fallback.")
            os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
            return False

    state["sully_response"] = architect_plan

    target_abs = os.path.join(repo_path, target_rel)
    if not os.path.isfile(target_abs) or is_test_path(target_rel):
        for cand in production_candidates:
            if cand == target_rel or is_test_path(cand):
                continue
            cand_abs = os.path.join(repo_path, cand)
            if os.path.isfile(cand_abs):
                print(f"[HYBRID] Caminho ({target_rel}) inexistente/inválido; usando candidato {cand}")
                target_rel, target_abs = cand, cand_abs
                break

    if not os.path.isfile(target_abs) or is_test_path(target_rel):
        print(f"[ERRO] Arquivo alvo inexistente ou inválido após fallback: {target_rel}")
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
Do NOT explain. Do NOT chatter. Do NOT add markdown outside the block.

ABSOLUTE RULES:
1. The SEARCH block MUST match the provided code EXACTLY (same leading spaces on every line).
2. SEARCH must cover complete statements: if you include "if/for/while/try:", include the full body.
3. ONLY fix the bug implied by the problem statement and test failure.
4. NEVER use '...' or placeholder comments to skip code. Write out ALL lines completely.
5. NEVER use 'REPLACE WITH:'. The correct keyword is 'REPLACE:'.
6. Output exactly ONE SEARCH and ONE REPLACE pair per response.
7. If you cannot find the bug, output 'ERROR: Bug not found in context'.
8. Finish every string, bracket, and line you opened. Never truncate.
9. Preserve ALL existing indentation from the Code section.

CORRECT FORMAT EXAMPLE:
SEARCH:
    def calculate(x):
        return x + 1
REPLACE:
    def calculate(x):
        if x is None:
            return 0
        return x + 1

WRONG (will be REJECTED):
- Using 'REPLACE WITH:' instead of 'REPLACE:'
- Using '...' to skip lines
- Multiple SEARCH/REPLACE blocks
- Changing indentation"""

    previous_error = ""
    for attempt in range(1, MAX_RETRIES + 2):
        # Tarefa 2: Rollback Atômico Determinístico no início de cada tentativa se a anterior falhou
        if attempt > 1:
            print(f"[ATOMIC ROLLBACK] Executando rollback_file antes da tentativa {attempt}...")
            rollback_file(repo_path, target_abs)
            
            # Validação com git status no repositório temporário
            status_res = subprocess.run(
                ["git", "-C", repo_path, "status", "--porcelain", "--", target_rel],
                capture_output=True,
                text=True
            )
            if status_res.stdout.strip():
                print(f"[ROLLBACK WARN] Git status não limpo para {target_rel}: {status_res.stdout.strip()}. Forçando checkout.")
                subprocess.run(["git", "-C", repo_path, "checkout", "-f", "--", target_rel], check=True)
            else:
                print(f"[ROLLBACK OK] Repositório verificado: {target_rel} está no estado limpo e estável.")

            current_content = read_file(target_abs)

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

        codey_response = prompt_agent(codey_prompt, user_msg)
        # Tarefa 3: Hardened Scalpel (pré-valida AST antes do Docker)
        patch_applied, err_msg = apply_codey_patch(codey_response, target_abs, repo_path=repo_path)

        if not patch_applied:
            previous_error = f"Patch failed: {err_msg}"
            state["errors"].append({"attempt": attempt, "error": previous_error})
            save_state(instance_id, state)
            # Tarefa 2: Rollback imediato se o patch falhar
            rollback_file(repo_path, target_abs)
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
            # Tarefa 2: Auto-Rollback Determinístico após falha nos testes
            rollback_file(repo_path, target_abs)
            save_state(instance_id, state)
            print(f"[VERA] Tentativa {attempt} falhou. {'Próxima...' if attempt <= MAX_RETRIES else 'Esgotadas.'}")

    os.system(f"docker rm -f {container_name} > /dev/null 2>&1")
    print(f"-> [ORDEM] {instance_id} REJEITADA após {MAX_RETRIES + 1} tentativas.")
    return False

# ====================== ENTRY POINT ======================
if __name__ == "__main__":
    sample_file = os.environ.get("LIARA_SAMPLE", "data/swebench_sample_50.json")
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

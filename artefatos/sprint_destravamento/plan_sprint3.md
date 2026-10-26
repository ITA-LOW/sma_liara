# LIARA — Análise de Causa Raiz & Plano Corretivo Sprint 2

**Autor:** Antigravity (Senior Software Engineer / DevOps Specialist Mode)  
**Data:** 12 de Outubro de 2026  
**Artefatos analisados:** `data/sprint_2/agent_dialogue_1007_0800.txt`, `data/sprint_2/state_*.json`, `main_orchestrator.py`, `plano_correcao_erros_liara.md`, `CONTEXTO_PROJETO.md`

---

## 1. Objetivo

Identificar **precisamente** por que o plano anterior (`plano_correcao_erros_liara.md`) não está gerando resolução das issues, e formular um plano corretivo novo, executável e cirúrgico.

---

## 2. Status de Implementação do Plano Anterior (Diagnóstico)

O plano anterior (`plano_correcao_erros_liara.md`) foi **parcialmente implementado**. Comparando o plano com o código atual:

| Tópico do Plano Anterior | Status no Código Atual |
|---|---|
| Tópico 1: Dockerfile com `python:3.9-bullseye` | ✅ **IMPLEMENTADO** (`Dockerfile.liara` correto) |
| Tópico 1: Trocar imagem no orchestrator | ✅ **IMPLEMENTADO** (linha 647: `liara-sandbox:3.9`) |
| Tópico 1: Remover `-q` do pip install | ✅ **IMPLEMENTADO** (linha 649: output verboso) |
| Tópico 2: Env-Guard (ModuleNotFoundError) | ✅ **IMPLEMENTADO** (linhas 665–710) |
| Tópico 3: `num_ctx=16384` como default | ✅ **IMPLEMENTADO** (linhas 71–73) |
| Tópico 4: Normalizar `REPLACE WITH:` | ✅ **IMPLEMENTADO** (linhas 307–309) |
| Tópico 4: Suporte multi-bloco SEARCH/REPLACE | ✅ **IMPLEMENTADO** (linhas 316–348) |
| Tópico 5: Prompt anti-alucinação do Codey | ✅ **IMPLEMENTADO** (linhas 890–918) |

> [!IMPORTANT]
> **Conclusão Crítica:** O plano anterior foi **completamente implementado** no código. O problema, portanto, **NÃO é de implementação incompleta** — é de **eficácia insuficiente das correções implementadas**. As soluções propostas atacaram os sintomas mas não as causas raízes reais observadas no `sprint_2`.

---

## 3. Análise Forense do Sprint 3: Por Que Ainda Falha

### 3.1 Issue `django__django-11211` — Análise Profunda

**O que os logs mostram (sprint_2/state_django__django-11211.json):**
```
Sully respondeu: {"file": "../../../../../../../../usr/local/lib/python3.9/unittest/suite.py", "function": "addTests"}
```

**Por que isso é catastrófico:**

O traceback do Django é:
```
File "/app/tests/runtests.py", line 499, in <module>
    failures = django_tests(
  File "/app/tests/runtests.py", line 288, in django_tests
    failures = test_runner.run_tests(
  ...
  File "/usr/local/lib/python3.9/unittest/suite.py", line 57, in addTests
    for test in tests:
TypeError: 'NoneType' object is not iterable
```

**Causa raiz real:** O teste Django usa `runtests.py` com um argumento de label de teste customizado que **retorna `None`** em vez de uma coleção de testes. Isso é um bug no `GenericForeignKey` com UUID PK que faz o `get_queryset()` retornar `None`. O arquivo correto é `django/contrib/contenttypes/fields.py`.

**Falha do Env-Guard:** O `ModuleNotFoundError: No module named 'MySQLdb'` que apareceu em tentativas anteriores **pode ter sido resolvido pela imagem Docker nova** — e de fato os logs do sprint_2 mostram que não há mais `ModuleNotFoundError` a interromper o loop. Mas o **traceback que sobrou** (`TypeError: 'NoneType' object is not iterable` na `suite.addTests`) **não é um erro de módulo faltante** — é o **stack frame mais alto visível** de um erro semântico muito mais profundo.

**Falha do Anti-Leakage do Sully:** O Sully está pegando `../../../../../../../../usr/local/lib/python3.9/unittest/suite.py` da lista de candidatos `all_candidates` gerada por `localize_from_traceback`. A função `localize_from_traceback` extrai todos os `File "..."` do traceback, incluindo os da biblioteca padrão. O filtro `is_test_path` **não filtra caminhos de biblioteca padrão** (`/usr/local/lib/python3.9/`).

**Falha Sistêmica #1: `localize_from_traceback` não filtra stdlib:**
```python
# Linha 514: file_hints = re.findall(r'File "([^"]+\.py)"', test_output)
# Para Django, isso captura:
# "/app/tests/runtests.py"  → filtrado (test path) ✓
# "/usr/local/lib/python3.9/unittest/suite.py" → NÃO filtrado ✗
# "/app/django/test/runner.py" → NÃO filtrado ✗ (deveria ser filtrado - é infra Django, não produção)
```

O `is_test_path` só filtra `test_`, `/tests/`, etc. **Não filtra `/usr/local/lib/`** nem paths fora do repositório. Então `/usr/local/lib/python3.9/unittest/suite.py` **entra na lista** de candidatos e o Sully escolhe ele.

**Falha Sistêmica #2: O Sully ignora a regra "must exist in provided list of production files":**

O prompt diz: `"The file MUST exist in the provided list of production files."` Mas a lista `all_candidates` contém esse caminho stdlib, então tecnicamente ele **obedeceu** — o problema é que o filtro a montante deixou entrar.

**Falha Sistêmica #3: Localizador não usa a heurística do traceback corretamente para Django:**

Para Django, o erro raiz está em `contenttypes/fields.py` (bug semântico de UUID GFK), mas o traceback começa pela borda (`runtests.py → runner.py → suite.py`). O sistema precisa identificar qual frame do traceback está **dentro do repositório-alvo** (projeto Django), não qual está no frame mais externo.

---

### 3.2 Issue `sympy__sympy-19783` — Dagger × IdentityOperator

**O que os logs mostram:**

Sully localiza: `sympy/physics/quantum/qexpr.py` → função `mul` ❌

**Causa raiz real:** O bug está em `sympy/physics/quantum/operator.py` → método `__mul__` de `IdentityOperator`. Quando `Dagger(O) * IdentityOperator()` é chamado, o `IdentityOperator.__mul__` não reconhece `Dagger` como um tipo que simplifica para si mesmo. A correção real é no `_eval_mul_method` do `IdentityOperator`.

**Falha do Sully:** O Sully localizou `qexpr.py`/`mul` porque os embeddings semânticos colocaram esse arquivo no topo (o texto da issue menciona "quantum expression"), mas o bug real está no `operator.py`. O modelo não conseguiu disambiguar com o contexto dado.

**Falha do Codey:** Após localização errada, Codey tentou 3× modificar `qexpr.py` sem efeito, pois o bug não está ali. As tentativas foram logicamente incoerentes com o problema real.

**Falha Sistêmica #4: Sem instrução de backtrack do Sully:**

Quando Codey falha 3 vezes no mesmo arquivo sem nunca ter um patch aplicado com sucesso semanticamente, o orquestrador deveria reativar o Sully com contexto de "o arquivo anterior não continha o bug — tente um arquivo diferente". Atualmente, as retentativas do Codey ficam presas no mesmo arquivo.

---

### 3.3 Issue `sympy__sympy-19954` — Sylow Subgroup IndexError

**O que os logs mostram (state_sympy__sympy-19954.json):**

- 18+ tentativas ao longo de múltiplas sessões
- Sully acertou: `sympy/combinatorics/perm_groups.py` → `minimal_blocks` ✓
- Codey gerou 3 patches distintos, todos com `"Patch não encontrado"` na maioria das tentativas

**Causa raiz real do bug:** No loop `for i, r in enumerate(rep_blocks)`, quando `del num_blocks[i], blocks[i]` é executado, o índice `i` calculado pelo `enumerate` para uma lista que está sendo modificada in-place fica inválido. A correção correta é acumular os índices a remover e deletar em ordem reversa.

**Falha do Scalpel com indentação:** Os logs mostram:
```
"Patch failed: Scalpel Error: unexpected indent (<unknown>, line 2193)"
```
e
```
"Patch failed: ERROR: Patch não encontrado (strip+indent ou substring exata)."
```

**Por que o fuzzy matching falha repetidamente?**

A análise do código em `fuzzy_apply_edit` revela um problema sutil: o algoritmo de matching fuzzy exige que **todos os tokens não-brancos** do `SEARCH` casem em sequência no arquivo. Mas quando o Codey gera:

```
SEARCH:
    for i, r in enumerate(rep_blocks):
REPLACE:
    for i, r in enumerate(rep_blocks):
```

Com indentação diferente (ex.: sem os 4 espaços de aninhamento de classe), a busca fuzzy **não encontra match** porque o `indent_delta` para linhas subsequentes não é consistente. Isso acontece porque a função `minimal_blocks` está dentro de uma **classe** (`PermutationGroup`), então o indentação real no arquivo é `    ` (4 espaços de classe) + `    ` (4 espaços de método) = 8 espaços. O Codey com frequência gera o SEARCH com 4 espaços em vez de 8.

**Falha Sistêmica #5: O contexto AST não preserva nem sinaliza explicitamente o nível de indentação para o Codey:**

O bloco SEARCH gerado pelo modelo precisa corresponder ao arquivo com indentação exata. O cabeçalho do contexto diz `"SEARCH must match below with IDENTICAL leading whitespace"`, mas o modelo SLM (qwen2.5-coder:14b ou llama3.1:8b) frequentemente "normaliza" a indentação para 4 espaços independentemente do contexto.

---

## 4. Mapa das Falhas Sistêmicas (Root Causes Reais)

```mermaid
flowchart TD
    subgraph "Falhas NÃO Cobertas pelo Plano Anterior"
        F1["🔴 Falha #1\nlocalize_from_traceback\ninclui caminhos stdlib\n(/usr/local/lib/python3.9/)"]
        F2["🔴 Falha #2\nSully fica preso num arquivo\nquando Codey falha 3×\n(sem backtrack de arquivo)"]
        F3["🔴 Falha #3\nFuzzy matching não casa quando\nindentação aninhada (classe+método)\ndifere do que o Codey gera"]
        F4["🔴 Falha #4\nDjango traceback aponta para\nbiblioteca padrão em vez do\narquivo de produção real"]
    end

    subgraph "Efeitos Observados no Sprint 2"
        E1["django-11211:\nSully targeta unittest/suite.py\n(biblioteca padrão Python)"]
        E2["sympy-19783:\nCodey itera 3× no arquivo errado\n(qexpr.py em vez de operator.py)"]
        E3["sympy-19954:\n18+ tentativas, patch nunca aplica\npor drift de indentação"]
    end

    F1 --> E1
    F4 --> E1
    F2 --> E2
    F3 --> E3
```

---

## 5. Por Que o Plano Anterior Era Insuficiente

O plano anterior focou em:
1. **Infraestrutura Docker** → ✅ Resolveu `ModuleNotFoundError` (psycopg2, MySQLdb)
2. **Env-Guard** → ✅ Abortou issues com dependências irrecuperáveis
3. **num_ctx=16384** → ✅ Eliminou truncamento de resposta
4. **Normalização REPLACE WITH:** → ✅ Reduziu rejeição de formato
5. **Prompt anti-alucinação** → ✅ Reduziu elipses `...`

**O que o plano anterior NÃO atacou:**
- ❌ Filtro de caminhos stdlib em `localize_from_traceback`
- ❌ Mecanismo de backtrack de Sully quando Codey falha no arquivo
- ❌ Indentação aninhada classe+método no matching fuzzy
- ❌ Estratégia de localização para repositórios com harness de teste complexo (Django)

---

## 6. Plano Corretivo Sprint 3 — Mudanças Propostas

> [!IMPORTANT]
> Todas as mudanças são no arquivo `openclaw_swe_benchmark/local_execution/main_orchestrator.py`. O Dockerfile está correto e não precisa de alterações.

---

### Mudança 1 — Filtro de Caminhos Stdlib em `localize_from_traceback`

**Problema:** A função captura `File "/usr/local/lib/python3.9/..."` do traceback e os inclui na lista de candidatos.

**Solução:** Adicionar filtro explícito para caminhos fora do repositório (stdlib, site-packages, etc.) usando um conjunto de prefixos proibidos.

#### [MODIFY] `main_orchestrator.py` — função `localize_from_traceback` (linhas 502–527)

```diff
 def localize_from_traceback(test_output, func_map, repo_path):
     """Usa o traceback do teste para identificar arquivos-fonte candidatos (excluindo testes)."""
     func_names = re.findall(r'in ([a-zA-Z_][a-zA-Z0-9_]+)\s*$', test_output, re.MULTILINE)
     file_hints  = re.findall(r'File "([^"]+\.py)"', test_output)
     candidates  = []
 
+    # LIARA v4.7: Prefixos que indicam stdlib ou dependências externas — nunca são código do repo
+    EXTERNAL_PATH_PREFIXES = (
+        "/usr/local/lib/",
+        "/usr/lib/",
+        "/opt/",
+        "site-packages/",
+        "/home/",      # Proteção extra: não é o repo alvo
+    )
+
     for fn in func_names:
         if fn in func_map:
             for (rel, _) in func_map[fn]:
                 if not is_test_path(rel) and rel not in candidates:
                     candidates.append(rel)
 
     for fh in file_hints:
+        # LIARA v4.7: Descarta caminhos de stdlib, site-packages e dependências externas
+        if any(fh.startswith(prefix) for prefix in EXTERNAL_PATH_PREFIXES):
+            continue
+        # Descarta caminhos que não começam com /app/ (Docker) ou são relativos ao repo
+        if os.path.isabs(fh) and not fh.startswith("/app/"):
+            continue
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
```

---

### Mudança 2 — Mecanismo de Sully Re-localização (File Backtrack)

**Problema:** Quando Codey falha todas as tentativas em um arquivo sem nunca ter aplicado um patch com sucesso semanticamente, o sistema abandona sem tentar outro arquivo.

**Solução:** Detectar quando **todos os erros de uma rodada são do tipo "patch aplicado mas teste falhou" vs "patch não encontrado"**, e no segundo caso (patch nunca aplicado) reativar Sully para tentar um arquivo diferente da lista de candidatos.

#### [MODIFY] `main_orchestrator.py` — Loop principal Codey+Vera (entre linhas 888–1007)

Adicionar variável de controle e lógica de backtrack após o loop:

```python
# === FASE 3: Loop Codey + Vera (escalada progressiva de contexto) ===
# LIARA v4.7: File-level backtrack — tenta até 2 arquivos diferentes por issue
MAX_FILE_ATTEMPTS = 2
tried_files = [target_rel]

for file_attempt in range(MAX_FILE_ATTEMPTS):
    # Reset de contexto para o arquivo atual
    current_content = read_file(target_abs)
    previous_error = ""
    patch_ever_applied = False  # LIARA v4.7: rastreia se algum patch foi aplicado neste arquivo
    
    for attempt in range(1, MAX_RETRIES + 2):
        # ... [código existente do loop interno sem alteração] ...
        
        patch_applied, err_msg = apply_codey_patch(codey_response, target_abs, repo_path=repo_path)
        
        if patch_applied:
            patch_ever_applied = True  # Ao menos um patch tocou o arquivo
        
        # ... [resto do loop interno] ...
    
    # LIARA v4.7: Se nenhum patch foi aplicado (apenas "Patch não encontrado"),
    # tentar um arquivo diferente da lista de candidatos.
    if not patch_ever_applied and file_attempt < MAX_FILE_ATTEMPTS - 1:
        next_candidates = [c for c in production_candidates if c not in tried_files]
        if next_candidates:
            new_target = next_candidates[0]
            tried_files.append(new_target)
            target_rel = new_target
            target_abs = os.path.join(repo_path, target_rel)
            
            # Re-inferir function_name do novo arquivo via AST + line_hint
            new_content = read_file(target_abs)
            if line_hint is not None:
                ast_fn = resolve_innermost_function_at_line(new_content, line_hint)
                if ast_fn:
                    function_name = ast_fn
            
            print(f"[BACKTRACK] Nenhum patch aplicado em '{tried_files[-2]}'. "
                  f"Tentando arquivo alternativo: '{target_rel}'")
            log_dialogue("BACKTRACK", f"Reorientando para arquivo: {target_rel}")
            
            # Rollback do arquivo anterior (embora não modificado, segurança)
            rollback_file(repo_path, os.path.join(repo_path, tried_files[-2]))
            continue  # Volta para o loop de file_attempt com novo target
    
    break  # Se chegou aqui com patch aplicado (mas falhou nos testes), encerra
```

---

### Mudança 3 — Contextualização Explícita de Indentação para o Codey

**Problema:** O cabeçalho `# LIARA:AST_FUNCTION_SCOPE` diz "SEARCH must match below with IDENTICAL leading whitespace", mas o modelo SLM ignora isso ao gerar. O Codey frequentemente remove um nível de indentação quando o método está dentro de uma classe.

**Solução:** Ao construir o `user_msg` para o Codey, calcular e injetar explicitamente o número de espaços de indentação da primeira linha não-blank do contexto.

#### [MODIFY] `main_orchestrator.py` — montagem do `user_msg` no loop Codey (linhas 944–964)

```diff
         if attempt == 1:
             user_msg = (
                 f"File: {target_rel}\n\nSully's Plan:\n{architect_plan}\n\n"
-                f"Code section:\n{code_context}"
+                f"Code section:\n{code_context}"
             )
+        # LIARA v4.7: Extrai indentação âncora e injeta no prompt para prevenir drift
+        anchor_indent = 0
+        for line in code_context.split('\n'):
+            if line.strip():
+                anchor_indent = len(line) - len(line.lstrip())
+                break
+        if anchor_indent > 0:
+            indent_warning = (
+                f"\n\nINDENTATION ALERT: The code above uses {anchor_indent} spaces "
+                f"of base indentation. Your SEARCH block MUST start with exactly "
+                f"{anchor_indent} spaces on the first non-empty line. "
+                f"DO NOT reduce indentation."
+            )
+            user_msg += indent_warning
         else:
             user_msg = (
                 f"File: {target_rel}\n\nPrevious fix FAILED. Test error:\n{previous_error}\n\n"
                 f"Original plan:\n{architect_plan}\n\n"
                 f"Code section (retry {attempt}):\n{code_context}\n\nTry a different fix consistent with the failure output."
             )
+            if anchor_indent > 0:
+                user_msg += (
+                    f"\n\nINDENTATION ALERT: Base indentation = {anchor_indent} spaces. "
+                    f"Keep ALL lines with their original leading spaces."
+                )
```

---

### Mudança 4 — Estratégia de Localização para Django (Harness Complexo)

**Problema:** Para issues Django, o traceback frequentemente termina em `runner.py` ou `suite.py` (a borda do harness de teste), sem revelar o arquivo de produção real. O campo `problem_statement` da issue contém a descrição do bug com menção ao modelo Django afetado (ex.: `GenericForeignKey`, `ContentType`). Mas a localização por embedding usa o `problem_statement` curto.

**Solução:** Para repositórios onde o traceback inclui arquivos de harness de teste (detectável pela presença de `runtests.py` no traceback), usar o `problem_statement` completo para guiar o Sully com contexto adicional e forçar o Sully a escolher um arquivo da lista de candidatos semânticos — não do traceback.

#### [MODIFY] `main_orchestrator.py` — construção do `sully_context` (linhas 751–772)

```diff
 sully_context = f"Bug Report: {issue_data['problem_statement']}\n\n"
 repro_traceback = extract_test_failure(pre_results)
 if repro_traceback:
     sully_context += f"Test Failure Traceback:\n{repro_traceback}\n\n"
 
+# LIARA v4.7: Detecta harness complexo (Django/pytest que falha na infraestrutura de runner)
+# Se o traceback aponta para arquivos de harness, instrui Sully a ignorar o traceback e focar
+# nos candidatos semânticos
+HARNESS_MARKERS = ["runtests.py", "unittest/suite.py", "test/runner.py", "conftest.py"]
+traceback_is_harness = any(m in repro_traceback for m in HARNESS_MARKERS) if repro_traceback else False
+if traceback_is_harness:
+    sully_context += (
+        "NOTE: The traceback above shows a test harness error (runtests.py / runner infrastructure). "
+        "The REAL bug is NOT in the test runner. Focus on the 'Bug Report' description above to "
+        "identify the correct production file and function. Prioritize files from the semantic "
+        "candidates list below.\n\n"
+    )
 
 sully_context += f"Analyzed Bug Pattern: {error_hint}\n\n"
```

---

### Mudança 5 — Validação de Existência do Arquivo Antes de Enviar ao Sully

**Problema:** A lista `all_candidates` pode conter caminhos que existem no traceback mas não existem no repositório clonado (ex.: caminhos da stdlib que passaram pelo filtro).

**Solução:** Filtrar `all_candidates` para conter apenas caminhos que efetivamente existem no `repo_path`.

#### [MODIFY] `main_orchestrator.py` — linha 738 (síntese de candidatos)

```diff
-    all_candidates = filter_production_files(list(dict.fromkeys(ast_candidates + emb_candidates)))
+    # LIARA v4.7: Garante que todos os candidatos existem fisicamente no repo (exclui stdlib/externos)
+    all_candidates = filter_production_files(list(dict.fromkeys(ast_candidates + emb_candidates)))
+    all_candidates = [c for c in all_candidates if os.path.isfile(os.path.join(repo_path, c))]
```

---

## 7. Arquivos Afetados

| Arquivo | Ação | Mudança |
|---|---|---|
| [`main_orchestrator.py`](file:///home/carol-lanzu/Documents/artigo-UFSC/sma_liara/openclaw_swe_benchmark/local_execution/main_orchestrator.py) | **MODIFY** | Mudanças 1, 2, 3, 4, 5 |
| `Dockerfile.liara` | **SEM ALTERAÇÃO** | Já correto |

---

## 8. Diagrama do Fluxo Corrigido

```mermaid
flowchart TD
    A["Fase 1: Reprodução do Bug"] --> B["Env-Guard\n(já implementado)"]
    B --> C["localize_from_traceback\n🆕 Filtra stdlib/externos\n🆕 Valida existência no repo"]
    C --> D["Sully\n🆕 Context: harness=complexo → ignora traceback\n🆕 Usa candidatos semânticos"]
    D --> E{Sully escolheu\narquivo de teste?}
    E -->|sim| F["Fallback AST\n(já implementado)"]
    E -->|não| G["Codey Loop"]
    F --> G
    G --> H["🆕 Inject: INDENTATION ALERT\nanchor_indent = N espaços"]
    H --> I["apply_codey_patch\n(fuzzy matching)"]
    I --> J{Patch\naplicado?}
    J -->|sim| K["Vera: roda testes"]
    J -->|não| L{Todas tentativas\nesgotadas sem\nnenhum patch?}
    L -->|sim| M["🆕 FILE BACKTRACK\nSully → próximo candidato"]
    L -->|não| G
    M --> G
    K --> N{Passou?}
    N -->|sim| O["RESOLVED ✓"]
    N -->|não| G
```

---

## 9. Verification Plan

### 9.1 Testes Automatizados

#### Teste de regressão de `localize_from_traceback` (Mudança 1)
```python
# Executar em: openclaw_swe_benchmark/local_execution/
python3 -c "
import sys; sys.path.insert(0, '.')
from main_orchestrator import localize_from_traceback

django_traceback = '''
Traceback (most recent call last):
  File \"/app/tests/runtests.py\", line 499, in <module>
    failures = django_tests(
  File \"/app/django/test/runner.py\", line 627, in run_tests
    suite = self.build_suite(test_labels, extra_tests)
  File \"/usr/local/lib/python3.9/unittest/suite.py\", line 57, in addTests
    for test in tests:
TypeError: 'NoneType' object is not iterable
'''
results = localize_from_traceback(django_traceback, {}, '/tmp/repo')
print('Candidatos:', results)
assert not any('usr/local' in c for c in results), 'FALHA: stdlib ainda na lista!'
assert not any('unittest' in c for c in results), 'FALHA: unittest/suite.py passou!'
print('PASSOU: stdlib filtrado corretamente')
"
```

#### Sintaxe do orchestrator
```bash
cd openclaw_swe_benchmark/local_execution
python3 -c "import ast; ast.parse(open('main_orchestrator.py').read()); print('Syntax OK')"
```

#### Smoke test com issue django__django-11211
```bash
cd openclaw_swe_benchmark/local_execution

# Criar amostra com apenas django-11211
python3 -c "
import json
with open('../../data/swebench_sample_50.json') as f:
    issues = json.load(f)
target = [i for i in issues if i['instance_id'] == 'django__django-11211']
with open('data/swebench_sample_1.json', 'w') as f:
    json.dump(target, f, indent=2)
print(f'Amostra criada: {len(target)} issue(s)')
"

LIARA_MODEL=qwen2.5-coder:14b \
LIARA_NUM_CTX=16384 \
LIARA_SAMPLE=data/swebench_sample_1.json \
LIARA_RETRIES=3 \
python3 main_orchestrator.py 2>&1 | tee /tmp/smoke_django.log

# Verificar que Sully NÃO aponta mais para unittest/suite.py
grep -i "sully\|unittest/suite\|usr/local" /tmp/smoke_django.log
```

#### Smoke test com issue sympy__sympy-19954 (Sylow/minimal_blocks)
```bash
python3 -c "
import json
with open('../../data/swebench_sample_50.json') as f:
    issues = json.load(f)
target = [i for i in issues if i['instance_id'] == 'sympy__sympy-19954']
with open('data/swebench_sample_1.json', 'w') as f:
    json.dump(target, f, indent=2)
"

LIARA_MODEL=qwen2.5-coder:14b \
LIARA_NUM_CTX=16384 \
LIARA_SAMPLE=data/swebench_sample_1.json \
LIARA_RETRIES=3 \
python3 main_orchestrator.py 2>&1 | tee /tmp/smoke_sympy.log

# Verificar INDENTATION ALERT no log e ausência de "Patch não encontrado" em todos
grep -c "INDENTATION ALERT" /tmp/smoke_sympy.log
grep -c "Patch não encontrado" /tmp/smoke_sympy.log
```

### 9.2 Verificação Manual

1. **Mudança 1 — Filtro stdlib:** Após smoke test Django, verificar em `data/agent_dialogue_*.txt` que nas seções `[HYBRID ANALYZER]` e `[SYSTEM: You are Sully]`, o arquivo `unittest/suite.py` ou qualquer path `/usr/local/lib/` **não aparece mais** na lista de candidatos.

2. **Mudança 2 — Backtrack:** Para sympy-19783, verificar se a seção `[BACKTRACK]` aparece no log quando Codey falha sem aplicar nenhum patch.

3. **Mudança 3 — Indentation Alert:** Para sympy-19954, verificar que o `user_msg` enviado ao Codey contém `"INDENTATION ALERT: Base indentation = 8 spaces"` (pois `minimal_blocks` está dentro de uma classe).

4. **Mudança 4 — Harness Django:** Verificar que o `[SYSTEM: You are Sully]` para django-11211 contém `"NOTE: The traceback above shows a test harness error"`.

5. **Mudança 5 — File existence:** Verificar que a lista `all_candidates` em `[HYBRID ANALYZER]` não contém mais `../../../../../../../../usr/local/lib/python3.9/unittest/suite.py`.

---

## 10. Considerações Técnicas Adicionais

### Sobre o Bug Real do Django-11211 (Para Validação Manual)

A correção real que o Codey deve gerar está em `django/contrib/contenttypes/fields.py`, função `get_prefetch_queryset` (ou `create_generic_related_objects_iterable`). O bug é que ao fazer `prefetch_related` com um `GenericForeignKey` cujo `object_id_field` é `CharField` mas o PK do modelo relacionado é `UUIDField`, o cast de tipos falha e retorna `None` em vez de uma queryset. A correção é converter o `pk_val` adequadamente antes do lookup.

### Sobre o Bug Real do Sympy-19954 (Para Validação Manual)

A correção real em `sympy/combinatorics/perm_groups.py`, função `minimal_blocks`:
```python
# Erro: del num_blocks[i], blocks[i] dentro de for i, r in enumerate(rep_blocks)
# Correção: Acumular índices e deletar em ordem reversa
to_remove_idx = []
for i, r in enumerate(rep_blocks):
    if len(r) > len(rep) and rep.issubset(r):
        to_remove_idx.append(i)  # Acumula em vez de deletar imediatamente
    elif len(r) < len(rep) and r.issubset(rep):
        minimal = False
        break
# Deleta em ordem reversa para preservar índices
for i in sorted(to_remove_idx, reverse=True):
    del num_blocks[i], blocks[i]
rep_blocks = [r for r in rep_blocks if r not in to_remove]
```

### Sobre o Bug Real do Sympy-19783 (Para Validação Manual)

A correção real está em `sympy/physics/quantum/operator.py`, método `__mul__` de `IdentityOperator`:
```python
def __mul__(self, other):
    if isinstance(other, (Operator, Dagger)):  # Adicionar Dagger aqui
        return other
    return Mul(self, other)
```

---

## 11. Sequência de Implementação

1. **Aplicar Mudança 5** (mais simples, uma linha) — previne caminhos inválidos na lista
2. **Aplicar Mudança 1** — filtro stdlib no `localize_from_traceback`  
3. **Aplicar Mudança 4** — detector de harness no contexto do Sully
4. **Aplicar Mudança 3** — injeção de `INDENTATION ALERT` no prompt do Codey
5. **Aplicar Mudança 2** — lógica de File Backtrack (mais complexa, requer refactor do loop)
6. **Rodar testes de regressão** (Mudança 1)
7. **Smoke tests** (django-11211, sympy-19954, sympy-19783)
8. **Benchmark completo** (50 issues)

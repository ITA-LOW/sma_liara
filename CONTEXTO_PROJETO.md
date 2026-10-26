# CONTEXTO_PROJETO.md — Memória de Sessão & Guia de Continuidade (TCC LIARA)

> **Instrução para a IA:** Ao iniciar ou retomar uma sessão neste repositório, leia este arquivo integralmente para entender o objetivo acadêmico, a arquitetura do software, o status atual dos experimentos, os gargalos diagnosticados e os próximos passos imediatos.

---

## 1. Identificação do Projeto & Objetivo Acadêmico

- **Natureza do Trabalho:** Trabalho de Conclusão de Curso (TCC) / Artigo Acadêmico formato IEEE Transactions on Software Engineering (TSE).
- **Instituição:** ITA (Instituto Tecnológico de Aeronáutica).
- **Equipe / Autores:** Ítalo Silva, Carol Yamaguchi.
- **Orientação:** Prof. Alison Panisson.
- **Nome do Framework:** **LIARA** (*Lean Isolated Agents for Repair Automation*).
- **Tese Central:** É viável e altamente custo-efetivo descentralizar a correção automática de programas (Automated Program Repair - APR) através de um Sistema Multiagente (MAS) composto exclusivamente por Modelos de Linguagem Compactos (SLMs, ex: `Qwen2.5-Coder:14b` ou `Llama-3.1:8B`), executados localmente em hardware de consumo (zero custo de API, privacidade total, sem fine-tuning prévio), alcançando resultados competitivos no benchmark **SWE-bench Verified**.

---

## 2. Arquitetura do Sistema LIARA

O pipeline do LIARA é executado de forma orquestrada e dividida em fases estritas:

```
[Issue + Test Patch] 
        │
        ▼
[Fase 0: Análise Estática sem LLM]
  ├─ AST Mapping (mapeia funções para arquivos locais)
  ├─ Embedding Search (nomic-embed-text)
  ├─ Error Pattern Matching (regras determinísticas para tracebacks)
  └─ Traceback Localization
        │
        ▼
[Fase 1: Reprodução do Bug no Docker Sandbox]
  └─ Valida se o teste da issue realmente falha (Bug Detectado)
        │
        ▼
[Fase 2: Sully (O Arquiteto LLM)]
  └─ Recebe issue + contexto estático e localiza o par {"file": ..., "function": ...}
        │
        ▼
[Fase 3: Loop Iterativo Codey (Coder) + Vera (QA)] (até MAX retries)
  ├─ Codey: Gera bloco SEARCH/REPLACE baseado no contexto (níveis 1, 2 ou 3)
  ├─ The Scalpel: Aplica patch via fuzzy matching tolerante a indentação/espaços
  ├─ Validação Sintática: ast.parse antes de chamar o Docker
  ├─ Execução no Docker: Roda os testes unitários do SWE-bench
  └─ Vera: Extrai falhas relevantes dos logs de teste e guia a próxima tentativa
```

---

## 3. Estado Atual do Repositório & Diagnóstico Técnico

- **Último Commit:** `7b30c67 (teste de 300 falhou)`.
- **Status do Código:** Arquivo principal localizado em `openclaw_swe_benchmark/local_execution/main_orchestrator.py`.

### Gargalos Críticos Identificados nos Testes:
1. **Sobrecarga de Escala (Amostra de 300 issues):** Tentar rodar 300 instâncias complexas em hardware de consumidor gerou instabilidade, timeouts e estouro de tempo de execução. **Decisão:** Limitar o benchmark a uma amostra representativa e estratificada de **30 a 50 issues** do SWE-bench Verified (arquivo `data/swebench_sample_50.json`, gerado com `seed=42`).
2. **Data Leakage no Sully (Localização em Testes):** Em instâncias como `sympy__sympy-13551`, o Sully sugeriu modificar arquivos dentro de diretórios de testes (`tests/test_products.py`). No SWE-bench, modificar o arquivo de teste desqualifica a solução. **Correção pendente:** Sanitizar e forçar o prompt/validador do Sully para selecionar exclusivamente arquivos de código-fonte de produção.
3. **Falhas de Aplicação de Patch do Codey:** Erros frequentes de `Patch não encontrado (strip+indent ou substring exata)` e erros de sintaxe gerados pelo modelo (`unmatched ')'`, problemas de indentação).
4. **Isolamento de Estado (Rollback):** Garantir que, a cada falha de tentativa do Codey, o repositório sofra rollback determinístico (`git checkout -- <arquivo>`) para que o contexto da tentativa anterior não contamine a próxima.
5. **Redação do Artigo LaTeX:** O arquivo `Computer_Society_LaTeX_template/main_article.tex` possui a estrutura completa montada, aguardando a inserção dos números empíricos consolidados (substituição dos placeholders `X%`), geração dos gráficos e curadoria do `references.bib`.

---

## 4. Plano de Ação Imediato (Sprint de Destravamento)

Quando retomar, execute as tarefas na seguinte sequência:

### Tarefa 1: Blindagem Anti-Leakage do Sully (Fase 1.1)
- **Arquivo:** `openclaw_swe_benchmark/local_execution/main_orchestrator.py`
- **Ação:** No método do Sully, filtrar a lista de arquivos candidatos para **excluir** caminhos contendo `/test`, `/tests`, `test_`, `_test.py`. Se o modelo devolver um arquivo de teste, rejeitar e forçar retry ou fallback para o candidato de produção do AST.

### Tarefa 2: Rollback Atômico Determinístico (Fase 1.3)
- **Arquivo:** `openclaw_swe_benchmark/local_execution/main_orchestrator.py`
- **Ação:** Assegurar que a função `rollback_file()` seja chamada pontualmente no início de cada tentativa do Codey se a anterior falhou, validando com `git status` no repositório temporário.

### Tarefa 3: Hardening do Patcher do Codey (Fase 1.2)
- **Arquivo:** `openclaw_swe_benchmark/local_execution/main_orchestrator.py`
- **Ação:** Reforçar a normalização de quebras de linha (`\r\n` vs `\n`) e espaços iniciais no "The Scalpel". Validar via `ast.parse()` antes de subir o container Docker para descartar tentativas com sintaxe quebrada sem gastar tempo de teste.

### Tarefa 4: Ajuste da Amostra & Smoke Test (Fase 1.4 e 1.5)
- **Ação:** Definir `LIARA_SAMPLE="data/swebench_sample_50.json"` (ou testar primeiro com 3 issues). Rodar um smoke test controlado para confirmar que o ciclo completo roda sem travar.

### Tarefa 5: Disparo do Benchmark & Avanço na Redação (Fase 2 e Fase 4)
- **Ação:** Executar o benchmark local com o comando:
  ```bash
  cd openclaw_swe_benchmark/local_execution
  LIARA_MODEL=qwen2.5-coder:14b LIARA_RETRIES=3 LIARA_SAMPLE=data/swebench_sample_50.json python3 main_orchestrator.py
  ```
- Enquanto o benchmark roda em segundo plano, editar as seções de Introdução, Related Work e Arquitetura no LaTeX.

---

## 5. Mapeamento de Arquivos e Diretórios Chave

| Caminho | Descrição |
|---|---|
| `openclaw_swe_benchmark/local_execution/main_orchestrator.py` | Orquestrador principal do LIARA (Sully, Codey, Vera, Docker, AST, Embeddings). |
| `openclaw_swe_benchmark/local_execution/download_swebench.py` | Script de download e amostragem do SWE-bench Verified (seed 42). |
| `openclaw_swe_benchmark/local_execution/data/` | Contém os arquivos de amostra (`swebench_sample_50.json`) e os arquivos de estado gerados (`state_*.json`). |
| `liara_architecture.md` | Diagrama Mermaid com o fluxo completo de decisão e execução do LIARA. |
| `artefatos/liara_positioning.md` | Posicionamento científico (quadrante: Local/Grátis sem Fine-Tuning) e baselines da literatura (SWE-agent, SWE-smith). |
| `artefatos/final_article_roadmap.md` | Planejamento da estrutura de seções do artigo. |
| `Computer_Society_LaTeX_template/main_article.tex` | Documento LaTeX principal do artigo/monografia IEEE TSE. |
| `Computer_Society_LaTeX_template/references.bib` | Arquivo BibTeX de referências acadêmicas. |

---

## 6. Comandos Úteis do Ambiente

- **Verificar status de containers e instâncias Docker:**
  ```bash
  docker ps -a
  ```
- **Limpar containers órfãos de benchmarks anteriores:**
  ```bash
  docker rm -f $(docker ps -a -q --filter "name=liara-") 2>/dev/null || true
  ```
- **Verificar instâncias resolvidas na pasta data:**
  ```bash
  grep -rn '"resolved": true' openclaw_swe_benchmark/local_execution/data/
  ```
- **Conferir histórico git recente:**
  ```bash
  git log -n 5 --oneline
  ```

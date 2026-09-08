# Visão Geral do Repositório `sma_liara`

## Engenharia de Software com Sistemas Multi-Agentes

---

## 1. Visão Geral do Repositório

O repositório **`sma_liara`** é o espaço de pesquisa e desenvolvimento do projeto **LIARA** (*Lean Isolated Agents for Repair Automation*), um trabalho acadêmico voltado para publicação na IEEE Transactions on Software Engineering (TSE). O repositório reúne:

- O **código-fonte do orquestrador principal** (`main_orchestrator.py`), que implementa o sistema multi-agente de reparação automática de programas;
- **Artefatos de pesquisa** (notas, roteiros, posicionamentos acadêmicos e prompts dos agentes);
- **Experimentos de benchmark** baseados no dataset **SWE-bench Verified**, que avalia a capacidade de sistemas autônomos em resolver issues reais do GitHub;
- **Documentação arquitetural** (diagramas de fluxo, changelogs e resumos técnicos);
- Um **template LaTeX** para a IEEE Computer Society, indicando a maturidade do projeto para submissão formal.

A função primária do repositório é servir como base experimental e documental para demonstrar que uma **equipe de modelos de linguagem pequenos e especializados**, operando localmente e sem custo de API, consegue executar tarefas complexas de engenharia de software de forma competitiva com sistemas baseados em LLMs proprietários (como GPT-4).

---

## 2. Conceitos Centrais

### 2.1 Sistemas Multi-Agentes (SMA) em Engenharia de Software

Um Sistema Multi-Agente é uma arquitetura computacional em que múltiplas entidades autônomas — os **agentes** — colaboram para resolver problemas que seriam difíceis ou impossíveis para um único agente. No contexto da engenharia de software, isso significa decompor tarefas complexas (como entender um bug, localizar o arquivo afetado, gerar um patch e validar a correção) em **papéis discretos e especializados**, cada um executado por um agente diferente. Essa divisão imita o fluxo natural de uma equipe de desenvolvimento humana: arquiteto → programador → QA.

### 2.2 Descentralização de Capacidades de LLMs

LLMs (*Large Language Models*) como GPT-4 e Claude são modelos com dezenas ou centenas de bilhões de parâmetros, acessíveis apenas via APIs pagas, com custo elevado e implicações de privacidade (o código-fonte enviado a APIs de terceiros pode ser sensível). A **descentralização** proposta pelo LIARA significa transferir essas capacidades para o ambiente local da organização, utilizando:

- **SLMs** (*Small Language Models*): modelos menores (7B–14B parâmetros), como Qwen 2.5-Coder ou Llama 3.1, que rodam em hardware de consumidor com GPU de 8GB de VRAM;
- **Ollama**: servidor de inferência local que elimina dependência de APIs externas;
- **Arquitetura multi-agente com papéis restritos**: em vez de um único modelo enorme tentando resolver tudo, múltiplos modelos menores atuam em tarefas focadas, reduzindo a carga cognitiva de cada um.

### 2.3 Orquestração de SLMs para Tarefas de Engenharia de Software

A orquestração é o mecanismo pelo qual o sistema coordena a sequência de chamadas aos agentes, gerencia o estado compartilhado (arquivo JSON de estado por issue), realiza *rollbacks* automáticos em caso de falha, e escala progressivamente o contexto fornecido a cada tentativa de reparo. O orquestrador é o "cérebro logístico" — determinístico e programático — que controla quando e como cada SLM é acionado.

---

## 3. O Projeto LIARA: Elaboração do Tema de Pesquisa

### 3.1 Objetivos e Posicionamento

O LIARA ocupa um **nicho não explorado na literatura**: a interseção entre (a) execução local sem fine-tuning e (b) arquitetura multi-agente. Os quadrantes existentes são:

| | Com fine-tuning | Sem fine-tuning |
|---|---|---|
| **API Cloud** | SWE-smith (40% Pass@1, custo ~$1.360) | SWE-agent (12.5% Pass@1, GPT-4 Turbo) |
| **Local / Custo Zero** | *(não publicado)* | **LIARA** ← |

Conforme afirma o documento de posicionamento do próprio projeto: *"Ninguém publicou um estudo sistemático do quadrante local + sem fine-tuning com arquitetura multi-agente."* O LIARA, portanto, **estabelece a linha de base do quadrante democratizado**: o que é possível com modelos locais, custo zero de API e sem fine-tuning.

### 3.2 Metodologia: Orquestração em Fases

O sistema opera em **quatro fases sequenciais**, visíveis tanto no código quanto no diagrama arquitetural:

- **Fase 0 — Análise Estática (sem LLM):** O orquestrador mapeia o repositório via AST (*Abstract Syntax Tree*), realiza busca semântica por embeddings (`nomic-embed-text`), aplica 12 heurísticas de padrões de erro (ex.: `IndexError → dica de verificação de bounds`) e extrai candidatos de localização a partir do traceback. **Nenhum modelo de linguagem é consumido nesta fase.**
- **Fase 1 — Reprodução do Bug:** O sistema executa os testes reais no Docker para confirmar que o bug existe antes de qualquer geração de código.
- **Fase 2 — Sully (O Arquiteto):** O primeiro SLM recebe o relatório do bug, o traceback e os candidatos da análise estática. Sua única tarefa é identificar o arquivo e a função exatos onde a correção deve ser aplicada (saída em JSON estrito). Papel: análise e planejamento.
- **Fase 3 — Loop Codey + Vera:** O segundo SLM (*Codey*) gera blocos SEARCH/REPLACE para aplicar a correção. O sistema valida sintaticamente o patch via `ast.parse` (sem Docker, custo zero) e, em caso de aprovação, executa os testes reais. Vera é uma **entidade determinística** (não um LLM): ela analisa a saída dos testes para classificar sucesso ou falha e guiar a próxima tentativa de *Codey*.

### 3.3 Significância e Impacto Potencial

- **Democratização:** Permite que laboratórios universitários e empresas sem orçamento para APIs realizem APR (*Automated Program Repair*) com qualidade comparável a sistemas proprietários;
- **Privacidade:** O código-fonte nunca sai do ambiente local;
- **Reprodutibilidade:** Qualquer pesquisador com `git clone` + `ollama pull` e uma GPU de consumidor pode reproduzir os experimentos;
- **Base científica inédita:** A tabela custo × resolução (GPT-4 vs. SLMs locais) não existe na literatura atual.

---

## 4. Implementação Técnica

### 4.1 Arquitetura Geral

O arquivo central é o `main_orchestrator.py` (816 linhas, Python puro, sem dependências de frameworks de agentes como LangChain ou CrewAI). Ele coordena:

- **Localização Híbrida de Bugs:** combina análise AST determinística (mapeamento `função → arquivo`), busca semântica por cosseno com embeddings e extração de candidatos via traceback;
- **`fuzzy_apply_edit`:** Motor de aplicação de patches tolerante a variações de indentação — resolve um dos principais gargalos de SLMs menores (erros de alinhamento de espaços);
- **Auto-Rollback (v4.3.5):** Após qualquer falha sintática ou de teste, o arquivo é restaurado via `git checkout` antes da próxima tentativa, evitando "acúmulo de danos" entre tentativas;
- **Contexto Progressivo (v4.4.0):** Nas primeiras tentativas, o Codey recebe apenas a assinatura da função (menos tokens, mais foco); em tentativas posteriores, o corpo completo e o entorno são incluídos;
- **Gestão de Estado JSON:** Cada issue tem seu estado persistido, permitindo retomada e análise post-mortem.

### 4.2 Estrutura do Repositório

```
sma_liara/
├── openclaw_swe_benchmark/
│   └── local_execution/
│       ├── main_orchestrator.py   ← Orquestrador central (LIARA v4.4.3)
│       ├── skills/
│       │   ├── file_editor/       ← Skill de edição de arquivo (Codey)
│       │   └── bash_executor/     ← Skill de execução Docker (Vera)
│       └── data/                  ← Estados JSON e logs de diálogo
├── artefatos/                     ← Documentação de pesquisa
├── artigos_referencia/            ← PDFs de trabalhos relacionados (SWE-agent, SWE-smith)
├── Computer_Society_LaTeX_template/ ← Template IEEE TSE
└── liara_architecture.md          ← Diagrama Mermaid do fluxo completo
```

### 4.3 Hardware e Configuração de Execução

| Componente | Especificação |
|---|---|
| GPU | AMD RX 580 (8GB VRAM) |
| RAM | 64 GB |
| Modelo SLM | Qwen2.5-Coder:14B via Ollama |
| Isolamento | Docker (container por issue, descartado após resolução) |
| Dataset | SWE-bench Verified (5 issues: sympy ×3, django ×2) |

---

## 5. Contribuição ao Estado da Arte

O LIARA avança o estado da arte em engenharia de software com IA em três frentes:

1. **Validação determinística como substituto ao julgamento LLM:** A substituição do "juiz LLM" por análise programática de saída de testes (a entidade Vera) elimina uma fonte mensurável de ruído e alucinações no loop de reparo — um passo metodológico que a literatura ainda não sistematizou;

2. **Especialização de papel como habilitadora de SLMs:** A hipótese central e testável do projeto é que SLMs menores *funcionam melhor* quando operam em tarefas atômicas e focadas, em vez de tentarem resolver o problema completo de uma só vez. O design do LIARA operacionaliza e quantifica essa hipótese;

3. **Benchmark de custo-eficiência inédito:** Ao comparar diretamente o desempenho (Pass@1) com o custo monetário real ($0 local vs. ~$1.360 SWE-smith), o projeto preenche uma lacuna significativa na literatura: a análise econômica da APR automatizada para pesquisadores e organizações com recursos limitados.

---

> **Nota metodológica:** Os resultados experimentais finais (Pass@1 do Qwen2.5-Coder:14B) estão em coleta no momento da redação deste documento (versão LIARA v4.4.3, agosto de 2026). O repositório serve simultaneamente como laboratório ativo de experimentos e como base documental para o artigo acadêmico em preparação para a IEEE TSE.

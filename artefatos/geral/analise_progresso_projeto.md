# Análise de Progresso do Projeto LIARA

> **Projeto:** LIARA — *Lean Isolated Agents for Repair Automation*
> **Avaliação realizada em:** Agosto de 2026 (LIARA v4.4.3)
> **Base de análise:** Repositório `sma_liara` — código, artefatos e documentação

---

## Legenda de Status

| Símbolo | Significado |
|---|---|
| ✅ | Completo / pronto para uso |
| 🔶 | Parcialmente completo / esboço existente |
| ❌ | Ausente / ainda não iniciado |

---

## Cenário 1: Artigo Científico (IEEE TSE)

### O que já está pronto

#### Estrutura e Escrita do Artigo

| Componente | Status | Detalhe |
|---|---|---|
| Título definitivo | ✅ | *"LIARA: Decentralizing LLM Capabilities in Software Engineering via Small Language Model Orchestration"* — definido no `main_article.tex` |
| Abstract | ✅ | Completo, em inglês, no formato IEEE, no `main_article.tex` |
| Seção 1 — Introdução | ✅ | Redigida e revisada, com motivação (custo, privacidade, SLMs) e apresentação do LIARA |
| Seção 2 — Related Work | ✅ | Redigida com citações ao MAGIS, MAO, RGD, "Lost in the Middle" e outros |
| Seção 3 — Arquitetura LIARA | ✅ | Redigida: papéis de Sully/Codey/Vera, sandboxing Docker, Skills restritas |
| Seção 4 — Setup Experimental | 🔶 | Estrutura pronta; hardware descrito como RTX 2050 (o hardware real é AMD RX 580) — **precisa correção** |
| Seção 5 — Resultados | ❌ | Existem apenas placeholders (`X%`) — **bloqueada por dados experimentais reais** |
| Seção 6 — Discussão | 🔶 | Esboço presente; Threats to Validity mencionadas mas não elaboradas com dados |
| Seção 7 — Conclusão | 🔶 | Esboço presente; precisa de amarração com os resultados finais |
| Keywords | ✅ | Definidas: *Multi-Agent Systems, Small Language Models, Software Engineering, Autonomous Agents, Democratization of AI* |

#### Template e Formatação

| Componente | Status | Detalhe |
|---|---|---|
| Template IEEE (IEEEtran) | ✅ | `main_article.tex` configurado com `\documentclass[10pt,journal,compsoc]{IEEEtran}` |
| Arquivo `references.bib` | ✅ | 24 referências formatadas no padrão IEEE, incluindo SWE-agent, SWE-smith, MAGIS, Liu et al. 2024 |
| Espaços para figuras | ✅ | 3 espaços declarados no LaTeX (Fig. 1: diagrama de sequência; Fig. 2: sandbox; Fig. 3: gráfico de resultados) |
| Autores e afiliações | ❌ | Comentados no `.tex` para double-blind — precisam ser preenchidos na versão final |

#### Pesquisa e Fundamentação

| Componente | Status | Detalhe |
|---|---|---|
| Posicionamento acadêmico | ✅ | Documentado em `liara_positioning.md` — quadrante local+sem fine-tuning identificado como inédito |
| Revisão da literatura | ✅ | 282 artigos do Scopus analisados (`gap_discovery_synthesis.md`); gaps identificados |
| Justificativa do design (SLMs + papéis restritos) | ✅ | Fundamentada em "Lost in the Middle" (Liu et al., 2024) — `bibtex_prelude.md` |
| PDFs de referência chave | ✅ | SWE-agent, SWE-smith, e outros em `artigos_referencia/` |
| Diagrama arquitetural | ✅ | Diagrama Mermaid completo em `liara_architecture.md` (Fase 0→1→2→3) |

#### Implementação Técnica (Código)

| Componente | Status | Detalhe |
|---|---|---|
| Orquestrador (`main_orchestrator.py`) | ✅ | 816 linhas, v4.4.3 — estável, com localização híbrida, fuzzy apply, rollback, contexto progressivo |
| Skill `file_editor` | ✅ | Implementada para o agente Codey |
| Skill `bash_executor` (Docker) | ✅ | Implementada para o agente Vera |
| Dataset SWE-bench Verified | ✅ | Script de download presente (`download_swebench.py`) |
| Ambiente Docker por issue | ✅ | Containerização isolada implementada e testada |
| Análise AST local (Fase 0) | ✅ | `build_ast_map`, `localize_from_traceback`, `extract_ast_function_scope` — sem LLM |
| Busca semântica por embeddings | ✅ | `find_relevant_files_by_embedding` via `nomic-embed-text` |

---

### Tarefas Restantes para o Artigo

> [!CAUTION]
> O **gargalo crítico** é a ausência de dados experimentais. Todas as tarefas abaixo dependem, direta ou indiretamente, da execução completa do benchmark.

#### 🔴 Bloco 1 — Execução Experimental (DESBLOQUEADOR PRINCIPAL)

- [ ] **Executar o benchmark completo** com Qwen2.5-Coder:14B no hardware do laboratório (AMD RX 580, 8GB VRAM)
  - Escala recomendada: mínimo 50 issues do SWE-bench Verified (atualmente só 5 foram rodadas)
  - Registrar: Pass@1 final, tempo médio por issue, erros frequentes por categoria
- [ ] **Registrar custo operacional** (tokens consumidos por issue, comparar com custo de API equivalente)
- [ ] **Executar com Llama 3.1 8B** para ter pelo menos 2 pontos de dados de modelos diferentes (tabela comparativa)
- [ ] Tabular os resultados: `configuração × modelo × Pass@1 × custo ($)`

#### 🟠 Bloco 2 — Escrita (depende do Bloco 1)

- [ ] **Preencher Seção 5 (Resultados):** substituir todos os `X%` pelos valores reais; gerar Figura 3 (gráfico custo vs. resolução)
- [ ] **Completar Seção 6 (Discussão):** elaborar ameaças à validade com dados concretos (limitações de VRAM, tamanho de amostra, viés do dataset)
- [ ] **Fechar a Conclusão** com contribuição quantificada (ex.: "LIARA resolve Y% das issues a $0.00 vs. $X do GPT-4")
- [ ] **Corrigir Seção 4:** alterar hardware de "RTX 2050 / 4GB" para "AMD RX 580 / 8GB" (inconsistência atual)
- [ ] Gerar Figura 1 (diagrama de sequência) e Figura 2 (sandbox) para incluir no LaTeX

#### 🟡 Bloco 3 — Submissão (depende do Bloco 2)

- [ ] **Anonimizar repositório GitHub** via serviço como *Anonymous GitHub* (exigência do double-blind review)
- [ ] **Preencher autores e afiliações** no `main_article.tex` (linhas comentadas)
- [ ] **Redigir Cover Letter** ao Editor-Chefe da IEEE TSE justificando urgência do tema
- [ ] Compilar PDF final e verificar formatação IEEE (duas colunas, 14–20 páginas)
- [ ] Submeter via portal **ScholarOne Manuscripts**

---

## Cenário 2: TCC (Trabalho de Conclusão de Curso)

### Componentes Existentes Aproveitáveis

Um TCC tem estrutura mais extensa que um artigo, mas tudo o que existe no repositório é diretamente reutilizável:

#### Fundamentação Teórica (Capítulo de Referencial Teórico)

| Componente disponível | Onde está | Como aproveitar |
|---|---|---|
| Síntese de 282 artigos do Scopus | `gap_discovery_synthesis.md` | Base do Referencial Teórico sobre SMA em ES |
| Análise de gaps de pesquisa | `gaps_agile_mas_legacy.md` | Justificativa da lacuna preenchida pelo trabalho |
| Referências formatadas (BibTeX) | `references.bib` (24 entradas) | Importar diretamente no template ABNT ou Overleaf |
| PDFs dos trabalhos relacionados chave | `artigos_referencia/` | Leitura e citação (SWE-agent, SWE-smith, MAGIS) |
| Fundamentação do design (Lost in the Middle) | `bibtex_prelude.md` | Seção teórica sobre limitações de SLMs |

#### Metodologia (Capítulo de Metodologia)

| Componente disponível | Onde está | Como aproveitar |
|---|---|---|
| Descrição completa da arquitetura LIARA | `main_article.tex` (Seção 3) + `system_design_slm_mas.md` | Capítulo de Metodologia completo |
| Prompts dos agentes (Sully, Codey, Vera) | `local_agents_prompts.md` | Subseção de implementação dos agentes |
| Diagrama de fluxo completo | `liara_architecture.md` (Mermaid) | Figura central da metodologia |
| Skills dos agentes | `openclaw_skills.md` | Descrição das ferramentas dos agentes |
| Configuração do ambiente DGX/Docker | `dgx_nemoclaw_config.md` | Subseção de infraestrutura experimental |
| Código-fonte do orquestrador | `main_orchestrator.py` | Anexo técnico + descrição de implementação |

#### Resultados Parciais

| Componente disponível | Onde está | Como aproveitar |
|---|---|---|
| Log de execução real (5 issues) | `resumo_nova_arquitetura.txt` | Primeiros resultados / análise qualitativa |
| Resultado Llama 3.1 8B: 0/5 (0%) | `liara_positioning.md` | Dado comparativo e análise de limitações |
| Changelog de evoluções arquiteturais | `changelog.md` | Histórico de decisões de design (metodologia evolutiva) |

---

### Tarefas Restantes para o TCC

> [!IMPORTANT]
> O TCC permite apresentar resultados parciais e análise qualitativa com maior profundidade narrativa. O gargalo experimental é o mesmo do artigo, mas o TCC tem mais tolerância a amostras menores.

#### 🔴 Bloco 1 — Estrutura e Normas do TCC

- [ ] **Definir template institucional** (ABNT — normas UFSC/UDESC/etc.) e configurar Overleaf ou editor LaTeX com o template correto
- [ ] Criar estrutura de capítulos padrão TCC:
  - Capa, folha de rosto, resumo/abstract, lista de figuras/tabelas, sumário
  - Capítulos: Introdução / Referencial Teórico / Metodologia / Resultados / Discussão / Conclusão / Referências / Anexos

#### 🟠 Bloco 2 — Escrita dos Capítulos (reuso + expansão do artigo)

- [ ] **Capítulo 1 — Introdução:** expandir a introdução do artigo com contextualização mais ampla (cenário de IA no Brasil, custo de API para startups, etc.); definir claramente objetivo geral e específicos; delimitar escopo do TCC
- [ ] **Capítulo 2 — Referencial Teórico:** expandir substancialmente além do artigo:
  - Subseção: Sistemas Multi-Agentes (conceitos, classificações, histórico)
  - Subseção: Large Language Models e Small Language Models (definições, benchmarks, comparações)
  - Subseção: Reparação Automática de Programas (APR — estado da arte, SWE-bench como padrão)
  - Subseção: Trabalhos Relacionados (SWE-agent, SWE-smith, MAGIS, OpenHands) — já existe base no repositório
- [ ] **Capítulo 3 — Metodologia:** reutilizar e expandir a Seção 3 do artigo; adicionar:
  - Descrição do ciclo de desenvolvimento (changelog como evidência)
  - Justificativa das escolhas de design (por que Ollama? por que Docker? por que 3 agentes?)
  - Protocolo completo de execução do benchmark (passos reprodutíveis)
- [ ] **Capítulo 4 — Resultados e Discussão:**
  - Com dados experimentais completos: tabela Pass@1 × custo × modelo
  - Com dados parciais disponíveis: análise qualitativa dos logs (`resumo_nova_arquitetura.txt`), padrões de falha, análise dos 5 casos executados
- [ ] **Capítulo 5 — Conclusão:** responder aos objetivos definidos na Introdução; contribuições; trabalhos futuros; limitações

#### 🟡 Bloco 3 — Experimentação (mesmo do Artigo, mas escala menor é aceitável)

- [ ] Executar benchmark com pelo menos **20–30 issues** do SWE-bench Verified (mínimo aceitável para TCC)
- [ ] Documentar erros e limitações encontradas com riqueza qualitativa (o TCC tolera e valoriza análise de falhas)
- [ ] Gerar tabelas e gráficos comparativos (matplotlib já está disponível no `requirements.txt`)

#### 🔵 Bloco 4 — Elementos Formais do TCC

- [ ] Redigir Resumo e Abstract (podem ser adaptados do artigo)
- [ ] Elaborar lista de figuras e tabelas
- [ ] Formatar referências no padrão ABNT (as 24 entradas do `.bib` precisarão ser convertidas de IEEE para ABNT)
- [ ] Incluir código relevante como Anexo (prompts dos agentes, fragmentos do orquestrador)
- [ ] Preparar apresentação (slides) para banca avaliadora

---

## Comparativo de Esforço Restante

| Dimensão | Artigo IEEE TSE | TCC |
|---|---|---|
| **Escrita pendente** | ~30% (Resultados, Discussão completa, Conclusão final) | ~55% (capítulos extensos de Referencial Teórico + Metodologia expandida) |
| **Dados experimentais necessários** | 50+ issues (escala alta) | 20–30 issues (escala menor aceitável) |
| **Prazo de revisão pós-submissão** | 3–6 meses (peer review double-blind) | Definido pela banca da instituição |
| **Risco de rejeição** | Alto (IEEE TSE é Qualis A1) | Baixo-médio (controlado pelo orientador) |
| **Reaproveita o que existe** | ~70% do repositório atual | ~80% do repositório atual |
| **Complexidade de formatação** | Moderada (IEEE IEEEtran já configurado) | Alta (ABNT tem mais elementos formais) |

> [!TIP]
> **Recomendação estratégica:** As duas saídas não são excludentes. O TCC pode ser concluído primeiro (com 20–30 issues), e o artigo submetido posteriormente com a escala completa de 50+ issues e os ajustes de formatação IEEE. O TCC serviria como etapa de validação e geração de dados para o artigo.

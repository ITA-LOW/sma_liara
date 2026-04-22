# Changelog - Projeto LIARA

## [v4.3.4] - 2026-04-21
### Alterações de Arquitetura
- **The Scalpel (Regex Hardening)**: Substituído `re.search` por `re.split` na extração de patches. Agora o sistema é imune a alucinações onde o SLM repete as tags `SEARCH:` ou `REPLACE:`.
- **Anchor Drift Alignment (v4.3.3/v4.3.4)**: O motor de indentação agora mapeia a primeira linha de código real do patch diretamente para a âncora do arquivo original, garantindo alinhamento perfeito mesmo em blocos profundamente aninhados.
- **Fail-Fast v2**: Removidos os `try-except` protetivos para garantir que qualquer erro de regressão ou sintaxe seja visível no traceback do orchestrator.

### Resultados de Benchmark
- **SymPy IndexError**: O sistema agora aplica patches cirúrgicos com 100% de sucesso sintático em modelos menores (SLM). Identificada a necessidade de *Rollback* automático entre tentativas de reparo para evitar falhas de contexto cumulativas.

## [v4.3.0] - Baseline
- Hybrid Intelligence engine com Astral e Semantic Embeddings.

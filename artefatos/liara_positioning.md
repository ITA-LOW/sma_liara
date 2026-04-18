# LIARA — Posicionamento Acadêmico (IEEE TSE)

## Referências Lidas

| Paper | Venue | Resultado principal |
|---|---|---|
| **SWE-agent** (Yang et al., arXiv:2405.15793) | NeurIPS 2024 | GPT-4 Turbo: 12.5% Pass@1. Llama 3 foi testado e descartado (8K contexto insuficiente). |
| **SWE-smith** (Yang et al., arXiv:2504.21798) | 2025 | Fine-tuning Qwen 2.5 32B com 5k trajetórias → 40.2% Pass@1. Custo: $1.360 em APIs. |

## O Espaço do LIARA

```
              | Com fine-tuning | Sem fine-tuning |
--------------+-----------------+-----------------|
API Cloud     | SWE-smith (40%) |  SWE-agent (12%)|
--------------+-----------------+-----------------|
Local/Grátis  |      ???        |    LIARA        |
```

**Ninguém publicou um estudo sistemático do quadrante local + sem fine-tuning com arquitetura multi-agente.**

## Contribuições Concretas do LIARA

1. **Arquitetura multi-agente de papéis discretos**: Sully (análise) → Codey (edição format-constrained) → Vera (verificação determinística). Hipótese testável: SLMs menores funcionam melhor com tarefas focadas.

2. **Verificação determinística (Vera programática)**: Substituir julgamento LLM por análise de saída de testes elimina fonte de ruído mensurável.

3. **Análise do custo-benefício de democratização**: Quantifica o trade-off Pass@1 × custo: GPT-4 ($$) vs Qwen 14B local ($0). **Essa tabela não existe na literatura**.

4. **Reprodutibilidade real**: Roda com `git clone` + `ollama pull` em hardware de consumidor (AMD RX 580, 8GB VRAM). Relevante para laboratórios sem recursos.

## Narrative do Artigo

> "LIARA não compete diretamente com SWE-smith em Pass@1. O LIARA estabelece a **linha de base do quadrante democratizado**: mostra o que é possível com modelos locais, zero custo de API, zero fine-tuning — e identifica os gargalos (tamanho do modelo, janela de contexto, precisão do patch) que, quando resolvidos, podem tornar APR local competitiva com soluções proprietárias."

## Resultados Experimentais (atualizar após o benchmark final)

| Configuração | Modelo | Pass@1 |
|---|---|---|
| LIARA v3.4.0 | Llama 3.1 8B | 0/5 (0%) |
| LIARA v3.4.0 | Qwen2.5-Coder 14B | **a medir** |

## Parâmetros do Benchmark

- Dataset: SWE-bench Verified (princeton-nlp/SWE-bench_Verified), seed=42
- Sample: 5 issues (sympy x3, django x2)
- Retries por issue: 2
- Hardware: Lab PC (AMD RX 580 8GB, 64GB RAM)
- Framework: LIARA v3.4.0 (Sully→Codey→Vera, fuzzy_apply_edit, retry guiado)

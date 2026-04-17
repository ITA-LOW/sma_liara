# Diretrizes de Submissão: IEEE TSE (Transactions on Software Engineering)

A **IEEE TSE** é indiscutivelmente a revista acadêmica mais prestigiosa do mundo em Engenharia de Software (Qualis A1 absoluto). Publicar nela exige um nível de rigor metodológico altíssimo.

Diferente de conferências, revistas como a TSE dão espaço para você contar a história completa. O artigo final terá cerca de **14 a 20 páginas** (formato IEEE de duas colunas).

## 1. O Pipeline de Submissão
1. **O Portal:** As submissões são feitas via **ScholarOne Manuscripts** (o portal oficial da IEEE).
2. **Double-Blind Review:** A avaliação é *Double-Blind* (cega dupla). Ou seja, quando enviarmos o PDF inicial, não podemos colocar seu nome, nem o da sua universidade. Até o repositório do GitHub (onde ficarão os scripts [main_orchestrator.py](file:///home/italo/%C3%81rea%20de%20Trabalho/artigo_carol/openclaw_swe_benchmark/local_execution/main_orchestrator.py) e os Prompts) precisará ser anonimizado (usaremos um serviço como o *Anonymous GitHub*).
3. **Cover Letter:** Precisaremos escrever uma Carta de Apresentação forte ao Editor-Chefe, justificando por que "SLMs no SWE-bench via OpenClaw" é um tema urgente para a comunidade de Engenharia de Software.
4. **Ciclo de Revisão:** O primeiro veredito (Major Revision, Minor Revision, Reject) costuma levar de **3 a 6 meses**.

## 2. A Estrutura do Nosso Artigo para a TSE

Para a TSE, nós usaremos a seguinte estrutura "vencedora":

*   **1. Introdução:** O problema do custo e privacidade em grandes LLMs comerciais (GPT-4) e a ascensão dos SLMs.
*   **2. Revisão de Literatura (Background):** 
    * O Fenômeno "Lost in the Middle".
    * O estado da arte do SWE-bench.
    * Lacunas (Onde entraremos: Orquestração local vs. Nuvem).
*   **3. Metodologia (O Framework OpenClaw):** 
    * O design arquitetural (Sully, Codey, Vera).
    * Restrição de ferramentas (Skills limitadas para não sobrecarregar SLMs).
    * Execução em ambiente isolado (NemoClaw/Docker no DGX).
*   **4. Estudo Empírico (Data & Setup):**
    * Como filtramos as 50 ou 100 *issues* do SWE-bench.
    * As métricas (Pass@k, Token Cost, Tempo de Execução).
*   **5. Resultados (Results):** Gráficos comparando nosso MAS com o GPT-4o e Claude 3.5.
*   **6. Discussão (Discussion):** 
    * Ameaças à Validade (Por que o modelo pode ter tido sorte?).
    * Implicações práticas para engenheiros e empresas (Privacidade/Custo).
*   **7. Conclusão.**

## Próximos Passos na Escrita
Como você já validou o "motor" localmente, o ideal agora é criarmos um documento LaTeX no **Overleaf** e eu começo a preencher as Seções 1 (Introdução) e 3 (Metodologia) enquanto você providencia as execuções reais no Lab.

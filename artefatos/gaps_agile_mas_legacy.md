# Gaps de Pesquisa: MAS Ágil vs. Sistemas Legados

Ao analisar o artigo de **Manish (2024)**, que propõe um framework MAS para desenvolvimento Ágil, identificamos lacunas significativas que podem ser exploradas para o seu artigo focado em **Legados**.

## Gap 1: "Arqueologia de Requisitos" (Reverse Engineering)
- **O que o artigo de 2024 diz:** Foca no fluxo *User Story -> Código*. Os agentes assumem que o requisito está claro.
- **A Lacuna:** No legado, o requisito "se perdeu". Existe um gap sobre como um MAS pode realizar a engenharia reversa de sistemas mal documentados para **recriar o backlog ágil** que o artigo de Manish assume como ponto de partida.

## Gap 2: Validação sob Incerteza (Black-Box Testing)
- **O que o artigo de 2024 diz:** Agentes verificadores validam se o código atende ao requisito.
- **A Lacuna:** Se o requisito original é desconhecido, a validação torna-se um problema de **paridade comportamental**. Como garantir que o MAS não "limpe" um comportamento que, embora pareça um bug, é uma regra de negócio crítica "enterrada" no legado?

## Gap 3: Papéis de Agentes para Refatoração Profunda
- **O que o artigo de 2024 diz:** Usa papéis genéricos (Developer, Manager).
- **A Lacuna:** Falta definir e testar papéis especializados em modernização, como o **"Analista de Impacto de Regressão"** ou o **"Tradutor de Padrões Arquiteturais"** (ex: migrar de um monolito para microserviços de forma incremental).

## Gap 4: Benchmarks de Modernização
- **O que o artigo de 2024 diz:** Avalia produtividade em tarefas novas.
- **A Lacuna:** Não existem benchmarks robustos para avaliar a eficácia de MAS em tarefas de **manutenção de longo prazo** em bases de código legadas reais (milhões de linhas).

---

### Por que isso é bom para o seu artigo?
Explorar essas lacunas permite que você pegue a base sólida do Manish (a ideia de agentes especializados trabalhando em ciclos ágeis) e a leve para um "terreno inexplorado" e de alto valor para a indústria: a **modernização autônoma**. 

Você estaria basicamente propondo um **"Agile Modernization Framework"** via MAS.

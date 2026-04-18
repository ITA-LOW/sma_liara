flowchart TD
    INPUT(["📥 Issue\n─────────────\nBug Report\nTest Patch\nRepository"])
    subgraph SETUP["⚙️ Setup"]
        S1["Clone Repo + Checkout Commit"]
        S2["Apply Test Patch"]
        S3["Start Docker Container"]
    end
    subgraph PHASE0["🔬 Fase 0 — Análise Estática (sem LLM)"]
        A1["AST Map\n(build_ast_map)\nfunc → arquivo"]
        A2["Embedding Search\n(nomic-embed-text)\nop. semântica"]
        A3["Error Pattern Matching\n12 heurísticas\nIndexError → hint, etc."]
        A4["Traceback Localization\nCandidatos via traceback"]
        A5["Repro Synthesis\nextrai código do bug report"]
    end
    subgraph PHASE1["🐞 Fase 1 — Reprodução do Bug"]
        B1["Executa testes no Docker"]
        B2{"Bug detectado?"}
    end
    subgraph PHASE2["🧠 Fase 2 — Sully (Arquiteto LLM)"]
        C1["Recebe: bug + hint + candidatos AST\n+ candidatos embedding + file list"]
        C2["Identifica\nFILE + FUNCTION"]
        C3[("💾 Salva estado JSON")]
    end
    subgraph PHASE3["✏️ Fase 3 — Loop Codey + Vera"]
        direction TB
        D1{"Tentativa\n1 / 2 / 3+"}
        CTX1["Contexto Nível 1\nAssinatura + docstring"]
        CTX2["Contexto Nível 2\nCorpo completo"]
        CTX3["Contexto Nível 3\nFunção + entorno"]
        D2["Codey gera\nSEARCH/REPLACE"]
        D3["fuzzy_apply_edit\n(exact → whitespace-tolerant)"]
        D4{"Patch\naplicado?"}
        D5["ast.parse\nvalidação estática\n(sem Docker)"]
        D6{"Sintaxe\nOK?"}
        D7["Executa testes\nno Docker"]
        D8{"Testes\npassam?"}
        VERA["🔍 Vera extrai\nfalha relevante"]
        ERR[("💾 Salva erro\nno JSON")]
    end
    OK(["✅ RESOLVIDA\nSalva estado"])
    FAIL(["❌ REJEITADA\nSalva estado"])
    INPUT --> SETUP
    SETUP --> PHASE0
    A1 <--> A2
    A1 --> A4
    PHASE0 --> PHASE1
    B1 --> B2
    B2 -->|Não| OK
    B2 -->|Sim| PHASE2
    C1 --> C2 --> C3
    PHASE2 --> PHASE3
    D1 -->|"attempt=1"| CTX1
    D1 -->|"attempt=2"| CTX2
    D1 -->|"attempt=3+"| CTX3
    CTX1 & CTX2 & CTX3 --> D2
    D2 --> D3 --> D4
    D4 -->|Não| ERR
    D4 -->|Sim| D5 --> D6
    D6 -->|Não| ERR
    D6 -->|Sim| D7 --> D8
    D8 -->|Sim| OK
    D8 -->|Não| VERA --> ERR
    ERR -->|"retries < MAX"| D1
    ERR -->|"retries = MAX"| FAIL
    style PHASE0 fill:#e8f4fd,stroke:#2196F3
    style PHASE2 fill:#fff3e0,stroke:#FF9800
    style PHASE3 fill:#f3e5f5,stroke:#9C27B0
    style OK fill:#e8f5e9,stroke:#4CAF50
    style FAIL fill:#ffebee,stroke:#F44336
    style INPUT fill:#e3f2fd,stroke:#1565C0
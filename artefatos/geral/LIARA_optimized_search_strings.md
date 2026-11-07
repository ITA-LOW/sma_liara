# LIARA — Optimized Academic Search Strings

## Research positioning

LIARA is best indexed around the intersection of automated program repair, LLM-based software engineering agents, multi-agent systems, small/local language models, and orchestration. Federated learning is a relevant adjacent literature stream for privacy-preserving decentralized software-engineering models, but it is not equivalent to LIARA's architecture because LIARA performs local inference and does not rely on federated training.

## 1. Core LIARA query — highest precision

("automated program repair" OR "program repair" OR "software maintenance" OR "bug fixing")
AND
("large language model" OR LLM OR "language model")
AND
("small language model" OR SLM OR "small language models" OR "local language model" OR "local LLM")
AND
("multi-agent system" OR "multi-agent" OR "LLM-based agent" OR "software engineering agent" OR "coding agent")
AND
("agent orchestration" OR orchestration OR coordination OR collaboration OR "role specialization")
AND
(local OR "on-premises" OR "on-device" OR edge OR decentralized OR decentralised)
NOT
("natural language generation" OR chatbot OR healthcare OR finance)

**Use:** primary search for the LIARA research niche.

For LeapSpace:
("automated program repair" OR "program repair" OR "bug fixing") AND ("large language model" OR LLM) AND ("small language model" OR SLM OR "local LLM") AND ("multi-agent system" OR "software engineering agent" OR "coding agent") AND (orchestration OR coordination OR "role specialization") AND (local OR "on-device" OR edge OR decentralized)

## 2. Decentralized/local/edge SLM orchestration — architecture-focused

("software engineering" OR "software development" OR "automated program repair")
AND
("small language model" OR SLM OR "compact language model" OR "local LLM" OR "open-source language model")
AND
("multi-agent" OR "multi-agent architecture" OR "agentic system" OR "agent-based system")
AND
(orchestration OR routing OR delegation OR coordination OR "task decomposition" OR "role specialization")
AND
("local inference" OR "on-device inference" OR "edge AI" OR "edge inference" OR "private deployment" OR "privacy-preserving" OR decentralized OR decentralised)
NOT
(training OR pretraining OR "foundation model training")

**Use:** targets the article-title concepts "decentralizing LLM capabilities" and "small language model orchestration", while emphasizing local inference rather than model training.

## 3. Multi-agent APR + deterministic/tool-based validation — mechanism-focused

("automated program repair" OR APR OR "bug fixing" OR "software maintenance")
AND
("LLM-based agent" OR "coding agent" OR "software engineering agent" OR "multi-agent system")
AND
("small language model" OR SLM OR "code language model" OR "code LLM")
AND
("static analysis" OR AST OR "abstract syntax tree" OR "semantic search" OR embeddings OR traceback)
AND
("test-based validation" OR "test oracle" OR "automated validation" OR "deterministic validation" OR "patch validation" OR rollback)
AND
(orchestration OR coordination OR "progressive context" OR "task specialization")
NOT
("human-in-the-loop" OR crowdsourcing)

**Use:** finds work closest to LIARA's technical implementation and its methodological contribution, not merely papers that mention LLMs in software engineering.

## 4. Federated learning / decentralized SE models — adjacent research stream

("software engineering" OR "software maintenance" OR "program repair" OR "code generation" OR "code summarization")
AND
("large language model" OR LLM OR "small language model" OR SLM OR "code language model")
AND
("federated learning" OR "federated fine-tuning" OR "federated LLM" OR "federated language model")
AND
("data privacy" OR "privacy-preserving" OR decentralized OR decentralised OR "distributed data" OR "proprietary code")
AND
("multi-agent" OR agent OR orchestration OR collaboration OR distributed)
NOT
("medical imaging" OR healthcare OR IoT OR recommender)

**Use:** deliberately broadens the review toward FL, privacy, and decentralized model development. Treat results as related work unless they also involve local inference, SLM orchestration, or agent-based SE automation.

## 5. Broad discovery / state-of-the-art mapping

(("LLM-based agent" OR "AI agent" OR "coding agent" OR "software engineering agent" OR "multi-agent system")
AND
("software engineering" OR "software development lifecycle" OR SDLC OR "program repair" OR debugging OR testing))
AND
(("small language model" OR SLM OR "local LLM" OR "open-source LLM" OR "code LLM")
OR
("federated learning" OR "federated fine-tuning" OR "edge AI" OR "on-device AI" OR "distributed inference"))
AND
(orchestration OR coordination OR delegation OR routing OR "task decomposition" OR specialization OR "agent collaboration")

**Use:** exploratory mapping when you want to discover terminology and then tighten the final systematic-review query.

## Database adaptation notes

### Scopus
Use the strings inside `TITLE-ABS-KEY(...)` and keep phrase searching. Example wrapper:
`TITLE-ABS-KEY(("automated program repair" OR ... ) AND (...))`

### Web of Science
Use `TS=(...)` for Topic search. Keep the quoted phrases and Boolean structure.

### IEEE Xplore
Use Advanced Search with metadata fields such as `Abstract`, `Index Terms`, and `Document Title`. IEEE's parser can be more restrictive, so split very large queries into thematic passes when needed.

### ACM Digital Library
Use Advanced Search and apply Boolean logic across Title/Abstract/Keywords where possible. ACM searches often benefit from several narrower queries rather than a single extremely long expression.

## Recommended search strategy

Run Query 1 first for the high-precision core literature. Run Query 2 to capture the decentralization/local/edge dimension. Run Query 4 separately as an adjacent FL track. Use Query 5 only for discovery and terminology harvesting; do not use its broader results directly as the final inclusion set.

## Evidence behind the vocabulary

Recent literature explicitly frames LLM-based multi-agent systems as a software-engineering research area, emphasizing collaboration, specialization, autonomy, scalability, and orchestration. ACM TOSEM published a 2025 literature review of LLM-based multi-agent systems for software engineering. A separate 2025 survey distinguishes LLMs from LLM-based agents across requirements, code generation, autonomous decision-making, testing, and maintenance. Recent APR research also treats LLM agents and automated program repair as a fast-moving area, and 2025 work has evaluated 7B–33B open models for APR, finding that model specialization can outperform larger general-purpose models.

Federated learning is relevant to the decentralization/privacy literature but represents a different mechanism from LIARA. A 2025 ACM TOSEM study investigated federated fine-tuning for LLM-based program repair, while another 2025 ACM TOSEM position paper framed federated learning as a way to collaboratively develop open-source AI-based software-engineering tools without centralizing proprietary code. Therefore FL is valuable for related-work retrieval but should not dominate the core LIARA query.

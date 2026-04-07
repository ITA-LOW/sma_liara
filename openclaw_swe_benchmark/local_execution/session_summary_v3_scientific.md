# LIARA: Scientific Session Summary (2026-04-06)

## 🏁 Milestones Achieved
1.  **Scientific Orchestrator (v3.2.1):** Transitioned from "mock" scripts to a rigorous benchmark using `SWE-bench Verified` repository clones.
2.  **Reproduction Engine:** Successfully implemented a "Sensor" that applies a `test_patch` and verifies bug reproduction (`REPRO: BUG DETECTADO`) before any repair attempt.
3.  **Docker Sandbox:** Automated environment setup with `pip install -e .` on a per-issue basis, ensuring total isolation.
4.  **Discovery of SLM Limitations:** Identified that Llama-3-8B suffers from "Output Laziness" (truncating full files), leading to the development of the **Surgeon Strategy (Search & Replace)**.
5.  **Robust Dialogue Logging:** Implemented `agent_dialogue_*.txt` to capture every word from the agents, providing qualitative data for the IEEE TSE article even when the quantitative repair fails.

## 🚧 Challenges & "The Last Mile"
-   **Model Instruction Following:** The 8B model occasionally fails to follow the strict `SEARCH:/REPLACE:` keywords, even in the updated Surgeon v3.2.1.
-   **Path Mapping:** Resolved issues where agents provided container-side paths (`/app/...`) versus host-side paths.

## 📅 Next Session - "The Data Collection Phase"
1.  **Prompt Refinement:** Tweak the Codey prompt to be "Format-Obsessive" (Few-shot prompting for the Search/Replace blocks).
2.  **Parser Optimization:** Make the regex for `SEARCH` and `REPLACE` case-insensitive and even more tolerant of chatter.
3.  **Full Benchmark Run:** Once parsing is 100% stable, run the 5-issue loop and collect the final JSON results for Table 1 of the article.

---
**Status:** Infrastructure 100% | Methodology 100% | Results Traceability 100% | **Model Success Rate: Pending (Prompt Tuning)**

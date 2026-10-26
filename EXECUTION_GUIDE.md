# LIARA: Setup and Execution Guide

This guide details all prerequisites, configuration options, and steps required to run the **LIARA** (*Lean Isolated Agents for Repair Automation*) multi-agent benchmark on any machine (such as a university or lab workstation).

---

## 1. Prerequisites

LIARA orchestrates multiple SLM agents (Sully, Codey, Vera) that generate code patches and execute test suites in isolated sandbox environments. It requires the following host components:

### A. Docker Engine
Docker is required because tests are executed in isolated containers to prevent environment corruption and capture reproducible test results.

1. **Verify or install Docker Engine**:
   ```bash
   sudo apt update
   sudo apt install -y docker.io
   ```
2. **Start and enable Docker service**:
   ```bash
   sudo systemctl enable --now docker
   ```
3. **Grant non-root user permissions** (required so Python can invoke `docker` without `sudo`):
   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```
4. **Pre-pull required base images** (avoids timeouts on the first run):
   ```bash
   docker pull python:3.9-slim
   docker pull alpine
   ```

---

### B. Ollama (Local LLM & Embedding Server)
LIARA communicates with Ollama locally via its REST API (`http://localhost:11434`).

1. **Install Ollama** (if not installed):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. **Ensure Ollama service is running**:
   ```bash
   ollama serve
   ```
3. **Download required models**:
   ```bash
   # Primary code reasoning & repair model:
   ollama pull llama3.1
   # (Alternative tested model: ollama pull qwen3.5:9b)

   # Semantic search embedding model (mandatory for AST/embedding hybrid retrieval):
   ollama pull nomic-embed-text
   ```

---

### C. Python Environment & Dependencies
LIARA requires Python 3.9+.

1. **Create and activate a virtual environment (recommended)**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. **Install project dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   *(Ensure `datasets` is installed if you plan to download or regenerate SWE-bench samples).*

3. **Ensure Git is installed on the host**:
   ```bash
   sudo apt install -y git
   ```

---

## 2. Pre-flight Check (Sanity Check)

Before running actual benchmarks, run the sanity check script to verify connectivity to Docker, Ollama, and bash execution inside containers:

```bash
cd openclaw_swe_benchmark/local_execution
python3 sanity_check.py
```

Expected output confirms:
- `[1/3] Docker está operacional.`
- `[2/3] Ollama respondeu: SUCCESS`
- `[3/3] Skill de Bash no Docker operacional.`
- `=== TUDO PRONTO PARA O BENCHMARK REAL ===`

---

## 3. Running the Benchmark

> [!IMPORTANT]
> **Working Directory:** You **must** be inside `openclaw_swe_benchmark/local_execution` when executing `main_orchestrator.py`. The script uses relative imports (`from skills...`) and relative storage paths (`data/`, `repos/`).

### Recommended Run (Small Sample for Testing)
By default, the benchmark script targets 300 instances (`data/swebench_sample_300.json`), which takes days to complete. For test runs, use the 5-issue or 50-issue sample:

```bash
cd openclaw_swe_benchmark/local_execution

LIARA_MODEL=llama3.1 \
LIARA_SAMPLE=data/swebench_sample_5.json \
LIARA_RETRIES=2 \
python3 main_orchestrator.py
```

### Environment Configuration Variables

| Variable | Default Value | Description |
|---|---|---|
| `LIARA_MODEL` | `llama3.1` | Ollama model name (e.g., `llama3.1`, `qwen2.5-coder:14b`). |
| `LIARA_SAMPLE` | `data/swebench_sample_300.json` | Path to JSON dataset (`data/swebench_sample_5.json` or `data/swebench_sample_50.json`). |
| `LIARA_RETRIES` | `2` | Maximum retry attempts per issue when tests fail. |
| `LIARA_MAX_FUNC_LINES` | `420` | Maximum lines of context passed from AST function scope. |
| `LIARA_NUM_CTX` | *(Ollama default)* | Ollama context window limit (e.g., `8192` or `16384`). |
| `LIARA_NUM_PREDICT` | *(Ollama default)* | Maximum token limit for Ollama response generation. |

---

## 4. Generating Custom SWE-bench Verified Samples

To generate new reproducible sample sets (uses seed 42):

```bash
cd openclaw_swe_benchmark/local_execution
python3 download_swebench.py --n 10
```
This generates `data/swebench_sample_10.json`.

---

## 5. Output Artifacts & Monitoring

* **Execution Dialogue Logs:** Stored in `openclaw_swe_benchmark/local_execution/data/agent_dialogue_<date>.txt`.
* **Instance States & Patches:** Saved individually as `openclaw_swe_benchmark/local_execution/data/state_<instance_id>.json`.
* **Cloned Repositories:** Downloaded locally in `openclaw_swe_benchmark/local_execution/repos/`.

---

## 6. Maintenance & Troubleshooting

### Clean Orphaned Docker Containers
If a run is interrupted (e.g. `Ctrl+C`), orphaned benchmark containers may remain:
```bash
docker rm -f $(docker ps -a -q --filter "name=liara-") 2>/dev/null || true
```

### Check Resolved Instances
```bash
grep -rn '"resolved": true' openclaw_swe_benchmark/local_execution/data/
```

### Fix Repository Permissions
Containers run as root inside Docker and may create root-owned files in `repos/`. If git fails with permission errors:
```bash
sudo chown -R $USER:$USER openclaw_swe_benchmark/local_execution/repos/
```

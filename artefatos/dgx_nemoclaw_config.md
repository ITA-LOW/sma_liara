# NemoClaw Deployment Strategy (NVIDIA DGX Cluster)

This document outlines how we will take the local OpenClaw agents we designed and deploy them onto the NVIDIA DGX cluster securely using NemoClaw. 

## 1. Why NemoClaw on DGX?
When running on the DGX cluster, we want to maximize parallel execution (to solve multiple SWE-bench issues simultaneously) while ensuring the agents cannot execute malicious code that escapes their sandbox. NemoClaw provides the `OpenShell Runtime` specifically for this type of isolated, GPU-accelerated execution.

## 2. Directory Structure on the Cluster
When you move the project to the lab's cluster, the folder structure will look like this:
```text
/openclaw_swe_benchmark/dgx_execution/
├── agents/
│   ├── Sully.yaml      (Agent profile & prompt)
│   ├── Codey.yaml      (Agent profile & prompt)
│   └── Vera.yaml       (Agent profile & prompt)
├── skills/             (OpenClaw skills like FileReader, BashExecutor)
└── nemoclaw_config.yaml (The main deployment blueprint)
```

## 3. The `nemoclaw_config.yaml` Blueprint
This is the heart of the cluster deployment. It tells the DGX how to allocate GPUs (e.g., loading a 70B model or multiple 8B models) and sets the strict sandbox rules for the codebase.

```yaml
# nemoclaw_config.yaml
version: "1.0"
runtime: "openshell-sandbox"

models:
  - name: "llama-3-8b-instruct"
    backend: "nemotron"     # NVIDIA's optimized runtime
    vram_allocation: "16GB" # Reserve VRAM on the DGX
    instances: 3            # One for each agent to run in parallel

agents:
  architect:
    enabled: true
    config_path: "./agents/Sully.yaml"
    model: "llama-3-8b-instruct"
    sandbox_policy: "read-only" # Sully can only read the repo, not edit.

  coder:
    enabled: true
    config_path: "./agents/Codey.yaml"
    model: "llama-3-8b-instruct"
    sandbox_policy: "read-write" 
    allowed_paths: ["/workspace/swe-bench-repo/"] # Strict isolation

  qa:
    enabled: true
    config_path: "./agents/Vera.yaml"
    model: "llama-3-8b-instruct"
    sandbox_policy: "execute-only"
    allowed_commands: ["pytest", "unittest", "make test"] # Vera cannot delete the OS.

# SWE-bench Integration
environment:
  docker_image: "sweagent/swe-bench:latest"
  mounts:
    - src: "./swe-bench-repo"
      dst: "/workspace"
```

## 4. Next Technical Steps
With this configuration drafted, our theoretical and structural planning is effectively complete. The next physical step requires you to be in front of the lab computer or your local PC to actually install Ollama/OpenClaw and run a "Hello World" test with the agents.

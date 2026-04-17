import os
import subprocess
import json
import sys

# Adiciona o path para encontrar as skills
sys.path.append(os.getcwd())

from skills.bash_executor.docker_qa import run_in_docker, check_container_exists

def run_sanity_check():
    print("=== LIARA SANITY CHECK ===")
    
    # 1. Verificar Docker
    print("[1/3] Verificando Docker...")
    try:
        subprocess.run(["docker", "ps"], check=True, capture_output=True)
        print(" -> Docker está operacional.")
    except Exception as e:
        print(f" -> [ERRO] Docker não responde: {e}")
        return

    # 2. Verificar Ollama + Llama3
    print("[2/3] Verificando Ollama (Llama3)...")
    OLLAMA_URL = "http://localhost:11434/api/chat"
    data = {
        "model": "llama3.1",
        "messages": [{"role": "user", "content": "Respond with the word SUCCESS."}],
        "stream": False
    }
    import urllib.request
    try:
        req = urllib.request.Request(OLLAMA_URL, json.dumps(data).encode('utf-8'), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(f" -> Ollama respondeu: {result['message']['content']}")
    except Exception as e:
        print(f" -> [ERRO] Falha ao falar com Ollama: {e}")
        return

    # 3. Verificar Skill de Bash no Docker
    print("[3/3] Verificando Skill de Bash no Docker (Container real)...")
    container_name = "liara-sanity-check"
    try:
        # Sobe um container ultra-leve (Alpine)
        os.system(f"docker run -d --name {container_name} alpine tail -f /dev/null")
        
        # Tenta executar um ls via skill
        output = run_in_docker(container_name, "ls /")
        print(f" -> Resultado da Vera no Docker:\n{output}")
        
        # Cleanup
        os.system(f"docker rm -f {container_name}")
        print(" -> Limpeza concluída.")
    except Exception as e:
        print(f" -> [ERRO] Falha no ciclo do Docker: {e}")
        return

    print("=== TUDO PRONTO PARA O BENCHMARK REAL ===")

if __name__ == "__main__":
    run_sanity_check()

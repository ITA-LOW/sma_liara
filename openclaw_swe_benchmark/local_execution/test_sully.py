import json
import urllib.request
import urllib.error

# Configuração da API local do Ollama
url = "http://localhost:11434/api/chat"

# O System Prompt que escrevemos para o Sully (O Arquiteto)
sully_prompt = """
You are Sully, a senior Software Architect focused on resolving bugs reported in GitHub issues.
Your sole function is to read the issue description and the current source code of the affected files.

DO NOT write complete source code.
Your output MUST be strictly a bulleted step-by-step plan describing the root cause of the problem and the logic that needs to be changed.
Use clear and direct language.
"""

# Simulando uma issue fictícia do GitHub para o teste
issue_simulada = """
Title: Bug - The login button does not navigate to the dashboard when clicked.
Description: When a user clicks the 'Login' button on the landing page, the terminal logs 'Authentication successful' but the page remains on the login screen. It seems the router object is not pushing the new path correctly.
"""

data = {
    "model": "phi3",
    "messages": [
        {"role": "system", "content": sully_prompt},
        {"role": "user", "content": f"Please analyze this issue and generate a plan:\n\n{issue_simulada}"}
    ],
    "stream": False # Mantemos falso para receber a resposta de uma só vez
}

print("Enviando o problema para o Sully (Phi-3) analisar. Aguardando raciocínio...\n")

req = urllib.request.Request(url, json.dumps(data).encode('utf-8'), {'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode())
        print("====== RESPOSTA DO SULLY ======")
        print(result['message']['content'])
        print("===============================\n")
except urllib.error.URLError as e:
    print(f"Erro ao conectar com o Ollama: {e.reason}")
    print("O Ollama está rodando em segundo plano? Tente executar 'ollama serve' no terminal.")

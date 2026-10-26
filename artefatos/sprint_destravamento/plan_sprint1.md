 Investigating potential causes for test failures by examining system logs for out-of-memory errors and resource exhaustion...
  Não é apenas o agent_dialogue e os state_*.json. Quando uma execução do LIARA roda no computador hospedeiro, ela interage
  com múltiplas camadas: código do projeto, Docker, Ollama, Git e o próprio sistema operacional.

  Se nenhuma issue passou, o problema pode estar tanto na lógica dos agentes (Sully errando arquivo, Codey errando patch)
  quanto na infraestrutura de execução (ex: o container Docker não ter as dependências C/Python necessárias e os testes
  quebrarem por ModuleNotFoundError antes mesmo de testar o bug).

  Abaixo está o mapa completo de tudo o que você pode e deve investigar na máquina onde o teste foi executado, dividido por
  camada:
  ──────
  ### 1. Artefatos Diretos do LIARA (na pasta do projeto)

  Localização: openclaw_swe_benchmark/local_execution/

  #### A. Logs de Diálogo (data/agent_dialogue_*.txt)

  Este é o log mais detalhado de raciocínio:

  • Sully (Arquiteto): Veja se o JSON retornado foi válido, se ele tentou sugerir arquivos de teste (e se o Anti-Leakage
  rejeitou) ou se ele escolheu um arquivo de produção que realmente continha o bug.
  • Codey (Coder): Veja os blocos SEARCH: e REPLACE:. Ele gerou alucinações de linhas que não existiam? Ele cortou o código
  no meio?
  • Vera (QA / Testes): Veja o retorno real do comando de teste executado no Docker. O teste falhou porque o bug não foi
  corrigido, ou porque deu erro de ambiente (ex: ModuleNotFoundError, Command not found, erro de compilação C)?
  • Embeddings: Verifique se as mensagens do [EMB] indicam que o nomic-embed-text respondeu ou se deu timeout/offline.

  #### B. Arquivos de Estado (data/state_<instance_id>.json)

  Cada issue gera seu arquivo com o histórico de tentativas. Você pode inspecionar:

  • "errors": Uma lista com os erros exatos de cada tentativa (ex: "Patch failed: ERROR: Patch não encontrado" ou o traceback
  do teste).
  • "sully_file" e "sully_function": O que foi diagnosticado pelo Sully/AST.
  • Dica de análise em lote: No terminal da máquina, rode este script rápido para ver o resumo dos motivos de falha de todas
  as issues de uma vez:
    python3 -c "
    import glob, json
    files = glob.glob('data/state_*.json')
    print(f'Total de estados: {len(files)}')
    for f in files:
        with open(f) as fp:
            d = json.load(fp)
            name = f.replace('data/state_', '').replace('.json', '')
            last_err = d.get('errors', [{}])[-1].get('error', 'Sem erro registrado')[:120] if d.get('errors') else 'Nenhum'
            print(f'[{d.get(\"resolved\")}] {name} | Sully: {d.get(\"sully_file\")} | Ultimo erro: {last_err.strip()}')
    "


  #### C. Diretório de Repositórios Clonados (repos/)

  O orquestrador clona os repositórios em repos/<repo_name>:

  • Patches de Teste originais: Arquivos repos/<instance_id>.patch contêm os testes unitários do SWE-bench que foram
  aplicados para aquela issue. Você pode ler esse .patch para entender o que o teste realmente esperava que o código fizesse.
  • Estado Git dos repositórios: Entre em um repositório clonado (ex: cd repos/django) e execute:
    git status
    git diff
  Verifique se o rollback deixou lixo de compilação (.pyc, pastas de build, cache de teste) ou se a árvore está limpa.
  ──────
  ### 2. Camada Docker (Sandbox dos Testes) — Ponto Crítico de Falha!

  No arquivo main_orchestrator.py:640-647, o ambiente é instanciado com python:3.9-slim:

    docker run -d --name container_name -v {repo_path}:/app python:3.9-slim ...
    pip install -e . -q
    pip install pytest pytest-django ...

  Muitos repositórios do SWE-bench (como Django, Sympy, Astropy, Scikit-learn) exigem bibliotecas de sistema C/C++ (como gcc,
  libpq-dev, gfortran, libopenblas-dev) ou versões diferentes do Python. Como o comando usa -q (quiet), se a instalação das
  dependências falhar, o container continua rodando e todos os testes falham imediatamente com erro de importação, fazendo
  com que 0 issues passem!

  O que investigar no Docker:

  1. Containers órfãos ou parados:
    docker ps -a --filter "name=liara-"

  2. Logs de containers que não fecharam ou quebraram:
    docker logs <nome_do_container>

  3. Reprodução interativa de ambiente (Teste Diagnóstico):
  Pegue um repositório que falhou e suba o container manualmente para ver o que acontece ao rodar o teste:
    cd repos/<nome_do_repo>
    docker run --rm -it -v $(pwd):/app -w /app python:3.9-slim bash
    # Dentro do container:
    pip install -e .
    # Execute o comando de teste da issue (ex: pytest ... ou ./tests/runtests.py ...)
  Se aqui você vir ModuleNotFoundError ou erro de compilação, o gargalo das 0 issues está na imagem base do Docker e não nos
  agentes LLM.
  4. Espaço em disco do Docker:
    docker system df
  (Se o Docker atingir 100% de uso de disco, comandos de teste silenciosamente retornam código de erro diferente de zero).
  ──────
  ### 3. Camada do Ollama (LLM & Embeddings)

  O orquestrador faz chamadas HTTP para http://localhost:11434.

  O que investigar:

  1. Logs do Servidor Ollama:
      • Se rodou via systemd:
        journalctl -u ollama -e --no-pager -n 100

      • Se rodou no terminal via ollama serve: veja o terminal de log ou ~/.ollama/logs/server.log.
  2. Estouro de Janela de Contexto (num_ctx):
      • O Ollama usa por padrão 2048 tokens se a variável LIARA_NUM_CTX não for passada no ambiente.
      • Funções grandes de AST + traceback + prompt excedem facilmente 2048 tokens. Quando isso acontece, o Ollama trunca o
      prompt no início ou gera saídas sem sentido. Verifique se nos logs do Ollama há avisos de contexto ou truncamento.
  3. Modelos realmente carregados na memória:
    ollama list
    ollama ps
  Confirme se o modelo carregado foi exatamente o esperado (ex: llama3.1:8b ou qwen2.5-coder:14b) e se o nomic-embed-text
  estava presente.
  4. Despejo para CPU (VRAM insuficiente):
  Se o Ollama não tiver VRAM suficiente, ele faz offload para CPU/RAM, gerando lentidão extrema ou timeouts.
  ──────
  ### 4. Camada do Sistema Operacional (Hardware e Processos)

  1. OOM-Killer do Linux (Falta de Memória RAM):
  Rodar LLMs locais junto com containers Docker compilando dependências pode acionar o killer de memória do Linux.
    dmesg -T | grep -i -E "oom|killed"
  Se algum processo python, dockerd ou ollama_runner tiver sido morto pelo kernel, isso aparecerá aqui.
  2. Espaço livre em disco:
    df -h
  Clonar 5 a 50 repositórios do SWE-bench e gerar builds consome dezenas de gigabytes rapidamente.
  3. Histórico de Comandos e Variáveis de Ambiente:
  Verifique como o benchmark foi invocado:
    history | grep main_orchestrator.py
    # ou
    cat ~/.bash_history | grep -E "LIARA_|main_orchestrator"
  Verifique se as variáveis LIARA_MODEL, LIARA_SAMPLE, LIARA_NUM_CTX e LIARA_RETRIES foram configuradas conforme planejado.
  ──────
  ### Resumo do Roteiro de Debug Recomendado

  1. Comece pelos state_*.json: Rode o script de sumarização para agrupar as causas de erro mais comuns.
  2. Abra o agent_dialogue_*.txt e procure por uma issue específica para ver se os testes da Vera falharam por asserção do
  bug ou por falta de biblioteca/ambiente.
  3. Valide a sandbox Docker: Suba um container manual de teste em um dos repositórios para garantir que o comando de teste
  realmente consegue rodar isolado na imagem python:3.9-slim.

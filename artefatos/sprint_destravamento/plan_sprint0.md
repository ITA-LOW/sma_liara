As modificações do Sprint de Destravamento listadas no arquivo
  CONTEXTO_PROJETO.md foram implementadas e validadas em
  main_orchestrator.py.
  
  ### Resumo das Implementações
  #### 🛡️ Tarefa 1: Blindagem Anti-Leakage do Sully (Fase 1.1)

  • Funções de Sanitização: Implementadas as funções
  main_orchestrator.py:109-142 e main_orchestrator.py:144-146 para filtrar
  caminhos contendo diretórios de teste (/test/, /tests/, /testing/) e
  arquivos de teste (test_*.py, *_test.py, tests.py), evitando falsos
  positivos com termos comuns como fastest ou contest.
  • Filtragem de Candidatos Estáticos: Mapeamentos em
  main_orchestrator.py:488-506, main_orchestrator.py:508-536 e
  main_orchestrator.py:544-564 agora filtram estritamente arquivos de teste.
  • Contexto e Prompt do Sully:
      • O prompt do Sully impõe a regra estrita: STRICT ANTI-LEAKAGE RULE:
      NEVER target test files.
      • Funções de teste identificadas no traceback são suprimidas de
      func_hints para evitar induzir o Sully ao erro.
  • Validação de Retorno & Fallback AST: Se o modelo sugerir um arquivo de
  teste, a resposta é rejeitada, emitindo retry com alerta. Se o modelo
  persistir ou falhar, o orquestrador aciona fallback automático
  determinístico para o primeiro candidato de produção do AST.
  
  #### 🔄 Tarefa 2: Rollback Atômico Determinístico (Fase 1.3)

  • Validação com git status: A função main_orchestrator.py:293-307 executa
  git checkout -- <file> e valida via git status --porcelain -- <file>. Se
  ainda houver alterações pendentes, força checkout -f.
  • Rollback no Início de Cada Retry: No início de cada tentativa (attempt >
  1), o orquestrador invoca main_orchestrator.py:874-890, verifica se a
  árvore de trabalho está 100% limpa e recarrega o conteúdo original com
  read_file(target_abs).
  • Rollback Imediato em Falhas: Se o patch falhar na aplicação, na validação
  de sintaxe ou na execução dos testes do Docker (Vera), rollback_file é
  disparado imediatamente.
  
  #### ⚡ Tarefa 3: Hardening do Patcher do Codey — "The Scalpel" (Fase 1.2)

  • Normalização CRLF/LF: main_orchestrator.py:182-291 e
  main_orchestrator.py:173-180 normalizam \r\n e \r para \n tanto no conteúdo
  do arquivo quanto nos blocos SEARCH e REPLACE.
  • Tolerância a Drift de Indentação: O "The Scalpel" preserva a estrutura de
  indentação relativa (indent_delta), permitindo casar blocos de código mesmo
  quando o modelo altera a indentação global do trecho.
  • Isolamento de Cercas de Código: A função main_orchestrator.py:309-315
  descarta automaticamente cercas markdown e qualquer comentário/chatter pós-
  código gerado pelo modelo.
  • Pré-Validação Sintática em Memória: Antes de persistir qualquer alteração
  no disco ou invocar o Docker, main_orchestrator.py:156-171 executa ast.
  parse() na string em memória. Se houver SyntaxError, o patch é rejeitado
  sem custo de overhead do container Docker e o erro é repassado ao Codey
  para a próxima tentativa.
  
  ### Testes e Validação Empírica

  Executamos uma suíte de testes de integração cobrindo:

  1. Anti-Leakage: Detecção precisa de caminhos de teste versus módulos de
  produção com nomes similares (src/fastest_algo.py, src/contest.py).
  2. The Scalpel: Tolerância a CRLF e drift de indentação.
  3. Pré-Validação AST: Rejeição em memória de sintaxes inválidas sem
  alteração no disco.
  4. Rollback com Git: Restauração atômica do arquivo e verificação com git
  status --porcelain.
  5. Simulação Sully: Rejeição de vazamento e acionamento de fallback AST
  para arquivo de produção.

  Todos os testes passaram com 100% de sucesso. O padrão de amostra foi
  também atualizado para data/swebench_sample_50.json e a versão do framework
  foi elevada para v4.5.0.


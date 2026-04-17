# Implementação das Skills (OpenClaw)

Esta seção define as ferramentas que o OpenClaw "emprestará" para os nossos agentes. Sem isso, eles são apenas chatbots de texto; com as skills, eles ganham "mãos".

Para o benchmark SWE-bench, nossos SLMs precisam de apenas duas ferramentas estritamente controladas:

## 1. Skill `file_editor` (Para Codey)
Como estamos usando SLMs nativos, não queremos que eles tentem reescrever milhares de linhas de código, pois eles errarão a indentação. Em vez disso, a skill focará na substituição de blocos.

**Caminho:** `/skills/file_editor/SKILL.md`
```markdown
---
name: file_editor
description: Ferramenta para ler o conteúdo de um arquivo ou modificar um bloco de código específico.
parameters:
  - name: action
    type: string
    description: "read" (para ler) ou "replace" (para alterar)
  - name: filepath
    type: string
    description: Caminho absoluto para o arquivo alvo.
  - name: target_code
    type: string
    description: O bloco de código original exato que precisa ser substituído.
  - name: replacement_code
    type: string
    description: O novo código que entrará no lugar.
---
# Instruções para o Agente
Utilize esta ferramenta para aplicar *patches* de correção nas issues. Sempre que usar "replace", garanta que `target_code` contenha o código idêntico ao original (com os mesmos espaços) para não falhar.
```

## 2. Skill `bash_executor` (Para Vera)
A Vera precisa rodar os testes do repositório para validar as correções do Codey.

**Caminho:** `/skills/bash_executor/SKILL.md`
```markdown
---
name: bash_executor
description: Ferramenta para executar comandos de terminal isolados no ambiente de teste do SWE-bench.
parameters:
  - name: command
    type: string
    description: O comando shell a ser executado (ex: "pytest tests/test_login.py").
---
# Instruções para a Agente de Qualidade
Esta skill retorna a saída padrão (stdout) e os erros (stderr) do comando. Se a palavra "FAILED" ou sub-processos do Python retornarem traceback, copie o conteúdo e envie ao Coder reportando a falha. Somente encerre se a palavra "PASSED" predominar na saída do teste.
```

## A "Mágica" no Artigo
O fato de limitarmos o escopo das ferramentas é o motivo pelo qual modelos pequenos (SLMs) têm chance de funcionar no nosso artigo. Sistemas tradicionais dão comandos bash recursivos aos agentes, fazendo com que LLMs pequenos travem em "loops infinitos" pesquisando pastas.

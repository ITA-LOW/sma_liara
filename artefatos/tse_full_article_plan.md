# Plano de Ação: Escrita Completa do Artigo (IEEE TSE)

Conforme solicitado, antes de despejar todo o código LaTeX e BibTeX, aqui está o planejamento milimétrico de como vamos estruturar o artigo completo utilizando o framework LIARA.

## 1. Estrutura do Arquivo [main.tex](file:///home/italo/%C3%81rea%20de%20Trabalho/artigo_carol/artigo_tex/main.tex)
O artigo será dividido nas seguintes seções de peso:

1. **Introdução:** Foco no problema econômico e de privacidade dos monolitos (GPT-4) e apresentação oficial do framework LIARA (Lean Isolated Agents for Repair Automation).
2. **Trabalhos Relacionados (Related Work):** 
   - Revisão da literatura extraída **exclusivamente do seu CSV do Scopus**.
   - Citação do *Lost in the Middle* como justificativa periférica para reduzir comandos.
3. **Metodologia (O Framework LIARA):**
   - **Espaço para a Figura 1:** O Diagrama de Sequência (Sully $\rightarrow$ Codey $\rightarrow$ Vera).
   - Definição formal das "Restrições de Skills" (File Editor vs Bash Executor).
4. **Design Experimental (Experimental Setup):**
   - **Espaço para a Figura 2:** A separação arquitetural (NemoClaw/DGX).
   - Definição do dataset oficial (SWE-bench Verified).
   - **Nota de Alerta:** Aqui eu deixarei as métricas (Pass@k, Token Cost) com "X\%", pois você precisará rodar no laboratório para termos os números.
5. **Baselines e Comparações (Results):**
   - Com quem vamos comparar matematicamente nossos resultados:
     1. *Monolitos Diretos:* GPT-4o e Claude 3.5 Sonnet (Para mostrar que custamos 10x menos).
     2. *Frameworks SOTA:* SWE-agent e OpenHands (Para mostrar que nosso modelo LIARA em SLM mantém precisão parecida).
   - *Se precisarmos dos resultados literais desses oponentes, pedirei para você trazer os PDFs acadêmicos deles para eu extrair os resultados.*
   - **Espaço para a Figura 3 (Gráfico):** Gráfico comparativo de Custo vs. Resolução.
6. **Discussão e Ameaças à Validade:** Como a restrição do hardware do laboratório impediria testes massivos simultâneos se não fosse por SLMs.
7. **Conclusão:** Resumo final provando a eficácia do modelo portátil.

## 2. A Construção do `references.bib`
Eu vou criar um script nativo, robusto, que varrerá aquele arquivo CSV (`scopus_export...csv`).
- A partir dessa varredura, vou selecionar os artigos empíricos (focados em *software engineering*, *agents*, e *testing*) e gerar um arquivo `references.bib` perfeitamente formatado no padrão IEEE.
- O LaTeX fará a lincagem automática das citações no texto (`\cite{autor2024}`).

## 3. O Que Será Entregue a Você
Após a sua aprovação, eu modificarei os arquivos lá na pasta `/Computer_Society_LaTeX_template/`:
1. Atualizarei o `main_article.tex` com **TODO** o artigo escrito (das Seções 1 a 7), com comentários no código mostrando onde entram as imagens.
2. Criarei e preencherei o `references.bib`.
3. Compilaremos (você no seu Overleaf).

Esse plano atende perfeitamente à robustez exigida por uma submissão para a IEEE TSE. Podemos mandar bala na escrita?

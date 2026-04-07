import os
import json
import argparse

try:
    from datasets import load_dataset
except ImportError:
    print("ERRO: O pacote 'datasets' não está instalado.")
    print("Por favor, rode: pip install datasets")
    exit(1)

def download_swebench(num_samples=5, output_dir="data"):
    print(f"Buscando as top {num_samples} issues aleatórias do SWE-bench Verified...")
    
    try:
        # A versão Verified do SWE-bench possui os testes com maior probabilidade de sucesso local
        dataset = load_dataset("princeton-nlp/SWE-bench_Verified", split="test")
    except Exception as e:
        print(f"Erro ao tentar baixar o dataset: {e}")
        return

    # Usamos seed 42 (O Padrão Ouro Acadêmico da reprodutibilidade)
    # Assim, os 5 primeiros que você testar hoje vão ser OS MESMOS 5 que o código testará no futuro.
    shuffled_dataset = dataset.shuffle(seed=42)
    samples = shuffled_dataset.select(range(num_samples))
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"swebench_sample_{num_samples}.json")
    
    if len(samples) > 0:
        print(f"DEBUG: Chaves disponíveis no primeiro registro: {samples[0].keys()}")

    raw_data = []
    for issue in samples:
        # A versão Verified usa chaves em MAIÚSCULO: FAIL_TO_PASS
        fail_to_pass = issue.get("FAIL_TO_PASS", [])
        if isinstance(fail_to_pass, str):
            import ast
            try: fail_to_pass = ast.literal_eval(fail_to_pass)
            except: fail_to_pass = [fail_to_pass]
            
        test_patch = issue.get("test_patch", "")
        # Extrai os nomes dos arquivos do patch (linhas que começam com +++ b/)
        import re
        test_files_from_patch = re.findall(r"\+\+\+ b/(.*)", test_patch)
        
        # Filtra para evitar arquivos que não sejam de teste (opcional, mas bom)
        test_files = [f for f in test_files_from_patch if "test" in f]
        if not test_files:
            test_files = fail_to_pass # Fallback
            
        test_paths = " ".join(test_files)
        repo = issue["repo"]
        
        # Lógica de Runner por Repositório
        if "sympy" in repo.lower():
            test_cmd = f"python3 bin/test {test_paths}"
        elif "django" in repo.lower():
            test_cmd = f"python3 tests/runtests.py {test_paths}"
        else:
            test_cmd = f"pytest {test_paths}"

        issue_dict = {
            "instance_id": issue["instance_id"],
            "repo": issue["repo"],
            "base_commit": issue["base_commit"],
            "version": issue.get("version", ""),
            "problem_statement": issue["problem_statement"],
            "test_patch": test_patch,
            "test": test_cmd
        }
        raw_data.append(issue_dict)
        
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n[SUCESSO] Dataset exportado. Pipeline Acadêmico pronto!")
    print(f"Salvo em: {output_path}")
    print(f"Amostra coletada das {num_samples} issues (Para os gráficos do artigo!):")
    for item in raw_data:
        print(f" -> {item['instance_id']} (Repo: {item['repo']})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Extração do SWE-bench V1")
    parser.add_argument("--n", type=int, default=5, help="Número de issues para amostra inicial")
    args = parser.parse_args()
    
    download_swebench(num_samples=args.n)

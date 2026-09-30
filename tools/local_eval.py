"""
Harness de validação LOCAL do prompt v2.

Replica exatamente a mesma lógica de avaliação do src/evaluate.py e
src/metrics.py, mas SEM tocar no LangSmith. Serve para iterar rápido e barato
no prompt antes de rodar o experimento oficial.

Uso:
    python tools/local_eval.py                 # roda os 15 exemplos
    python tools/local_eval.py 1 2 3           # roda apenas os índices dados
    python tools/local_eval.py --quick         # roda 5 exemplos (2 simples, 2 medios, 1 complexo)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from langchain_core.prompts import ChatPromptTemplate
from utils import load_yaml, get_llm, get_eval_llm
from metrics import evaluate_f1_score, evaluate_clarity, evaluate_precision

PROMPT_FILE = ROOT / "prompts" / "bug_to_user_story_v2.yml"
PROMPT_KEY = "bug_to_user_story_v2"
DATASET = ROOT / "datasets" / "bug_to_user_story.jsonl"
THRESHOLD = 0.8
METRIC_KEYS = ["helpfulness", "correctness", "f1_score", "clarity", "precision"]


def load_dataset():
    rows = []
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_chain():
    data = load_yaml(str(PROMPT_FILE))[PROMPT_KEY]
    prompt = ChatPromptTemplate.from_messages([
        ("system", data["system_prompt"]),
        ("user", data["user_prompt"]),
    ])
    return prompt | get_llm()


def score_one(idx, row, chain):
    """
    Roda 1 exemplo: gera a resposta e calcula as 3 metricas base + 2 derivadas.
    Replica evaluate_all_metrics() de evaluate.py.
    """
    bug_report = row["inputs"]["bug_report"]
    reference = row["outputs"]["reference"]
    meta = row.get("metadata", {})
    llm = get_eval_llm()

    try:
        answer = chain.invoke({"bug_report": bug_report}).content
    except Exception as e:
        return idx, meta, {k: 0.0 for k in METRIC_KEYS}, f"ERRO geracao: {e}"

    f1 = evaluate_f1_score(bug_report, answer, reference)
    clarity = evaluate_clarity(bug_report, answer, reference)
    precision = evaluate_precision(bug_report, answer, reference)

    scores = {
        "f1_score": f1["score"],
        "clarity": clarity["score"],
        "precision": precision["score"],
    }
    scores["helpfulness"] = round((scores["clarity"] + scores["precision"]) / 2, 4)
    scores["correctness"] = round((scores["f1_score"] + scores["precision"]) / 2, 4)

    return idx, meta, scores, answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indices", nargs="*", type=int, help="Índices 1-based dos exemplos")
    ap.add_argument("--quick", action="store_true", help="Roda um subconjunto rápido")
    ap.add_argument("--workers", type=int, default=4, help="Paralelismo")
    ap.add_argument("--save", action="store_true", help="Salva as respostas geradas")
    args = ap.parse_args()

    rows = load_dataset()

    if args.indices:
        selected = [(i, rows[i - 1]) for i in args.indices if 1 <= i <= len(rows)]
    elif args.quick:
        # 2 simples + 2 medios + 1 complexo
        picks = [1, 2, 6, 7, 13]
        selected = [(i, rows[i - 1]) for i in picks]
    else:
        selected = list(enumerate(rows, 1))

    print(f"Provider: {os.getenv('LLM_PROVIDER')} | LLM: {os.getenv('LLM_MODEL')} "
          f"| EVAL: {os.getenv('EVAL_MODEL')}")
    print(f"Exemplos: {len(selected)} | workers={args.workers}\n")

    chain = build_chain()
    results = [None] * len(selected)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(score_one, i, r, chain) for i, r in selected]
        for pos, fut in enumerate(futs):
            idx, meta, scores, payload = fut.result()
            results[pos] = (idx, meta, scores, payload)
            print(f"  [{idx:2d}] {meta.get('complexity','?'):8s} "
                  f"F1:{scores['f1_score']:.2f} "
                  f"Clarity:{scores['clarity']:.2f} "
                  f"Precision:{scores['precision']:.2f}")

    # Agrega
    agg = {}
    for k in METRIC_KEYS:
        vals = [r[2][k] for r in results if r]
        agg[k] = round(sum(vals) / len(vals), 4) if vals else 0.0

    print("\n" + "=" * 50)
    print("METRICAS AGREGADAS (mesma logica do LangSmith)")
    print("=" * 50)
    print("\nMetricas Derivadas:")
    print(f"  - Helpfulness: {agg['helpfulness']:.4f} {'OK' if agg['helpfulness']>=THRESHOLD else 'FALHOU'}")
    print(f"  - Correctness: {agg['correctness']:.4f} {'OK' if agg['correctness']>=THRESHOLD else 'FALHOU'}")
    print("\nMetricas Base:")
    print(f"  - F1-Score:    {agg['f1_score']:.4f} {'OK' if agg['f1_score']>=THRESHOLD else 'FALHOU'}")
    print(f"  - Clarity:     {agg['clarity']:.4f} {'OK' if agg['clarity']>=THRESHOLD else 'FALHOU'}")
    print(f"  - Precision:   {agg['precision']:.4f} {'OK' if agg['precision']>=THRESHOLD else 'FALHOU'}")

    avg = sum(agg.values()) / len(agg)
    print(f"\nMEDIA GERAL: {avg:.4f}")

    failed = [k for k, v in agg.items() if v < THRESHOLD]
    if not failed and avg >= THRESHOLD:
        print("\nSTATUS: APROVADO - todas as metricas >= 0.8")
    else:
        print(f"\nSTATUS: REPROVADO - abaixo de 0.8: {', '.join(failed)}")

    # Piores exemplos (para direcionar a proxima iteracao)
    print("\nExemplos com menor F1 (candidatos a investigar):")
    ranked = sorted(results, key=lambda r: r[2]["f1_score"])[:5]
    for idx, meta, scores, _ in ranked:
        print(f"  [{idx:2d}] {meta.get('complexity','?'):8s} "
              f"F1:{scores['f1_score']:.2f} P:{scores['precision']:.2f} C:{scores['clarity']:.2f}")

    if args.save:
        out = ROOT / "tools" / "local_eval_output.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump([{"idx": i, "meta": m, "scores": s, "answer": a}
                       for i, m, s, a in results], f, ensure_ascii=False, indent=2)
        print(f"\nRespostas salvas em: {out}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

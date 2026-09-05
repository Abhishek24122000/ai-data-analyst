"""
Evaluation harness: runs benchmark_questions.json against a LIVE backend
(local or deployed) via its HTTP API and reports accuracy/latency.

This intentionally talks to the real, running FastAPI + LangGraph +
DuckDB stack over HTTP -- the same code path a user's browser hits --
rather than importing internals, so the numbers in the report reflect
what an actual user would get.

Usage:
    python evaluator.py --base-url http://localhost:8000
    python evaluator.py --base-url https://your-app.onrender.com --out results/run1.json

Zero third-party dependencies (uses urllib) so it can run anywhere
Python 3 runs, independent of whether the backend's own venv is active.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read())


def _within_tolerance(actual: float, expected: float, tolerance_pct: float) -> bool:
    if expected == 0:
        return abs(actual) < 1e-6
    return abs(actual - expected) / abs(expected) * 100 <= tolerance_pct


def evaluate(base_url: str, questions_path: Path) -> dict[str, Any]:
    spec = json.loads(questions_path.read_text())
    questions = spec["questions"]

    print(f"Loading sample dataset from {base_url} ...")
    dataset = _get(f"{base_url}/api/sample")
    dataset_id = dataset["dataset_id"]
    session_id = "eval-session"

    results = []
    passed = 0
    total_latency = 0.0

    for q in questions:
        t0 = time.perf_counter()
        try:
            resp = _post(
                f"{base_url}/api/chat",
                {"session_id": session_id, "dataset_id": dataset_id, "message": q["question"]},
            )
        except urllib.error.URLError as exc:
            results.append({"id": q["id"], "question": q["question"], "pass": False, "error": str(exc)})
            continue
        latency_ms = (time.perf_counter() - t0) * 1000
        total_latency += latency_ms

        facts = resp.get("facts") or {}
        ok = _check_expectation(q, resp, facts)
        if ok:
            passed += 1

        results.append(
            {
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "pass": ok,
                "answer": resp.get("answer"),
                "sql": resp.get("sql"),
                "latency_ms": round(latency_ms, 1),
                "low_confidence": resp.get("low_confidence", False),
            }
        )
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {q['id']}: {q['question']}")

    n = len(questions)
    report = {
        "total": n,
        "passed": passed,
        "accuracy_pct": round(passed / n * 100, 1) if n else 0.0,
        "avg_latency_ms": round(total_latency / n, 1) if n else 0.0,
        "results": results,
    }
    return report


def _check_expectation(q: dict, resp: dict, facts: dict) -> bool:
    tol = q.get("tolerance_pct")

    if "expected_value" in q and tol is not None:
        headline = facts.get("headline_value")
        if headline is None:
            return False
        if not _within_tolerance(float(headline), float(q["expected_value"]), tol):
            return False
        if "expected_label" in q:
            # Best-effort: the label should appear somewhere in the answer text.
            if q["expected_label"].lower() not in (resp.get("answer") or "").lower():
                return False
        return True

    if "expected_row_count" in q:
        return facts.get("row_count") == q["expected_row_count"]

    if "expected_row_count_min" in q:
        return (facts.get("row_count") or 0) >= q["expected_row_count_min"]

    if "expected_min_value" in q:
        headline = facts.get("headline_value")
        return headline is not None and float(headline) >= q["expected_min_value"]

    if "expected_value_pct_change" in q:
        pct = facts.get("pct_change")
        if pct is None:
            return False
        return abs(pct - q["expected_value_pct_change"]) <= tol if tol else True

    # No hard-coded check available for this question type -- treat any
    # non-error response as a pass (used for open-ended/ambiguous questions).
    return bool(resp.get("answer")) and not resp.get("error")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--questions", default=str(Path(__file__).parent / "benchmark_questions.json"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    report = evaluate(args.base_url, Path(args.questions))

    print("\n=== Evaluation summary ===")
    print(f"Passed: {report['passed']}/{report['total']} ({report['accuracy_pct']}%)")
    print(f"Average latency: {report['avg_latency_ms']} ms")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"Full report written to {out_path}")


if __name__ == "__main__":
    main()

"""Load the FAIRified data into Apache Jena Fuseki and answer the competency questions.

Named graphs (loaded with the SPARQL 1.1 Graph Store Protocol):
  <BASE graph/data>                      data/rdf/fairified.ttl
  <BASE graph/ontology>                  ontology/ont.ttl
  <BASE graph/nora>                      data/linking/nora_standards.ttl
  <BASE graph/specification-supplement>  data/linking/specification_supplement.ttl

Runs queries/cq/*.rq, writes CSV and JSON results to queries/cq/results/ and checks the acceptance
values (CQ2 = 129 municipalities, CQ3 = 287 of 342). The federated variant of CQ2 runs only with
--federated, because it calls the live NORA endpoint.
Requires Fuseki on http://127.0.0.1:3030 with dataset /g33 (fuseki --tdb2 --loc=db --update /g33).
Run: .venv/bin/python scripts/run_cqs.py [--federated]
"""
import csv
import io
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

FUSEKI = "http://127.0.0.1:3030/g33"
GRAPHS = {
    "data": C.ROOT / "data" / "rdf" / "fairified.ttl",
    "ontology": C.ROOT / "ontology" / "ont.ttl",
    "nora": C.ROOT / "data" / "linking" / "nora_standards.ttl",
    "specification-supplement": C.ROOT / "data" / "linking" / "specification_supplement.ttl",
}
QDIR = C.ROOT / "queries" / "cq"
OUT = QDIR / "results"


def load():
    for name, path in GRAPHS.items():
        r = requests.put(f"{FUSEKI}/data", params={"graph": C.BASE + "graph/" + name},
                         data=path.read_bytes(), headers={"Content-Type": "text/turtle"}, timeout=600)
        r.raise_for_status()
    q = "SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g ORDER BY ?g"
    r = requests.post(f"{FUSEKI}/sparql", data={"query": q}, headers={"Accept": "application/sparql-results+json"})
    return {b["g"]["value"].rsplit("/", 1)[1]: int(b["n"]["value"]) for b in r.json()["results"]["bindings"]}


def run(name: str):
    query = (QDIR / f"{name}.rq").read_text()
    t0 = time.time()
    r = requests.post(f"{FUSEKI}/sparql", data={"query": query}, headers={"Accept": "text/csv"}, timeout=600)
    r.raise_for_status()
    seconds = round(time.time() - t0, 2)
    text = r.content.decode("utf-8")
    (OUT / f"{name}.csv").write_text(text, encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    return rows, seconds


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    requests.get(f"{FUSEKI}/sparql", params={"query": "ASK {}"}, timeout=10).raise_for_status()
    report = {"graphs": load(), "queries": {}}
    names = ["cq1", "cq2", "cq2_count", "cq2_per_test", "cq3", "cq4"]
    if "--federated" in sys.argv:
        names.append("cq2_federated")
    results = {}
    for n in names:
        rows, seconds = run(n)
        results[n] = rows
        report["queries"][n] = {"rows": len(rows), "seconds": seconds}
        print(f"{n}: {len(rows)} rows in {seconds} s", flush=True)

    # Acceptance checks.
    cq1 = {(r["host"], r["test"]): r["verdict"] for r in results["cq1"]}
    assert len(results["cq1"]) == 20, len(results["cq1"])
    assert cq1[("enschede.nl", "HTTPS redirect")] == "pass" and cq1[("www.enschede.nl", "HTTPS redirect")] == "fail"
    assert cq1[("enschede.nl", "HSTS")] == "pass" and cq1[("www.enschede.nl", "HSTS")] == "fail"
    assert int(results["cq2_count"][0]["municipalities"]) == 129
    assert len({r["municipality"] for r in results["cq2"]}) == 129
    cq3_pass = sum(int(r["passing"]) for r in results["cq3"])
    cq3_total = sum(int(r["municipalities"]) for r in results["cq3"])
    assert (cq3_pass, cq3_total) == (287, 342), (cq3_pass, cq3_total)
    report["acceptance"] = {"cq1_enschede": "enschede.nl passes HTTPS redirect and HSTS, www.enschede.nl fails both",
                            "cq2_municipalities": 129, "cq3": f"{cq3_pass}/{cq3_total}"}
    report["cq2_per_test"] = {r["test"]: int(r["municipalities"]) for r in results["cq2_per_test"]}
    report["cq3"] = results["cq3"]
    report["cq4_top"] = results["cq4"][:5]
    (OUT / "summary.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("graphs", "acceptance", "cq2_per_test")}, indent=1,
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

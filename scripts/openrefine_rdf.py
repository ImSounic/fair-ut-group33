"""Triplify the extracted tables with OpenRefine and its RDF extension (Task 3).

Creates three OpenRefine projects, saves an RDF skeleton in each (visible in OpenRefine under
RDF > Edit RDF Skeleton) and exports them as Turtle:

  g33-A-assertions      data/extracted/results_long.csv   one row = one EARL assertion and its result
  g33-B-hosts           data/extracted/attribution.csv    one row = one host and its attribution
  g33-C-municipalities  data/extracted/municipalities.csv one row = one municipality

Project C also reconciles the municipality names against Wikidata (type Q2039348) and compares the
matches with the identifiers in the frozen Wikidata export. Outputs go to data/rdf/openrefine/ and
openrefine/ (project archives with the operation history and the skeletons).
Requires OpenRefine 3.9 with the RDF extension 1.6 on http://127.0.0.1:3333.
Run: .venv/bin/python scripts/openrefine_rdf.py [--no-reconcile]
     .venv/bin/python scripts/openrefine_rdf.py --resume-reconcile   (finish a reconciliation that is
     still running in project C, without recreating the projects)
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

OR = "http://127.0.0.1:3333"
OUT = C.ROOT / "data" / "rdf" / "openrefine"
ARCHIVES = C.ROOT / "openrefine"
ONT, DATA = C.ONT_NS, C.DATA_NS
EARL = "http://www.w3.org/ns/earl#"
DCT = "http://purl.org/dc/terms/"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
PROV = "http://www.w3.org/ns/prov#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SCHEMA = "https://schema.org/"
PREFIXES = [{"name": n, "uri": u} for n, u in (("d", DATA), ("ont", ONT), ("earl", EARL), ("dct", DCT),
                                                ("rdfs", RDFS), ("prov", PROV), ("xsd", XSD),
                                                ("schema", SCHEMA))]
CURIE = {u: n for n, u in ((p["name"], p["uri"]) for p in PREFIXES)}
RULE_IRI = {"R1": "R1-official-host", "R2": "R2-official-domain", "R3": "R3-name-domain", "R4": "R4-name-label"}
RECON_SERVICE = "https://wikidata.reconci.link/nl/api"
ENGINE = json.dumps({"facets": [], "mode": "row-based"})  # no facets: export every row

s = requests.Session()


def token() -> str:
    return s.get(f"{OR}/command/core/get-csrf-token").json()["token"]


def term(uri: str) -> dict:
    for ns, name in CURIE.items():
        if uri.startswith(ns):
            return {"uri": uri, "curie": f"{name}:{uri[len(ns):]}"}
    return {"uri": uri, "curie": uri}


def link(prop: str, target: dict) -> dict:
    return {**term(prop), "target": target}


def cell_res(col: str, expr: str = "value", types=(), links=()) -> dict:
    return {"nodeType": "cell-as-resource", "columnName": col, "expression": expr, "isRowNumberCell": False,
            "rdfTypes": [term(t) for t in types], "links": list(links)}


def cell_lit(col: str, expr: str = "value", lang: str | None = None, dtype: str | None = None) -> dict:
    n = {"nodeType": "cell-as-literal", "columnName": col, "expression": expr, "isRowNumberCell": False}
    if lang:
        n["lang"] = lang
    if dtype:
        n["valueType"] = dtype
    return n


def res(uri: str) -> dict:
    return {"nodeType": "resource", "value": uri, "rdfTypes": [], "links": []}


def lit(value: str, dtype: str) -> dict:
    return {"nodeType": "literal", "value": value, "valueType": dtype}


# --- skeletons -----------------------------------------------------------------------------------
# Relative IRIs (for example "host-" + value) resolve against the base IRI .../data#.

SKELETON_A = [cell_res("assertion_id", "value", [EARL + "Assertion"], [
    link(EARL + "subject", cell_res("host", '"host-" + value')),
    link(EARL + "test", cell_res("test_slug", f'"{ONT}" + value')),
    link(EARL + "assertedBy", res(DATA + "internetnl")),
    link(EARL + "mode", res(EARL + "automatic")),
    link(PROV + "wasInfluencedBy",
         cell_res("label_was_corrected", 'if(isBlank(value), null, "label-correction-2026H1")')),
    link(EARL + "result", cell_res("assertion_id", 'value + "-result"', [EARL + "TestResult"], [
        link(EARL + "outcome", cell_res("outcome_code", f'"{ONT}" + value')),
        link(DCT + "date", lit(C.REFERENCE_DATE, XSD + "date")),
        link(PROV + "wasGeneratedBy", res(DATA + f"measurement-{C.EDITION}")),
    ])),
])]

RULE_GREL = "null"
for code, local in reversed(RULE_IRI.items()):
    RULE_GREL = f'if(value == "{code}", "{ONT}{local}", {RULE_GREL})'

SKELETON_B = [
    cell_res("host", '"host-" + value', [ONT + "Host", EARL + "TestSubject"], [
        link(ONT + "hostName", cell_lit("host", "value", dtype=XSD + "string")),
    ]),
    cell_res("rule", 'if(value == "none", null, "attribution-" + cells["host"].value)',
             [ONT + "HostAttribution"], [
        link(ONT + "attributedHost", cell_res("host", '"host-" + value')),
        link(ONT + "attributedTo", cell_res("municipality_tooi")),
        link(ONT + "attributionRule", cell_res("rule", RULE_GREL)),
        link(ONT + "candidateMunicipality", cell_res("candidates", 'value.split(" ")')),
        link(ONT + "viaServiceDomain", cell_res("service_domain", '"domain-" + value', [ONT + "ServiceDomain"], [
            link(ONT + "hostName", cell_lit("service_domain", "value", dtype=XSD + "string")),
        ])),
        link(PROV + "wasGeneratedBy", res(DATA + f"linking-{C.EDITION}")),
    ]),
]

SKELETON_C = [cell_res("tooi", "value", [ONT + "Municipality"], [
    link(RDFS + "label", cell_lit("label_nl", "value", lang="nl")),
    link(ONT + "cbsCode", cell_lit("cbs_code", "value", dtype=XSD + "string")),
    link(SCHEMA + "sameAs", cell_res("wikidata")),
    link(ONT + "inProvince", cell_res("province_wikidata", "value", [ONT + "Province"], [
        link(RDFS + "label", cell_lit("province_label_nl", "value", lang="nl")),
    ])),
    link(ONT + "websiteHost", cell_res("website_hosts", 'forEach(value.split(" "), h, "host-" + h)')),
    link(ONT + "mainMailDomain", cell_res("main_mail_domain", '"host-" + value')),
])]

PROJECTS = [
    ("g33-A-assertions", C.EXTRACTED_DIR / "results_long.csv", SKELETON_A),
    ("g33-B-hosts", C.EXTRACTED_DIR / "attribution.csv", SKELETON_B),
    ("g33-C-municipalities", C.EXTRACTED_DIR / "municipalities.csv", SKELETON_C),
]


# --- OpenRefine API -------------------------------------------------------------------------------

def delete_existing(name: str):
    meta = s.get(f"{OR}/command/core/get-all-project-metadata").json()["projects"]
    for pid, m in meta.items():
        if m["name"] == name:
            s.post(f"{OR}/command/core/delete-project", params={"csrf_token": token()}, data={"project": pid})


def create_project(name: str, path: Path) -> str:
    delete_existing(name)
    opts = {"separator": ",", "headerLines": 1, "guessCellValueTypes": False, "encoding": "UTF-8",
            "storeBlankCellsAsNulls": True}
    with open(path, "rb") as f:
        r = s.post(f"{OR}/command/core/create-project-from-upload", params={"csrf_token": token()},
                   files={"project-file": (path.name, f, "text/csv")},
                   data={"project-name": name, "format": "text/line-based/*sv", "options": json.dumps(opts)},
                   allow_redirects=False)
    pid = r.headers["Location"].split("project=")[-1]
    for _ in range(120):
        m = s.get(f"{OR}/command/core/get-models", params={"project": pid})
        if m.ok and "columnModel" in m.json():
            return pid
        time.sleep(1)
    raise RuntimeError(f"project {name} was not created")


def wait_for_processes(pid: str, timeout: int = 5400):
    """Wait for OpenRefine's long-running operations (reconciliation can take tens of minutes)."""
    last = None
    for _ in range(timeout // 5):
        procs = s.get(f"{OR}/command/core/get-processes", params={"project": pid}).json()["processes"]
        if not procs:
            return
        progress = procs[0].get("progress")
        if progress != last:
            print(f"  {procs[0]['description']}: {progress}%", flush=True)
            last = progress
        time.sleep(5)
    raise RuntimeError("OpenRefine process did not finish")


def project_id(name: str) -> str:
    meta = s.get(f"{OR}/command/core/get-all-project-metadata").json()["projects"]
    return next(pid for pid, m in meta.items() if m["name"] == name)


def save_skeleton(pid: str, roots: list):
    schema = {"baseUri": DATA, "prefixes": PREFIXES, "rootNodes": roots}
    r = s.post(f"{OR}/command/rdf-extension/save-rdf-schema", params={"csrf_token": token(), "project": pid},
               data={"schema": json.dumps(schema), "engine": ENGINE})
    assert r.ok and r.json().get("code") == "ok", r.text[:300]


def export(pid: str, fmt: str) -> bytes:
    r = s.post(f"{OR}/command/core/export-rows", params={"csrf_token": token()},
               data={"project": pid, "format": fmt, "engine": ENGINE})
    r.raise_for_status()
    return r.content


def export_archive(pid: str, name: str):
    r = s.post(f"{OR}/command/core/export-project", params={"csrf_token": token()}, data={"project": pid})
    r.raise_for_status()
    (ARCHIVES / f"{name}.openrefine.tar.gz").write_bytes(r.content)


def reconcile_municipalities(pid: str, start: bool = True) -> dict:
    """Reconcile label_nl against Wikidata municipalities and compare with the frozen identifiers."""
    if start:
        start_reconciliation(pid)
    wait_for_processes(pid)
    return compare_reconciliation(pid)


def start_reconciliation(pid: str):
    config = {"mode": "standard-service", "service": RECON_SERVICE,
              "identifierSpace": "http://www.wikidata.org/entity/",
              "schemaSpace": "http://www.wikidata.org/prop/direct/",
              "type": {"id": "Q2039348", "name": "municipality of the Netherlands"},
              "autoMatch": True, "batchSize": 10, "columnDetails": [], "limit": 0}
    r = s.post(f"{OR}/command/core/reconcile", params={"csrf_token": token(), "project": pid},
               data={"columnName": "label_nl", "config": json.dumps(config), "engine": ENGINE})
    assert r.ok and r.json().get("code") in ("ok", "pending"), r.text[:300]


def compare_reconciliation(pid: str) -> dict:
    r = s.post(f"{OR}/command/core/add-column", params={"csrf_token": token(), "project": pid},
               data={"baseColumnName": "label_nl", "newColumnName": "reconciled_wikidata",
                     "expression": 'if(cell.recon.matched, "http://www.wikidata.org/entity/" + cell.recon.match.id, "")',
                     "onError": "set-to-blank", "columnInsertIndex": 4, "engine": ENGINE})
    assert r.ok, r.text[:300]
    wait_for_processes(pid)
    rows = list(csv.DictReader(io.StringIO(export(pid, "csv").decode("utf-8"))))
    matched = [r for r in rows if r["reconciled_wikidata"]]
    differ = [(r["label_nl"], r["wikidata"], r["reconciled_wikidata"]) for r in matched
              if r["reconciled_wikidata"] != r["wikidata"]]
    return {"service": RECON_SERVICE, "type": "Q2039348", "municipalities": len(rows),
            "auto_matched": len(matched), "unmatched": len(rows) - len(matched),
            "matched_but_different_from_export": differ}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ARCHIVES.mkdir(exist_ok=True)
    s.get(f"{OR}/command/core/get-version").raise_for_status()
    log_path = OUT / "openrefine_log.json"
    report = json.loads(log_path.read_text()) if log_path.exists() else {}
    if "--resume-reconcile" in sys.argv:
        pid = project_id("g33-C-municipalities")
        report["reconciliation"] = reconcile_municipalities(pid, start=False)
        (OUT / "g33-C-municipalities.ttl").write_bytes(export(pid, "Turtle"))
        export_archive(pid, "g33-C-municipalities")
    else:
        for name, path, skeleton in PROJECTS:
            t0 = time.time()
            pid = create_project(name, path)
            save_skeleton(pid, skeleton)
            ttl = export(pid, "Turtle")
            (OUT / f"{name}.ttl").write_bytes(ttl)
            export_archive(pid, name)
            report[name] = {"project_id": pid, "rows": sum(1 for _ in open(path, encoding="utf-8")) - 1,
                            "turtle_bytes": len(ttl), "seconds": round(time.time() - t0, 1)}
            print(name, report[name], flush=True)
        log_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
        if "--no-reconcile" not in sys.argv:
            pid = project_id("g33-C-municipalities")
            report["reconciliation"] = reconcile_municipalities(pid)
            export_archive(pid, "g33-C-municipalities")
    log_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    if "reconciliation" in report:
        print(json.dumps(report["reconciliation"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

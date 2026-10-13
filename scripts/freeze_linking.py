"""Freeze the external linking sources as dated, checksummed files in data/linking/.

  wikidata_municipalities.json  result of queries/linking/wikidata_municipalities.rq (WDQS)
  nora_standards.json           result of queries/linking/nora_standards.rq (NORA SPARQL endpoint)
  cbs_gemeenten_2026.json       CBS StatLine 86247NED region codes (municipal set of 2026)
  manifest.json                 retrieval time, endpoint, query checksum and file checksum

The municipal set is validated against CBS: every CBS GM code must occur exactly once in Wikidata.
Run: .venv/bin/python scripts/freeze_linking.py
"""
import datetime as dt
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

OUT = C.ROOT / "data" / "linking"
QUERIES = C.ROOT / "queries" / "linking"
USER_AGENT = "FAIR-DE-Group33-linking/1.0 (University of Twente FAIR Data Engineering course project)"
SOURCES = {
    "wikidata_municipalities": ("https://query.wikidata.org/sparql", QUERIES / "wikidata_municipalities.rq"),
    "nora_standards": ("https://sparql.noraonline.nl/nora/sparql", QUERIES / "nora_standards.rq"),
}
CBS_URL = "https://opendata.cbs.nl/ODataApi/odata/86247NED/RegioS?$format=json"


def fetch(url: str, data: bytes | None = None, accept: str = "application/json") -> bytes:
    req = urllib.request.Request(url, data=data, headers={"Accept": accept, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (endpoint, qfile) in SOURCES.items():
        q = qfile.read_bytes()
        body = fetch(endpoint, urllib.parse.urlencode({"query": q.decode()}).encode(),
                     "application/sparql-results+json")
        json.loads(body)  # must parse
        (OUT / f"{name}.json").write_bytes(body)
        manifest[name] = {"endpoint": endpoint, "query": str(qfile.relative_to(C.ROOT)),
                          "query_sha256": hashlib.sha256(q).hexdigest()}
    body = fetch(CBS_URL)
    (OUT / "cbs_gemeenten_2026.json").write_bytes(body)
    manifest["cbs_gemeenten_2026"] = {"endpoint": CBS_URL, "table": "CBS StatLine 86247NED, Gebieden in Nederland 2026"}

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    for name, entry in manifest.items():
        f = OUT / f"{name}.json"
        entry.update({"file": f.name, "retrieved": now, "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})

    # Validate the municipal set against CBS.
    cbs = {r["Key"].strip() for r in json.loads((OUT / "cbs_gemeenten_2026.json").read_bytes())["value"]
           if r["Key"].startswith("GM")}
    rows = json.loads((OUT / "wikidata_municipalities.json").read_bytes())["results"]["bindings"]
    wd = {}
    for b in rows:
        wd.setdefault("GM" + b["cbsCode"]["value"], set()).add(b["municipality"]["value"])
    assert all(len(v) == 1 for v in wd.values()), "a CBS code maps to several Wikidata items"
    manifest["validation"] = {
        "cbs_codes": len(cbs), "wikidata_municipalities": len(wd), "wikidata_rows": len(rows),
        "missing_in_wikidata": sorted(cbs - set(wd)), "not_in_cbs": sorted(set(wd) - cbs),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps(manifest["validation"], indent=1))
    assert cbs == set(wd), "Wikidata municipal set differs from CBS 2026"


if __name__ == "__main__":
    main()

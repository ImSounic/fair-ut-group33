"""Export the FAIR Data Point records as static files for the website (docs/), where the w3id rules
point (.../group33/fdp and .../fdp/{catalog|dataset|distribution|profile}/{uuid}).

  docs/fdp/index.ttl                      the FAIR Data Point record
  docs/fdp/<type>/<uuid>.ttl              catalog, dataset, distributions and their profiles
  docs/shapes/<name>.ttl                  the SHACL shapes of the metadata schemas (fdp/schemas/)
  docs/metadata.html                      a readable overview of the records
  data/metadata/                          the same records, merged into metadata.ttl for validation

Run after scripts/fdp_publish.py: .venv/bin/python scripts/fdp_export.py
"""
import html
import json
import os
import shutil
import sys
from pathlib import Path

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, DCTERMS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

API = os.environ.get("FDP_API", "http://127.0.0.1:8085")
FDP = C.BASE + "fdp"
DOCS = C.ROOT / "docs"
META = C.ROOT / "data" / "metadata"


def fetch(iri: str) -> str:
    r = requests.get(API + iri[len(FDP):] if iri != FDP else API + "/", headers={"Accept": "text/turtle"})
    r.raise_for_status()
    # The FDP sends text/turtle without a charset; requests would then decode
    # it as ISO-8859-1 and double-encode non-ASCII characters.
    return r.content.decode("utf-8")


def main():
    records = json.loads((C.ROOT / "fdp" / "records.json").read_text())
    (DOCS / "fdp").mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    merged = Graph()
    todo = [FDP] + list(records.values())
    seen, rows = set(), []
    while todo:
        iri = todo.pop(0)
        if iri in seen:
            continue
        seen.add(iri)
        ttl = fetch(iri)
        g = Graph().parse(data=ttl, format="turtle")
        merged += g
        rel = "index" if iri == FDP else iri[len(FDP) + 1:]
        out = DOCS / "fdp" / f"{rel}.ttl"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(ttl, encoding="utf-8")
        (META / f"{rel.replace('/', '-')}.ttl").write_text(ttl, encoding="utf-8")
        for prof in g.objects(URIRef(iri), DCTERMS.conformsTo):
            if str(prof).startswith(FDP + "/profile/"):
                todo.append(str(prof))
        if "/profile/" not in iri:
            title = next((str(t) for t in g.objects(URIRef(iri), DCTERMS.title) if getattr(t, "language", None)
                          in ("en", None)), rel)
            rows.append((rel.split("/")[0] if rel != "index" else "FAIR Data Point", title, iri))
    merged.serialize(META / "metadata.ttl", format="turtle")

    shapes = DOCS / "shapes"
    shapes.mkdir(exist_ok=True)
    for f in (C.ROOT / "fdp" / "schemas").glob("*.ttl"):
        shutil.copyfile(f, shapes / f.name)

    order = {"FAIR Data Point": 0, "catalog": 1, "dataset": 2, "distribution": 3}
    rows.sort(key=lambda r: (order.get(r[0], 9), r[1]))
    table = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(t)}</td>"
                    f'<td><a href="fdp/{html.escape(i[len(FDP) + 1:] if i != FDP else "index")}.ttl"><code>'
                    f"{html.escape(i)}</code></a></td></tr>" for k, t, i in rows)
    shape_links = " · ".join(f'<a href="shapes/{n}.ttl">{n}</a>' for n in ("resource", "catalog", "dataset",
                                                                              "distribution"))
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><title>Metadata records</title>"
            "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:960px;margin:0 auto;padding:32px 16px}"
            "table{border-collapse:collapse;width:100%;display:block;overflow-x:auto}th,td{text-align:left;"
            "padding:6px 10px;border-bottom:1px solid #ddd;vertical-align:top}code{word-break:break-all}"
            "@media (prefers-color-scheme:dark){body{background:#16171a;color:#e8e8ea}a{color:#7fb2e5}}"
            "</style></head><body>"
            "<h1>Metadata records</h1><p>Records of the project's FAIR Data Point (DCAT, DCAT-AP-NL 3.0), "
            "exported as Turtle. Each identifier resolves through w3id.org to the Turtle below for machines "
            "and to this page for people.</p>"
            f"<table><tr><th>Type</th><th>Title</th><th>Identifier</th></tr>{table}</table>"
            f"<h2>SHACL shapes of the metadata schemas</h2><p>{shape_links}</p>"
            '<p><a href="./">Project home</a></p></body></html>\n')
    (DOCS / "metadata.html").write_text(page, encoding="utf-8")
    print(f"exported {len(seen)} documents ({len(merged)} triples) to docs/fdp and data/metadata")


if __name__ == "__main__":
    main()

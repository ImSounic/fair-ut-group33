"""Build the GitHub Pages site in docs/, which the w3id redirect rules (w3id/.htaccess) point at.

  docs/index.html            landing page of the project and of .../group33/data for people
  docs/ont/                  ont.ttl, ont.owl and index.html (documentation, one anchor per term)
  docs/dist/                 distribution files
  docs/source/               the deposited source snapshot with its checksums

Run: .venv/bin/python scripts/build_site.py
"""
import html
import shutil
import sys
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

DOCS = C.ROOT / "docs"
REPO = "https://github.com/ImSounic/fair-ut-group33"
EARL = Namespace("http://www.w3.org/ns/earl#")
CSS = """
:root { --fg:#1d1d1f; --muted:#5f6368; --bg:#ffffff; --line:#e3e3e8; --accent:#2f6fa8; --code:#f4f5f7; }
@media (prefers-color-scheme: dark) { :root { --fg:#e8e8ea; --muted:#a0a3a8; --bg:#16171a; --line:#2c2e33;
  --accent:#7fb2e5; --code:#1f2126; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.55 system-ui, -apple-system,
  "Segoe UI", Roboto, sans-serif; }
main { max-width: 920px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 1.7rem; line-height: 1.25; margin: 0 0 8px; }
h2 { font-size: 1.2rem; margin: 40px 0 12px; padding-top: 8px; border-top: 1px solid var(--line); }
h3 { font-size: 1rem; margin: 24px 0 4px; }
p, li { max-width: 72ch; }
.lead { color: var(--muted); font-size: 1.05rem; }
a { color: var(--accent); }
code { background: var(--code); padding: 1px 5px; border-radius: 4px; font-size: .88em; word-break: break-all; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; margin: 8px 0 16px; display: block;
  overflow-x: auto; }
th, td { text-align: left; vertical-align: top; padding: 6px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 600; }
.term { padding: 12px 0; border-bottom: 1px solid var(--line); }
.term:target { background: var(--code); }
.meta { color: var(--muted); font-size: .9rem; }
"""


def page(title: str, body: str) -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main></body></html>\n")


def lit(g, s, p, lang):
    for o in g.objects(s, p):
        if getattr(o, "language", None) == lang:
            return str(o)
    return ""


def local(iri) -> str:
    return str(iri).split("#")[-1]


def curie(g, iri) -> str:
    try:
        c = g.namespace_manager.normalizeUri(iri)
    except Exception:  # noqa: BLE001
        return str(iri)
    return str(iri) if c.startswith("<") else c


def link(g, iri) -> str:
    s = str(iri)
    if s.startswith(C.ONT_NS):
        return f'<a href="#{html.escape(local(iri))}"><code>ont:{html.escape(local(iri))}</code></a>'
    return f'<a href="{html.escape(s)}"><code>{html.escape(curie(g, iri))}</code></a>'


def term_block(g, s) -> str:
    label = lit(g, s, RDFS.label, "en") or lit(g, s, SKOS.prefLabel, "en")
    label_nl = lit(g, s, RDFS.label, "nl") or lit(g, s, SKOS.prefLabel, "nl")
    rows = [f'<div class="term" id="{html.escape(local(s))}"><h3>{html.escape(label)} '
            f'<span class="meta">({html.escape(label_nl)}@nl)</span></h3>',
            f'<div class="meta"><code>{html.escape(str(s))}</code></div>',
            f"<p>{html.escape(lit(g, s, SKOS.definition, 'en'))}</p>",
            f'<p class="meta" lang="nl">{html.escape(lit(g, s, SKOS.definition, "nl"))}</p>']
    facts = []
    for p, name in ((RDF.type, "type"), (RDFS.subClassOf, "subclass of"), (RDFS.domain, "domain"),
                    (RDFS.range, "range"), (URIRef(C.ONT_NS + "checksStandard"), "checks standard"),
                    (RDFS.seeAlso, "see also"), (DCTERMS.source, "source")):
        vals = [o for o in g.objects(s, p) if not (p == RDF.type and o in (OWL.NamedIndividual,))]
        if vals:
            facts.append(f"<li>{name}: " + ", ".join(link(g, o) for o in sorted(vals, key=str)) + "</li>")
    note = lit(g, s, SKOS.scopeNote, "en")
    if note:
        facts.append(f"<li>note: {html.escape(note)}</li>")
    if facts:
        rows.append("<ul>" + "".join(facts) + "</ul>")
    return "".join(rows) + "</div>"


def ontology_page(g) -> str:
    onto = URIRef(C.ONT_IRI)
    own = lambda xs: sorted((x for x in xs if str(x).startswith(C.ONT_NS)), key=str)  # noqa: E731
    classes = own(g.subjects(RDF.type, OWL.Class))
    props = own(set(g.subjects(RDF.type, OWL.ObjectProperty)) | set(g.subjects(RDF.type, OWL.DatatypeProperty)))
    tests = own(g.subjects(RDF.type, EARL.TestCase))
    codes = own(g.subjects(SKOS.inScheme, URIRef(C.ONT_NS + "OutcomeCodes")))
    rules = own(g.subjects(SKOS.inScheme, URIRef(C.ONT_NS + "AttributionRules")))
    body = [f"<h1>{html.escape(lit(g, onto, DCTERMS.title, 'en'))}</h1>",
            f'<p class="lead">{html.escape(lit(g, onto, DCTERMS.description, "en"))}</p>',
            "<table><tr><th>Ontology IRI</th><td><code>" + html.escape(C.ONT_IRI) + "</code></td></tr>",
            f"<tr><th>Namespace</th><td><code>{html.escape(C.ONT_NS)}</code> (prefix <code>ont:</code>)</td></tr>",
            f"<tr><th>Version</th><td>{html.escape(str(g.value(onto, OWL.versionInfo)))}</td></tr>",
            f'<tr><th>Licence</th><td>{link(g, g.value(onto, DCTERMS.license))}</td></tr>',
            '<tr><th>Download</th><td><a href="ont.ttl">Turtle</a> · <a href="ont.owl">RDF/XML</a></td></tr>',
            "</table>",
            "<h2>Classes</h2>", *[term_block(g, s) for s in classes],
            "<h2>Properties</h2>", *[term_block(g, s) for s in props],
            "<h2>Tests</h2><p>The 14 tests of the measurement, each an <code>earl:TestCase</code>.</p>",
            *[term_block(g, s) for s in tests],
            "<h2>Outcome codes</h2><p>Members of <code>ont:OutcomeCodes</code>; each is also an instance of "
            "an EARL outcome class.</p>", *[term_block(g, s) for s in codes],
            "<h2>Attribution rules</h2>", *[term_block(g, s) for s in rules]]
    return page("Group 33 ontology", "".join(body))


def landing_page() -> str:
    ns = C.BASE
    rows = [("Ontology", ns + "ont", "ont/"),
            ("FAIRified data (Turtle)", ns + "data", "dist/fairified.ttl"),
            ("Extracted tables (CSV)", ns + "dist/municipal_web.csv", "dist/municipal_web.csv"),
            ("Source snapshot", ns + "source/" + C.APPENDIX.name, "source/" + C.APPENDIX.name),
            ("Metadata records (FAIR Data Point)", ns + "fdp", "metadata.html")]
    table = "".join(f"<tr><td>{html.escape(n)}</td><td><code>{html.escape(i)}</code></td>"
                    f'<td><a href="{html.escape(h)}">open</a></td></tr>' for n, i, h in rows)
    body = ("<h1>Municipal results of the Dutch information security standards measurement, FAIRified</h1>"
            '<p class="lead">Per-host results of the half-yearly measurement of mandatory internet security '
            "standards by Forum Standaardisatie (edition begin 2026, reference date 31 December 2025), for the "
            "internet domains of Dutch municipalities: 26,064 test results for 1,867 hosts and 14 tests, "
            "described with W3C EARL, PROV-O and SKOS and linked to the municipalities (TOOI, Wikidata) and to "
            "the standards they check (NORA).</p>"
            "<h2>Identifiers</h2><table><tr><th>Resource</th><th>Persistent identifier</th><th></th></tr>"
            f"{table}</table>"
            "<h2>Source and licence</h2><p>Source: Forum Standaardisatie, <em>Meting "
            "Informatieveiligheidstandaarden begin 2026, Bijlage: individuele resultaten per "
            "internetdomein</em>, published June 2026, CC0 1.0 (site-wide statement). Data and metadata of this "
            "project: CC0 1.0. Ontology: CC BY 4.0. Code: MIT.</p>"
            f'<p>Project of Group 33, FAIR Data Engineering, University of Twente, 2026. '
            f'Code and files: <a href="{REPO}">{REPO}</a>.</p>')
    return page("FAIRified information security measurement, Group 33", body)


def main():
    (DOCS / "ont").mkdir(parents=True, exist_ok=True)
    (DOCS / "dist").mkdir(exist_ok=True)
    (DOCS / "source").mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    for f in ("ont.ttl", "ont.owl"):
        shutil.copyfile(C.ROOT / "ontology" / f, DOCS / "ont" / f)
    g = Graph().parse(C.ROOT / "ontology" / "ont.ttl")
    (DOCS / "ont" / "index.html").write_text(ontology_page(g), encoding="utf-8")
    for f in ("municipal_web.csv", "municipal_mail.csv"):
        shutil.copyfile(C.EXTRACTED_DIR / f, DOCS / "dist" / f)
    for f in ("fairified.ttl", "fairified.ttl.gz"):
        shutil.copyfile(C.ROOT / "data" / "rdf" / f, DOCS / "dist" / f)
    for f in C.SOURCE_DIR.iterdir():
        if f.is_file():
            shutil.copyfile(f, DOCS / "source" / f.name)
    (DOCS / "index.html").write_text(landing_page(), encoding="utf-8")
    print("site written to", DOCS, sorted(str(p.relative_to(DOCS)) for p in DOCS.rglob("*") if p.is_file()))


if __name__ == "__main__":
    main()

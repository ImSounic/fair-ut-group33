"""Build the mini-ontology ontology/ont.ttl (and ont.owl, RDF/XML) from ontology/src/.

  tbox.ttl          header, classes, properties, concept schemes and attribution rules (hand-written)
  tests.csv         the 14 tests: service, standards checked (NORA), documentation, definitions
  outcome_codes.csv the 10 outcome codes: EARL class, labels, definitions and their sources

Dutch definitions are checked against (tests) or taken from (codes) the legend of the appendix, so
they are verbatim. The base IRI comes from config.BASE.
Run: .venv/bin/python scripts/build_ontology.py
"""
import csv
import re
import sys
from pathlib import Path

import lxml.html
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

SRC = C.ROOT / "ontology" / "src"
OUT = C.ROOT / "ontology"
TEMPLATE_BASE = "https://w3id.org/FAIR-course-UT/2026-2027/group33/"
EARL = Namespace("http://www.w3.org/ns/earl#")
VANN = Namespace("http://purl.org/vocab/vann/")
ONT = Namespace(C.ONT_NS)
NORA = "https://www.noraonline.nl/wiki/Special:URIResolver/FS:"
APPENDIX_URL = ("https://www.forumstandaardisatie.nl/sites/default/files/OBDO/2026/0611/"
                "20260611-1b-bijlage-meting-informatieveiligheidstandaarden-begin-2026-OBDO.html")
LEGEND = URIRef(APPENDIX_URL + "#1_toelichting_resultaten")
INTERNETNL = "https://github.com/internetstandards/Internet.nl/blob/ad507d18bee333f3db5a3a3cf965678a41b5893a/"
SOURCES = {"openapi": URIRef(INTERNETNL + "interface/batch/openapi.yaml"),
           "custom_results": URIRef(INTERNETNL + "interface/batch/custom_results.py"),
           "legend": LEGEND}
# Legend row names (appendix section 1) -> test slugs.
LEGEND_TESTS = {"TLS cf. NCSC": "tls", "HTTPS redirect": "https_redirect", "HSTS": "hsts", "DNSSEC": "dnssec",
                "IPv6 web": "ipv6_web", "RPKI web": "rpki_web", "DKIM": "dkim", "DMARC policy": "dmarc",
                "SPF policy": "spf", "DNSSEC MX": "dnssec_mx", "DANE": "dane", "STARTTLS NCSC": "starttls",
                "IPv6 MX": "ipv6_mx", "RPKI MX": "rpki_mx"}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def cell_text(cell) -> str:
    for el in cell.iter("li", "br", "p"):  # keep list items and line breaks apart
        el.text = " " + (el.text or "")
    return clean(cell.text_content())


def read_legend():
    doc = lxml.html.fromstring(C.APPENDIX.read_bytes().decode("utf-8"))
    tables = doc.xpath("//table")[:3]
    rows = [[cell_text(c) for c in tr.xpath("./th|./td")] for t in tables for tr in t.xpath(".//tr")[1:]]
    codes = {r[0]: r[1] for r in rows[:7]}
    tests = {LEGEND_TESTS[r[0]]: r[1] for r in rows[7:]}
    assert len(codes) == 7 and len(tests) == 14, (len(codes), len(tests))
    return codes, tests


def main():
    legend_codes, legend_tests = read_legend()
    g = Graph()
    g.parse(data=(SRC / "tbox.ttl").read_text(encoding="utf-8").replace(TEMPLATE_BASE, C.BASE), format="turtle")
    onto = URIRef(C.ONT_IRI)
    assert (onto, RDF.type, OWL.Ontology) in g
    for prefix, ns in [("ont", ONT), ("earl", EARL), ("skos", SKOS), ("dct", DCTERMS),
                       ("nora", Namespace(NORA))]:
        g.bind(prefix, ns, override=True)

    tests = list(csv.DictReader(open(SRC / "tests.csv", encoding="utf-8")))
    assert len(tests) == 14
    for t in tests:
        assert clean(t["definition_nl"]) == legend_tests[t["slug"]], f"Dutch definition of {t['slug']} differs from legend"
        s = ONT[t["slug"]]
        g.add((s, RDF.type, EARL.TestCase))
        g.add((s, RDF.type, ONT.WebTest if t["service"] == "web" else ONT.MailTest))
        if t["core_mail"] == "1":
            g.add((s, RDF.type, ONT.CoreMailTest))
        for lang in ("en", "nl"):
            g.add((s, RDFS.label, Literal(t["column_label"], lang=lang)))
        g.add((s, SKOS.notation, Literal(t["column_label"])))
        g.add((s, SKOS.definition, Literal(clean(t["definition_nl"]), lang="nl")))
        g.add((s, SKOS.definition, Literal(t["definition_en"], lang="en")))
        g.add((s, SKOS.editorialNote, Literal("The Dutch definition is quoted from the legend of the appendix; "
                                              "the English definition is a translation of it.", lang="en")))
        g.add((s, DCTERMS.source, LEGEND))
        for std in t["nora_standards"].split():
            g.add((s, ONT.checksStandard, URIRef(NORA + std)))
        g.add((s, RDFS.seeAlso, URIRef(t["internetnl_faq"])))
        g.add((s, RDFS.isDefinedBy, onto))

    codes = list(csv.DictReader(open(SRC / "outcome_codes.csv", encoding="utf-8")))
    assert len(codes) == 10 and {c["code"] for c in codes} == set(C.OUTCOME_CODES)
    for c in codes:
        s = ONT[c["code"]]
        g.add((s, RDF.type, SKOS.Concept))
        g.add((s, RDF.type, EARL[c["earl_class"]]))
        g.add((s, SKOS.inScheme, ONT.OutcomeCodes))
        g.add((s, SKOS.topConceptOf, ONT.OutcomeCodes))
        g.add((s, SKOS.notation, Literal(c["code"])))
        g.add((s, SKOS.prefLabel, Literal(c["label_en"], lang="en")))
        g.add((s, SKOS.prefLabel, Literal(c["label_nl"], lang="nl")))
        g.add((s, SKOS.definition, Literal(c["definition_en"], lang="en")))
        g.add((s, SKOS.definition, Literal(legend_codes[c["legend_key"]], lang="nl")))
        g.add((s, DCTERMS.source, SOURCES[c["source_en"]]))
        g.add((s, DCTERMS.source, LEGEND))
        if c["scope_note_en"]:
            g.add((s, SKOS.scopeNote, Literal(c["scope_note_en"], lang="en")))
        g.add((s, RDFS.seeAlso, EARL[c["earl_instance"]]))
        g.add((s, RDFS.isDefinedBy, onto))

    # OWL 2 declarations, so that OWL tools (Protégé, HermiT) read the file as intended.
    for s in set(g.subjects(RDF.type, EARL.TestCase)) | set(g.subjects(SKOS.inScheme, None)):
        g.add((s, RDF.type, OWL.NamedIndividual))
    for p in (SKOS.prefLabel, SKOS.definition, SKOS.notation, SKOS.scopeNote, SKOS.editorialNote, SKOS.inScheme,
              SKOS.topConceptOf, DCTERMS.title, DCTERMS.description, DCTERMS.creator, DCTERMS.publisher,
              DCTERMS.license, DCTERMS.created, DCTERMS.modified, DCTERMS.source, VANN.preferredNamespacePrefix,
              VANN.preferredNamespaceUri):
        g.add((p, RDF.type, OWL.AnnotationProperty))

    # Quality checks: every term defined here has English and Dutch labels and definitions.
    own = {s for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(C.ONT_NS)}
    for s in own:
        for p in ((RDFS.label, SKOS.prefLabel), (SKOS.definition,)):
            langs = {o.language for q in p for o in g.objects(s, q)}
            assert {"en", "nl"} <= langs, f"{s} lacks en/nl {p[0]}"
    OUT.mkdir(exist_ok=True)
    g.serialize(OUT / "ont.ttl", format="turtle")
    g.serialize(OUT / "ont.owl", format="pretty-xml")
    print(f"{len(g)} triples; {len(own)} terms in {C.ONT_NS}; written ont.ttl and ont.owl")


if __name__ == "__main__":
    main()

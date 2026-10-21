"""Turn the frozen NORA export into RDF and add a curated supplement of specification documents.

  data/linking/nora_standards.ttl            the nine NORA standards as exported (title, status, version
                                             text, specification documents, Forum Standaardisatie page)
  data/linking/specification_supplement.ttl  specification documents that NORA lacks or links wrongly,
                                             each with its basis, attributed to the project

Run: .venv/bin/python scripts/build_linking_rdf.py
"""
import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

LINK = C.ROOT / "data" / "linking"
E = Namespace("https://www.noraonline.nl/wiki/Eigenschap:")
NORA = "https://www.noraonline.nl/wiki/Special:URIResolver/FS:"
RFC = "https://www.rfc-editor.org/rfc/rfc{}"
SUPPLEMENT = {
    "Dnssec": ([4033, 4034, 4035], "NORA gives no specification document for DNSSEC; its version field lists "
                                   "RFC 4033, RFC 4034 and RFC 4035."),
    "Tls": ([8446, 5246], "NORA links an Internet-Draft (draft-ietf-tls-tls13) while its version field says "
                          "'1.3 en 1.2'; TLS 1.3 is RFC 8446 and TLS 1.2 is RFC 5246."),
    "Ipv6": ([8200], "NORA links RFC 791 (IPv4) and RFC 2460 (obsoleted by RFC 8200); IPv6 is specified in "
                     "RFC 8200."),
}


def main():
    man = json.loads((LINK / "manifest.json").read_text())["nora_standards"]
    rows = json.loads((LINK / "nora_standards.json").read_text())["results"]["bindings"]
    g = Graph()
    g.bind("e", E)
    g.bind("skos", SKOS)
    g.bind("dct", DCTERMS)
    for b in rows:
        s = URIRef(b["standard"]["value"])
        g.add((s, RDF.type, SKOS.Concept))
        if "title" in b:
            g.add((s, DCTERMS.title, Literal(b["title"]["value"])))
        if "status" in b:
            g.add((s, E["Status_lijst_Forum_Standaardisatie"], Literal(b["status"]["value"])))
        if b.get("versions", {}).get("value"):
            g.add((s, E.Versie, Literal(b["versions"]["value"])))
        for spec in b.get("specifications", {}).get("value", "").split():
            g.add((s, E.Specificatiedocument, URIRef(spec)))
        if "forumPage" in b:
            g.add((s, OWL.sameAs, URIRef(b["forumPage"]["value"])))
    header = (f"# NORA standards register (https://sparql.noraonline.nl/nora/sparql), query "
              f"{man['query']}, retrieved {man['retrieved']}, sha256 of the JSON result {man['sha256']}.\n")
    (LINK / "nora_standards.ttl").write_text(header + g.serialize(format="turtle"))

    sup = Graph()
    sup.bind("e", E)
    graph_iri = URIRef(C.BASE + "graph/specification-supplement")
    sup.add((graph_iri, RDF.type, PROV.Entity))
    sup.add((graph_iri, RDFS.label, Literal("Curated supplement to the specification documents in NORA", lang="en")))
    sup.add((graph_iri, PROV.wasAttributedTo, URIRef(C.DATA_NS + "sounic-akkaraju")))
    sup.add((graph_iri, PROV.wasDerivedFrom, URIRef(C.DATA_NS + "export-nora-standards")))
    for std, (rfcs, basis) in SUPPLEMENT.items():
        s = URIRef(NORA + std)
        for n in rfcs:
            sup.add((s, E.Specificatiedocument, URIRef(RFC.format(n))))
        sup.add((s, RDFS.comment, Literal(f"Supplement: {basis}", lang="en")))
    (LINK / "specification_supplement.ttl").write_text(
        "# Specification documents added by the project where NORA lacks them or links them wrongly.\n"
        + sup.serialize(format="turtle"))
    print(f"nora_standards.ttl: {len(g)} triples; specification_supplement.ttl: {len(sup)} triples")


if __name__ == "__main__":
    main()

"""Validate the exported metadata records against DCAT-AP 3.0 and DCAT-AP-NL 3.0 (SHACL).

The records (data/metadata/metadata.ttl, without the FAIR Data Point's own record, which is a
dcat:DataService) are validated together with data/metadata/vocabulary-types.ttl, which gives the
classes of the referenced code-list terms. Mandatory, class-range and code-list shapes must conform;
the shapes for recommended properties are reported separately. Writes data/metadata/validation.json.
Run: .venv/bin/python scripts/validate_metadata.py
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import DCAT, RDF, RDFS, SH

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

META = C.ROOT / "data" / "metadata"
EU = "http://publications.europa.eu/resource/authority/"
EU_TERMS = ["language/ENG", "language/NLD", "access-right/PUBLIC", "frequency/ANNUAL_2", "country/NLD",
            "data-theme", "data-theme/GOVE", "file-type/HTML", "file-type/CSV", "file-type/RDF_TURTLE"]
KEEP = {str(RDF.type), "http://www.w3.org/2004/02/skos/core#prefLabel", "http://purl.org/dc/terms/title",
        "http://www.w3.org/2004/02/skos/core#inScheme"}
REQUIRED = ["dcat-ap-SHACL.ttl", "dcat-ap-nl-SHACL.ttl", "dcat-ap-nl-SHACL-klassebereik.ttl",
            "dcat-ap-nl-SHACL-klassebereik-codelijsten.ttl"]
RECOMMENDED = ["dcat-ap-nl-SHACL-aanbevolen.ttl"]
KNOWN_FDP_DEVIATIONS = {
    "http://www.w3.org/ns/dcat#themeTaxonomy": (
        "FAIR Data Point 1.22.2 replaces the catalog's dcat:themeTaxonomy with the themes of its datasets "
        "when it serves the record (CatalogMetadataService.retrieve -> setThemeTaxonomies), so the record "
        "holds the theme data-theme/GOVE instead of the concept scheme data-theme that was entered. Exports "
        "are kept as the FDP serves them."),
}


def run(data: Graph, files):
    shapes = Graph()
    for f in files:
        shapes.parse(META / "shapes" / f)
    conforms, report, _ = validate(data, shacl_graph=shapes, inference="none", allow_warnings=True)
    results = []
    for r in report.subjects(RDF.type, SH.ValidationResult):
        results.append({"severity": str(report.value(r, SH.resultSeverity)).split("#")[1],
                        "focus": str(report.value(r, SH.focusNode)), "path": str(report.value(r, SH.resultPath)),
                        "message": str(report.value(r, SH.resultMessage))})
    return conforms, results


def freeze_eu_vocabularies():
    """Deposit the type, labels and scheme of each referenced EU Vocabularies term (dated)."""
    g = Graph()
    for t in EU_TERMS:
        req = urllib.request.Request(EU + t, headers={"Accept": "application/rdf+xml"})
        with urllib.request.urlopen(req, timeout=60) as r:
            full = Graph().parse(data=r.read(), format="xml")
        for s_, p, o in full.triples((URIRef(EU + t), None, None)):
            if str(p) in KEEP and (getattr(o, "language", None) in (None, "en", "nl")):
                g.add((s_, p, o))
    path = META / "eu-vocabularies.ttl"
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path.write_text(f"# Extract of EU Vocabularies (publications.europa.eu/resource/authority), retrieved {stamp}:\n"
                    "# rdf:type, skos:prefLabel (en, nl), dct:title and skos:inScheme of the terms used.\n"
                    + g.serialize(format="turtle"))


def main():
    if "--refresh-vocabularies" in sys.argv or not (META / "eu-vocabularies.ttl").exists():
        freeze_eu_vocabularies()
    data = Graph().parse(META / "metadata.ttl")
    root = URIRef(C.BASE + "fdp")
    for t in list(data.triples((root, None, None))):
        data.remove(t)
    data.parse(META / "vocabulary-types.ttl")
    data.parse(META / "eu-vocabularies.ttl")
    prov = Graph().parse(C.ROOT / "data" / "rdf" / "prov.ttl")  # describes the creator
    creator = URIRef(C.DATA_NS + "sounic-akkaraju")
    for t in prov.triples((creator, None, None)):
        data.add(t)
    std = URIRef("http://purl.org/dc/terms/Standard")
    for o in set(data.objects(None, URIRef("http://purl.org/dc/terms/conformsTo"))):
        if str(o).startswith(C.BASE + "fdp/profile/"):  # FDP profiles are prof:Profile, a dct:Standard
            data.add((o, RDF.type, std))
    for p in (DCAT.accessURL, DCAT.downloadURL):  # every IRI is an rdfs:Resource
        for o in set(data.objects(None, p)):
            data.add((o, RDF.type, RDFS.Resource))
    ok, required = run(data, REQUIRED)
    _, recommended = run(data, RECOMMENDED)
    for r in required:
        if r["path"] in KNOWN_FDP_DEVIATIONS:
            r["known_fdp_deviation"] = KNOWN_FDP_DEVIATIONS[r["path"]]
    unexplained = [r for r in required if "known_fdp_deviation" not in r]
    out = {"required_shapes": REQUIRED, "conforms": ok, "violations": required,
           "violations_not_caused_by_the_fdp": len(unexplained),
           "recommended_shapes": RECOMMENDED,
           "recommended_findings": sorted({(r["severity"], r["path"], r["message"]) for r in recommended})}
    (META / "validation.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("DCAT-AP 3.0 + DCAT-AP-NL 3.0 (mandatory, class ranges, code lists):",
          "conforms" if ok else f"{len(required)} violations, {len(unexplained)} not caused by the FDP")
    for r in required:
        print("  ", r["path"], "-", r["message"], "[known FDP deviation]" if "known_fdp_deviation" in r else "")
    print("recommended properties:", Counter(r["severity"] for r in recommended))
    for f in out["recommended_findings"]:
        print("  ", f)


if __name__ == "__main__":
    main()

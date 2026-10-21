"""Build data/rdf/prov.ttl: the agents, activities and source entities behind the FAIRified data.

The values (checksums, dates, counts, versions) are read from the logs and manifests written by the
earlier steps, so nothing is typed by hand. These resources live in the data namespace (.../data#),
because their IRIs must resolve to the data document.
Run: .venv/bin/python scripts/build_prov.py
"""
import json
import sys
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, PROV, RDF, RDFS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

D = Namespace(C.DATA_NS)
ONT = Namespace(C.ONT_NS)
EARL = Namespace("http://www.w3.org/ns/earl#")
SPDX = Namespace("http://spdx.org/rdf/terms#")
SCHEMA = Namespace("https://schema.org/")
WD = Namespace("http://www.wikidata.org/entity/")
REPO = "https://github.com/ImSounic/fair-ut-group33/blob/main/"
APPENDIX_URL = ("https://www.forumstandaardisatie.nl/sites/default/files/OBDO/2026/0611/"
                "20260611-1b-bijlage-meting-informatieveiligheidstandaarden-begin-2026-OBDO.html")
REPORT_URL = APPENDIX_URL.replace("1b-bijlage", "1a-rapport")
E = C.EDITION


def en(s):
    return Literal(s, lang="en")


def checksum(g, node, value):
    c = BNode()
    g.add((node, SPDX.checksum, c))
    g.add((c, RDF.type, SPDX.Checksum))
    g.add((c, SPDX.algorithm, SPDX.checksumAlgorithm_sha256))
    g.add((c, SPDX.checksumValue, Literal(value, datatype=XSD.hexBinary)))


def main():
    ext = json.loads((C.EXTRACTED_DIR / "extraction_log.json").read_text())
    att = json.loads((C.EXTRACTED_DIR / "attribution_log.json").read_text())
    man = json.loads((C.ROOT / "data" / "linking" / "manifest.json").read_text())
    sums = dict(reversed(line.split()) for line in (C.SOURCE_DIR / "SHA256SUMS").read_text().splitlines())
    g = Graph()
    for p, ns in (("d", D), ("ont", ONT), ("earl", EARL), ("prov", PROV), ("dct", DCTERMS), ("dcat", DCAT),
                  ("foaf", FOAF), ("spdx", SPDX), ("schema", SCHEMA), ("wd", WD)):
        g.bind(p, ns)

    # Agents
    forum, inl, me = D["forum-standaardisatie"], D["internetnl"], D["sounic-akkaraju"]
    g.add((forum, RDF.type, PROV.Organization))
    g.add((forum, RDF.type, FOAF.Organization))
    g.add((forum, FOAF.name, Literal("Forum Standaardisatie", lang="nl")))
    g.add((forum, FOAF.name, en("Netherlands Standardisation Forum")))
    g.add((forum, FOAF.homepage, URIRef("https://www.forumstandaardisatie.nl/")))
    g.add((forum, SCHEMA.sameAs, WD.Q135706416))
    g.add((inl, RDF.type, EARL.Software))
    g.add((inl, RDF.type, PROV.SoftwareAgent))
    g.add((inl, FOAF.name, Literal("Internet.nl")))
    g.add((inl, FOAF.homepage, URIRef("https://internet.nl/")))
    g.add((inl, SCHEMA.sameAs, WD.Q138768186))
    g.add((inl, PROV.actedOnBehalfOf, forum))
    g.add((inl, RDFS.comment, en("Open-source test suite for internet standards, used through its batch API. "
                                 "The release used for this measurement is not stated by the source.")))
    g.add((me, RDF.type, PROV.Person))
    g.add((me, RDF.type, FOAF.Person))
    g.add((me, FOAF.name, Literal("Sounic Akkaraju")))
    agents = {}
    for key, name, path in (("extract", "extract.py", "scripts/extract.py"),
                            ("attribute", "attribute.py", "scripts/attribute.py"),
                            ("openrefine", "OpenRefine 3.9.3 with RDF extension 1.6.0", "scripts/openrefine_rdf.py")):
        a = D[f"software-{key}"]
        agents[key] = a
        g.add((a, RDF.type, PROV.SoftwareAgent))
        g.add((a, FOAF.name, Literal(name)))
        g.add((a, DCTERMS.source, URIRef(REPO + path)))
        g.add((a, PROV.actedOnBehalfOf, me))

    # Source entities
    snap = D["snapshot-appendix"]
    g.add((snap, RDF.type, PROV.Entity))
    g.add((snap, RDFS.label, en("Snapshot of the appendix 'Bijlage: individuele resultaten per internetdomein "
                                "begin 2026'")))
    g.add((snap, PROV.hadPrimarySource, URIRef(APPENDIX_URL)))
    g.add((snap, DCTERMS.date, Literal("2026-10-01", datatype=XSD.date)))
    g.add((snap, DCTERMS.license, URIRef("http://creativecommons.org/publicdomain/zero/1.0/")))
    g.add((snap, RDFS.comment, en("Retrieved on 2026-09-30 and again on 2026-10-01 with an identical SHA-256. "
                                  "Licence: CC0 1.0, declared site-wide by the publisher.")))
    checksum(g, snap, ext["source"]["sha256"])
    rep = D["snapshot-report"]
    g.add((rep, RDF.type, PROV.Entity))
    g.add((rep, RDFS.label, en("Snapshot of the report 'Meting Informatieveiligheidstandaarden begin 2026'")))
    g.add((rep, PROV.hadPrimarySource, URIRef(REPORT_URL)))
    g.add((rep, DCTERMS.date, Literal("2026-10-01", datatype=XSD.date)))
    checksum(g, rep, sums[REPORT_URL.rsplit("/", 1)[1]])
    exports = {}
    for key, label, primary in (("wikidata_municipalities", "Wikidata export: municipalities of the Netherlands",
                                 "https://www.wikidata.org/"),
                                ("nora_standards", "NORA export: standards on the comply-or-explain list",
                                 "https://www.noraonline.nl/"),
                                ("cbs_gemeenten_2026", "CBS export: municipalities in 2026 (StatLine 86247NED)",
                                 "https://opendata.cbs.nl/")):
        m = man[key]
        x = D["export-" + key.replace("_", "-")]
        exports[key] = x
        g.add((x, RDF.type, PROV.Entity))
        g.add((x, RDFS.label, en(label)))
        g.add((x, PROV.hadPrimarySource, URIRef(primary)))
        g.add((x, PROV.generatedAtTime, Literal(m["retrieved"], datatype=XSD.dateTime)))
        g.add((x, DCTERMS.source, URIRef(REPO + (m.get("query") or f"scripts/freeze_linking.py"))))
        checksum(g, x, m["sha256"])
    tables = D[f"extracted-tables-{E}"]
    g.add((tables, RDF.type, PROV.Entity))
    g.add((tables, RDFS.label, en("Extracted municipal web and e-mail tables, labels corrected")))
    for f in ("municipal_web.csv", "municipal_mail.csv", "results_long.csv"):
        part = D[f"file-{f}"]
        g.add((tables, DCTERMS.hasPart, part))
        g.add((part, RDF.type, PROV.Entity))
        g.add((part, RDFS.label, Literal(f)))
        checksum(g, part, ext["outputs"][f])

    # Activities
    meas = D[f"measurement-{E}"]
    g.add((meas, RDF.type, PROV.Activity))
    g.add((meas, RDFS.label, en("Measurement of information security standards, begin 2026")))
    g.add((meas, RDFS.label, Literal("Meting Informatieveiligheidstandaarden begin 2026", lang="nl")))
    g.add((meas, PROV.wasAssociatedWith, inl))
    g.add((meas, PROV.wasAssociatedWith, forum))
    period = BNode()
    g.add((meas, DCTERMS.temporal, period))
    g.add((period, RDF.type, DCTERMS.PeriodOfTime))
    g.add((period, DCAT.endDate, Literal(C.REFERENCE_DATE, datatype=XSD.date)))
    g.add((meas, RDFS.comment, en("Bulk test of government internet domains through the Internet.nl API. The "
                                  "results reflect the state on 31 December 2025; the source does not state the "
                                  "test dates, so the reference date is used as dct:date of every result.")))
    g.add((meas, DCTERMS.source, URIRef(REPORT_URL)))

    extr = D[f"extraction-{E}"]
    g.add((extr, RDF.type, PROV.Activity))
    g.add((extr, RDFS.label, en("Extraction of the municipal tables from the appendix")))
    g.add((extr, PROV.used, snap))
    g.add((extr, PROV.wasAssociatedWith, agents["extract"]))
    g.add((tables, PROV.wasGeneratedBy, extr))

    corr = D[f"label-correction-{E}"]
    g.add((corr, RDF.type, PROV.Activity))
    g.add((corr, RDFS.label, en("Correction of two mislabelled web columns")))
    g.add((corr, PROV.wasInformedBy, extr))
    g.add((corr, PROV.used, snap))
    g.add((corr, PROV.used, rep))
    g.add((corr, PROV.wasAssociatedWith, agents["extract"]))
    g.add((corr, RDFS.comment, en(
        "In all 16 web tables of the appendix, columns 3 and 4 are labelled 'IPv6 web' and 'RPKI web', repeating "
        "the labels of columns 6 and 7. They are relabelled 'HTTPS redirect' and 'HSTS': the legend lists the web "
        "tests in that order; the duplicated columns hold different values; the 2025 edition had neither test; and "
        "chart 33 of the report puts HTTPS redirect adoption among municipalities (95%) above HSTS (91%), the "
        "order of columns 3 and 4.")))

    excl = D[f"exclusion-{E}"]
    g.add((excl, RDF.type, PROV.Activity))
    g.add((excl, RDFS.label, en("Exclusion of one host name that contains a personal name")))
    g.add((excl, PROV.wasInformedBy, extr))
    g.add((excl, PROV.wasAssociatedWith, agents["extract"]))
    g.add((excl, RDFS.comment, en(
        f"One municipal subdomain contains the name of a living person and is left out of all derived data "
        f"(data minimisation): {ext['excluded']['rows_per_table']['web']} web and "
        f"{ext['excluded']['rows_per_table']['mail']} e-mail row. The host is matched by the SHA-256 of its name, "
        f"so the name is not repeated: {ext['excluded']['sha256'][0]}.")))

    link = D[f"linking-{E}"]
    g.add((link, RDF.type, PROV.Activity))
    g.add((link, RDFS.label, en("Attribution of hosts to municipalities")))
    for x in (exports["wikidata_municipalities"], exports["cbs_gemeenten_2026"], tables):
        g.add((link, PROV.used, x))
    g.add((link, PROV.wasAssociatedWith, agents["attribute"]))
    assoc = BNode()
    g.add((link, PROV.qualifiedAssociation, assoc))
    g.add((assoc, RDF.type, PROV.Association))
    g.add((assoc, PROV.agent, agents["attribute"]))
    for r in ("R1-official-host", "R2-official-domain", "R3-name-domain", "R4-name-label"):
        g.add((assoc, PROV.hadPlan, ONT[r]))
    c = att["counts"]
    g.add((link, RDFS.comment, en(
        f"Rules version {att['rules_version']}. {att['hosts']} hosts: R1 {c['R1']}, R2 {c['R2']}, R3 {c['R3']}, "
        f"R4 {c['R4']}, ambiguous {c['ambiguous']}, not attributed {c['none']} (coverage "
        f"{round(100 * att['coverage'], 1)}%). The municipal set was checked against CBS 2026 (342 codes).")))

    trip = D[f"triplification-{E}"]
    g.add((trip, RDF.type, PROV.Activity))
    g.add((trip, RDFS.label, en("Triplification with the OpenRefine RDF extension")))
    g.add((trip, PROV.used, tables))
    g.add((trip, PROV.wasInformedBy, link))
    g.add((trip, PROV.wasAssociatedWith, agents["openrefine"]))

    # The data document itself
    doc = URIRef(C.BASE + "data")
    g.add((doc, RDF.type, PROV.Entity))
    g.add((doc, DCTERMS.title, en("Municipal results of the Dutch information security standards measurement, "
                                  "begin 2026, as linked data")))
    g.add((doc, DCTERMS.creator, me))
    g.add((doc, DCTERMS.license, URIRef("http://creativecommons.org/publicdomain/zero/1.0/")))
    g.add((doc, DCTERMS.conformsTo, URIRef("http://www.w3.org/ns/earl#")))
    g.add((doc, DCTERMS.conformsTo, URIRef(C.ONT_IRI)))
    g.add((doc, DCTERMS.source, URIRef(APPENDIX_URL)))
    g.add((doc, PROV.wasDerivedFrom, snap))
    g.add((doc, PROV.wasGeneratedBy, trip))
    for a in (extr, corr, excl, link):
        g.add((doc, PROV.wasInfluencedBy, a))

    out = C.ROOT / "data" / "rdf"
    out.mkdir(parents=True, exist_ok=True)
    g.serialize(out / "prov.ttl", format="turtle")
    print(f"prov.ttl: {len(g)} triples")


if __name__ == "__main__":
    main()

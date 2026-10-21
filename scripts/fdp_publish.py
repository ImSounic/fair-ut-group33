"""Describe the dataset in the local FAIR Data Point (Tasks 4 and 5).

1. Release the DCAT-AP-NL versions of the Resource, Catalog, Dataset and Distribution schemas
   (fdp/schemas/*.ttl) as version 1.1.0.
2. Describe the FAIR Data Point itself, and create (or update) one catalog, the dataset and four
   distributions: the source HTML snapshot, the two extracted CSV tables and the FAIRified Turtle.
3. Publish the records. Their IRIs are kept in fdp/records.json, so a second run updates them.

Credentials: FDP_EMAIL and FDP_PASSWORD (default: the FDP's documented factory account).
Run: .venv/bin/python scripts/fdp_publish.py
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, PROV, RDF, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

API = os.environ.get("FDP_API", "http://127.0.0.1:8085")
FDP = C.BASE + "fdp"
SCHEMAS = C.ROOT / "fdp" / "schemas"
RECORDS = C.ROOT / "fdp" / "records.json"
SCHEMA_VERSION = "1.1.0"
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
DCAT_VERSION = URIRef("http://www.w3.org/ns/dcat#version")  # DCAT 3 term, absent from rdflib's DCAT
SPDX = Namespace("http://spdx.org/rdf/terms#")
EU = "http://publications.europa.eu/resource/authority/"
IANA = "https://www.iana.org/assignments/media-types/"
CC0 = URIRef("http://creativecommons.org/publicdomain/zero/1.0/deed.nl")
SITE = "https://imsounic.github.io/fair-ut-group33/"
REPO = "https://github.com/ImSounic/fair-ut-group33"
APPENDIX_URL = ("https://www.forumstandaardisatie.nl/sites/default/files/OBDO/2026/0611/"
                "20260611-1b-bijlage-meting-informatieveiligheidstandaarden-begin-2026-OBDO.html")
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

s = requests.Session()


def login():
    r = s.post(f"{API}/tokens", json={"email": os.environ.get("FDP_EMAIL", "albert.einstein@example.com"),
                                      "password": os.environ.get("FDP_PASSWORD", "password")})
    r.raise_for_status()
    s.headers["Authorization"] = "Bearer " + r.json()["token"]


# --- schemas --------------------------------------------------------------------------------------

def release_schemas():
    existing = {x["latest"]["name"]: x for x in s.get(f"{API}/metadata-schemas", headers={"Accept": "application/json"}).json()}
    for name in ("Resource", "Catalog", "Dataset", "Distribution"):
        latest = existing[name]["latest"]
        definition = (SCHEMAS / f"{name.lower()}.ttl").read_text()
        if latest["version"] == SCHEMA_VERSION and latest["definition"] == definition:
            continue
        uuid = latest["uuid"]
        draft = s.get(f"{API}/metadata-schemas/{uuid}/draft", headers={"Accept": "application/json"}).json()
        draft["definition"] = definition
        draft["description"] = "DCAT-AP-NL 3.0 additions (FAIR Data Engineering, Group 33)"
        r = s.put(f"{API}/metadata-schemas/{uuid}/draft", json=draft)
        assert r.ok, (name, r.status_code, r.text[:500])
        r = s.post(f"{API}/metadata-schemas/{uuid}/versions",
                   json={"version": SCHEMA_VERSION, "description": draft["description"], "published": False})
        assert r.ok, (name, r.status_code, r.text[:500])
        print(f"schema {name}: released {SCHEMA_VERSION}")


# --- records --------------------------------------------------------------------------------------

def common(g, node, title_en, title_nl, desc_en, desc_nl):
    g.add((node, DCTERMS.title, Literal(title_en, lang="en")))
    g.add((node, DCTERMS.title, Literal(title_nl, lang="nl")))
    g.add((node, DCTERMS.description, Literal(desc_en, lang="en")))
    g.add((node, DCTERMS.description, Literal(desc_nl, lang="nl")))
    pub = BNode()
    g.add((node, DCTERMS.publisher, pub))
    g.add((pub, RDF.type, FOAF.Agent))
    g.add((pub, FOAF.name, Literal("Sounic Akkaraju, University of Twente (FAIR Data Engineering, Group 33)")))
    g.add((node, DCAT_VERSION, Literal("1.0")))
    g.add((node, DCTERMS.language, URIRef(EU + "language/ENG")))
    g.add((node, DCTERMS.language, URIRef(EU + "language/NLD")))
    g.add((node, DCTERMS.license, CC0))


def contact(g, node):
    c = BNode()
    g.add((node, DCAT.contactPoint, c))
    g.add((c, RDF.type, VCARD.Kind))
    g.add((c, VCARD.fn, Literal("Sounic Akkaraju (FAIR Data Engineering, Group 33)")))
    g.add((c, VCARD.hasURL, URIRef(REPO + "/issues")))


def file_facts(path: Path):
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def catalog_graph(node, parent):
    g = Graph()
    g.add((node, RDF.type, DCAT.Catalog))
    common(g, node, "Dutch government information security measurements, FAIRified",
           "Metingen informatieveiligheid van de Nederlandse overheid, FAIR gemaakt",
           "Catalogue of the FAIRified results of the half-yearly measurement of mandatory internet security "
           "standards (Meting Informatieveiligheidstandaarden) of Forum Standaardisatie, made in the FAIR Data "
           "Engineering course of the University of Twente.",
           "Catalogus van de FAIR gemaakte resultaten van de halfjaarlijkse Meting Informatieveiligheidstandaarden "
           "van Forum Standaardisatie, gemaakt in de cursus FAIR Data Engineering van de Universiteit Twente.")
    g.add((node, FOAF.homepage, URIRef(SITE)))
    g.add((node, DCAT.themeTaxonomy, URIRef(EU + "data-theme")))
    contact(g, node)
    g.add((node, DCTERMS.isPartOf, URIRef(parent)))
    return g


def dataset_graph(node, parent, identifier):
    g = Graph()
    g.add((node, RDF.type, DCAT.Dataset))
    common(g, node, "Municipal results of the information security standards measurement, begin 2026",
           "Gemeentelijke resultaten van de Meting Informatieveiligheidstandaarden begin 2026",
           "Per-host results of the begin-2026 edition of the measurement of mandatory internet security standards "
           "by Forum Standaardisatie for the internet domains of Dutch municipalities: 26,064 results of 14 tests "
           "(web: TLS, HTTPS redirect, HSTS, DNSSEC, IPv6, RPKI; e-mail: DKIM, DMARC, SPF, STARTTLS, DNSSEC MX, "
           "DANE, IPv6 MX, RPKI MX) for 1,867 hosts, reference date 31 December 2025. Each result is a W3C EARL "
           "assertion; hosts are attributed to municipalities (TOOI, Wikidata) by explicit rules and tests are "
           "linked to the standards they check (NORA). Two mislabelled columns of the source are corrected and "
           "one host name containing a personal name is excluded; both are recorded as provenance. The publisher "
           "intends a half-yearly measurement; no mid-2025 edition was published.",
           "Resultaten per host van de Meting Informatieveiligheidstandaarden begin 2026 van Forum "
           "Standaardisatie voor de internetdomeinen van Nederlandse gemeenten: 26.064 resultaten van 14 tests "
           "voor 1.867 hosts, peildatum 31 december 2025, als W3C EARL-beweringen, gekoppeld aan gemeenten "
           "(TOOI, Wikidata) en aan de standaarden die de tests toetsen (NORA).")
    g.add((node, DCAT.theme, URIRef(EU + "data-theme/GOVE")))
    contact(g, node)
    for k in ("information security", "internet standards", "municipalities", "Netherlands", "EARL",
              "informatieveiligheid", "gemeenten"):
        g.add((node, DCAT.keyword, Literal(k)))
    g.add((node, DCAT.landingPage, URIRef(SITE)))
    g.add((node, DCTERMS.identifier, Literal(identifier)))
    g.add((node, DCTERMS.accessRights, URIRef(EU + "access-right/PUBLIC")))
    g.add((node, DCTERMS.creator, URIRef(C.DATA_NS + "sounic-akkaraju")))
    g.add((node, DCTERMS.spatial, URIRef(EU + "country/NLD")))
    period = BNode()
    g.add((node, DCTERMS.temporal, period))
    g.add((period, RDF.type, DCTERMS.PeriodOfTime))
    g.add((period, DCAT.startDate, Literal(C.REFERENCE_DATE, datatype=XSD.date)))
    g.add((period, DCAT.endDate, Literal(C.REFERENCE_DATE, datatype=XSD.date)))
    g.add((node, FOAF.page, URIRef(REPO)))
    g.add((node, DCTERMS.accrualPeriodicity, URIRef(EU + "frequency/ANNUAL_2")))
    # The source page is linked through prov:wasDerivedFrom (snapshot -> prov:hadPrimarySource), not
    # dct:source, whose range in DCAT-AP-NL 3.0 is dcat:Dataset.
    g.add((node, PROV.wasDerivedFrom, URIRef(C.DATA_NS + "snapshot-appendix")))
    g.add((node, DCTERMS.issued, Literal(NOW, datatype=XSD.dateTime)))
    g.add((node, DCTERMS.modified, Literal(NOW, datatype=XSD.dateTime)))
    g.add((node, DCTERMS.isPartOf, URIRef(parent)))
    return g


DISTRIBUTIONS = [
    {"key": "source-html", "file": C.APPENDIX, "pid": "source/" + C.APPENDIX.name, "media": "text/html",
     "format": "HTML", "conforms": [],
     "title": ("Source appendix (HTML snapshot)", "Bronbijlage (HTML-momentopname)"),
     "desc": ("The appendix as published by Forum Standaardisatie, deposited unchanged (all 16 government groups). "
              "Retrieved on 2026-09-30 and 2026-10-01 with identical checksums.",
              "De bijlage zoals gepubliceerd door Forum Standaardisatie, ongewijzigd gedeponeerd.")},
    {"key": "csv-web", "file": C.EXTRACTED_DIR / "municipal_web.csv", "pid": "dist/municipal_web.csv",
     "media": "text/csv", "format": "CSV", "conforms": [],
     "title": ("Extracted municipal web table (CSV)", "Geëxtraheerde gemeentelijke webtabel (CSV)"),
     "desc": ("Section 3.15 of the appendix as CSV: 1,856 hosts and 6 web tests. Columns 3 and 4 carry the corrected "
              "labels HTTPS redirect and HSTS (published as IPv6 web and RPKI web); one host is excluded.",
              "Paragraaf 3.15 van de bijlage als CSV, met gecorrigeerde kolomnamen.")},
    {"key": "csv-mail", "file": C.EXTRACTED_DIR / "municipal_mail.csv", "pid": "dist/municipal_mail.csv",
     "media": "text/csv", "format": "CSV", "conforms": [],
     "title": ("Extracted municipal e-mail table (CSV)", "Geëxtraheerde gemeentelijke e-mailtabel (CSV)"),
     "desc": ("Section 4.15 of the appendix as CSV: 1,866 hosts and 8 e-mail tests; one host is excluded.",
              "Paragraaf 4.15 van de bijlage als CSV.")},
    {"key": "turtle", "file": C.ROOT / "data" / "rdf" / "fairified.ttl", "pid": "dist/fairified.ttl",
     "access": C.BASE + "data", "media": "text/turtle", "format": "RDF_TURTLE",
     "conforms": ["http://www.w3.org/ns/earl#", C.ONT_IRI],
     "title": ("FAIRified data (RDF, Turtle)", "FAIR gemaakte data (RDF, Turtle)"),
     "desc": ("26,064 EARL assertions and results, 1,867 hosts, 1,388 host attributions, 342 municipalities and the "
              "provenance of the measurement, extraction, correction and linking, in Turtle.",
              "26.064 EARL-beweringen met resultaten, hosts, toewijzingen, gemeenten en herkomst, in Turtle.")},
]


def distribution_graph(node, parent, d):
    g = Graph()
    g.add((node, RDF.type, DCAT.Distribution))
    common(g, node, *d["title"], *d["desc"])
    sha, size = file_facts(d["file"])
    g.add((node, DCAT.accessURL, URIRef(d.get("access", C.BASE + d["pid"]))))
    g.add((node, DCAT.downloadURL, URIRef(C.BASE + d["pid"])))
    g.add((node, DCAT.mediaType, URIRef(IANA + d["media"])))
    g.add((node, DCTERMS.format, URIRef(EU + "file-type/" + d["format"])))
    g.add((node, DCAT.byteSize, Literal(size, datatype=XSD.nonNegativeInteger)))
    for c in d["conforms"]:
        g.add((node, DCTERMS.conformsTo, URIRef(c)))
    cs = BNode()
    g.add((node, SPDX.checksum, cs))
    g.add((cs, RDF.type, SPDX.Checksum))
    g.add((cs, SPDX.algorithm, SPDX.checksumAlgorithm_sha256))
    g.add((cs, SPDX.checksumValue, Literal(sha, datatype=XSD.hexBinary)))
    g.add((node, DCTERMS.issued, Literal(NOW, datatype=XSD.dateTime)))
    g.add((node, DCTERMS.isPartOf, URIRef(parent)))
    return g


def to_turtle(g: Graph, node: URIRef, base: str) -> str:
    """Serialise with the new record as the relative IRI <> (the FDP mints the IRI on creation)."""
    g2 = Graph()
    for s_, p, o in g:
        g2.add((URIRef(base) if s_ == node else s_, p, URIRef(base) if o == node else o))
    return g2.serialize(format="turtle")


def save(prefix: str, key: str, records: dict, build) -> str:
    """Create the record (POST) or update it (PUT); return its IRI."""
    hdr = {"Content-Type": "text/turtle", "Accept": "text/turtle"}
    if key in records:
        iri = records[key]
        r = s.put(f"{API}/{prefix}/{iri.rsplit('/', 1)[1]}", data=to_turtle(build(URIRef(iri)), URIRef(iri), iri).encode(),
                  headers=hdr)
        assert r.ok, (key, r.status_code, r.text[:800])
        return iri
    tmp = URIRef("http://example.org/new")
    r = s.post(f"{API}/{prefix}", data=to_turtle(build(tmp), tmp, "").encode(), headers=hdr)
    assert r.ok, (key, r.status_code, r.text[:800])
    iri = r.headers.get("Location") or next(
        str(x) for x in Graph().parse(data=r.text, format="turtle").subjects(RDF.type, None)
        if str(x).startswith(f"{FDP}/{prefix}/"))
    records[key] = iri
    RECORDS.write_text(json.dumps(records, indent=1) + "\n")
    return iri


def publish(iri: str):
    path = iri[len(FDP):]
    r = s.put(f"{API}{path}/meta/state", json={"current": "PUBLISHED"})
    assert r.ok or "already published" in r.text, (iri, r.status_code, r.text[:300])


def describe_fdp():
    """Replace the placeholder title, description and publisher of the FAIR Data Point record."""
    r = s.get(f"{API}/", headers={"Accept": "text/turtle"})
    g = Graph().parse(data=r.text, format="turtle")
    root = URIRef(FDP)
    for p in (DCTERMS.title, DCTERMS.description, URIRef("http://www.w3.org/2000/01/rdf-schema#label")):
        g.remove((root, p, None))
    for o in list(g.objects(root, DCTERMS.publisher)):
        g.remove((o, None, None))
        g.remove((root, DCTERMS.publisher, o))
    common(g, root, "FAIR Data Point of Group 33, FAIR Data Engineering (University of Twente)",
           "FAIR Data Point van groep 33, FAIR Data Engineering (Universiteit Twente)",
           "Metadata about the FAIRified municipal results of the Dutch information security standards measurement.",
           "Metadata over de FAIR gemaakte gemeentelijke resultaten van de Meting Informatieveiligheidstandaarden.")
    g.remove((root, DCAT_VERSION, Literal("1.0")))  # common() adds one; keep the FDP's own version value
    r = s.put(f"{API}/", data=g.serialize(format="turtle").encode(),
              headers={"Content-Type": "text/turtle", "Accept": "text/turtle"})
    assert r.ok, (r.status_code, r.text[:500])


def main():
    login()
    release_schemas()
    describe_fdp()
    records = json.loads(RECORDS.read_text()) if RECORDS.exists() else {}
    cat = save("catalog", "catalog", records, lambda n: catalog_graph(n, FDP))
    ds = save("dataset", "dataset", records, lambda n: dataset_graph(n, cat, records.get("dataset", "")))
    ds = save("dataset", "dataset", records, lambda n: dataset_graph(n, cat, ds))  # identifier = own IRI
    for d in DISTRIBUTIONS:
        save("distribution", "distribution-" + d["key"], records, lambda n, d=d: distribution_graph(n, ds, d))
    for key, iri in records.items():
        publish(iri)
    print(json.dumps(records, indent=1))


if __name__ == "__main__":
    main()

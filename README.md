# FAIRified municipal results of the Dutch information security standards measurement

FAIR Data Engineering project, University of Twente, 2026. Group 33 (Sounic Akkaraju).

The appendix of Forum Standaardisatie's *Meting Informatieveiligheidstandaarden begin 2026*
publishes, per internet domain, whether Dutch government organisations apply the mandatory
internet security standards. It is available only as an HTML page. This project makes the
municipal results FAIR: 26,064 test results for 1,867 hosts and 14 tests, described with
W3C EARL, PROV-O and SKOS, linked to the municipalities (TOOI, Wikidata) and to the
standards they check (NORA), with metadata in a FAIR Data Point.

Persistent identifiers: `https://w3id.org/FAIR-course-UT/2026/group33/` (rules in `w3id/`).
Website: https://imsounic.github.io/fair-ut-group33/

## Layout

| Path | Content |
|---|---|
| `source/` | Checksummed snapshot of the source appendix and report |
| `scripts/extract.py` | Extracts the municipal tables, corrects two mislabelled columns |
| `scripts/freeze_linking.py` | Dated Wikidata, NORA and CBS exports in `data/linking/` |
| `scripts/attribute.py` | Rule-based attribution of hosts to municipalities |
| `scripts/build_ontology.py` | Builds `ontology/ont.ttl` from `ontology/src/` |
| `scripts/build_site.py` | Builds the GitHub Pages site in `docs/` |
| `data/extracted/` | Extracted tables, long-format results, hosts, attributions |
| `ontology/` | Ontology, its sources and the data model diagram |
| `w3id/` | Redirect rules and tests for the course PID relay |

Run the scripts with Python 3.12+ and `rdflib`, `lxml`, in this order: extract, freeze_linking
(optional, re-fetches the exports), attribute, build_ontology, build_site.

## Licences

Source data: CC0 1.0 (Forum Standaardisatie). Data and metadata of this project: CC0 1.0.
Ontology: CC BY 4.0. Code: MIT (see `LICENSE`).

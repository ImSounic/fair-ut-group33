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
| `scripts/openrefine_rdf.py` | Triplifies the tables in OpenRefine with the RDF extension (skeletons in the projects) |
| `scripts/build_prov.py` | Builds `data/rdf/prov.ttl`: agents, activities and source entities (PROV-O) |
| `scripts/merge_rdf.py` | Merges and checks the RDF into `data/rdf/fairified.ttl` |
| `scripts/fdp_publish.py`, `fdp_export.py` | Metadata records in the FAIR Data Point, exported to `docs/fdp/` |
| `scripts/validate_metadata.py` | Validates the records against DCAT-AP 3.0 and DCAT-AP-NL 3.0 |
| `scripts/build_linking_rdf.py` | NORA standards and the specification supplement as RDF |
| `scripts/run_cqs.py` | Loads named graphs into Apache Jena Fuseki and answers the competency questions |
| `scripts/build_site.py` | Builds the GitHub Pages site in `docs/` |
| `data/extracted/` | Extracted tables, long-format results, hosts, attributions |
| `data/rdf/` | OpenRefine exports, provenance and the merged FAIRified data |
| `openrefine/` | OpenRefine project archives (operation history and RDF skeletons) |
| `ontology/` | Ontology, its sources and the data model diagram |
| `fdp/` | FAIR Data Point deployment configuration |
| `queries/cq/` | SPARQL for the competency questions and their results |
| `w3id/` | Redirect rules and tests for the course PID relay |

Run the scripts with Python 3.12+ and `rdflib`, `lxml`, `requests`, in this order: extract,
freeze_linking (optional, re-fetches the exports), attribute, build_ontology, openrefine_rdf (needs
OpenRefine 3.9 with the RDF extension 1.6), build_prov, merge_rdf, build_site.

## Licences

Source data: CC0 1.0 (Forum Standaardisatie). Data and metadata of this project: CC0 1.0.
Ontology: CC BY 4.0. Code: MIT (see `LICENSE`).

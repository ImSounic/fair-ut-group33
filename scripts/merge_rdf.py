"""Merge the OpenRefine exports and prov.ttl into data/rdf/fairified.ttl and check the result.

Checks: expected counts; every host, test, outcome code and municipality that is referenced is
defined; every website host has its six web results; and the graph reproduces the acceptance values
of competency questions 2 and 3 (129 and 287 of 342), computed from the RDF, not from the CSVs.
Run: .venv/bin/python scripts/merge_rdf.py
"""
import gzip
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

RDF_DIR = C.ROOT / "data" / "rdf"
PARTS = [RDF_DIR / "openrefine" / f"g33-{n}.ttl" for n in ("A-assertions", "B-hosts", "C-municipalities")]
PARTS.append(RDF_DIR / "prov.ttl")
EARL = Namespace("http://www.w3.org/ns/earl#")
ONT = Namespace(C.ONT_NS)
D = Namespace(C.DATA_NS)
EXPECTED = {"assertions": 26064, "results": 26064, "hosts": 1867, "attributions": 1388,
            "municipalities": 342, "provinces": 12, "service_domains": 46}
ACCEPT = {"cq2": 129, "cq3": 287}
CORE = {ONT[t] for t in ("dkim", "dmarc", "spf", "starttls", "dnssec_mx", "dane")}


def main():
    g = Graph()
    for p in PARTS:
        g.parse(p, format="turtle")
    ont = Graph().parse(C.ROOT / "ontology" / "ont.ttl")
    tests = set(ont.subjects(RDF.type, EARL.TestCase))
    codes = set(ont.subjects(SKOS.inScheme, ONT.OutcomeCodes))
    is_pass = set(ont.subjects(RDF.type, EARL.Pass))
    is_fail = set(ont.subjects(RDF.type, EARL.Fail))

    counts = {
        "assertions": len(set(g.subjects(RDF.type, EARL.Assertion))),
        "results": len(set(g.subjects(RDF.type, EARL.TestResult))),
        "hosts": len(set(g.subjects(RDF.type, ONT.Host))),
        "attributions": len(set(g.subjects(RDF.type, ONT.HostAttribution))),
        "municipalities": len(set(g.subjects(RDF.type, ONT.Municipality))),
        "provinces": len(set(g.subjects(RDF.type, ONT.Province))),
        "service_domains": len(set(g.subjects(RDF.type, ONT.ServiceDomain))),
    }
    assert counts == EXPECTED, counts

    hosts = set(g.subjects(RDF.type, ONT.Host))
    muns = set(g.subjects(RDF.type, ONT.Municipality))
    assert set(g.objects(None, EARL.subject)) <= hosts, "assertion about an undefined host"
    assert set(g.objects(None, EARL.test)) <= tests, "assertion with an undefined test"
    assert set(g.objects(None, EARL.outcome)) <= codes, "result with an undefined outcome code"
    assert set(g.objects(None, ONT.attributedTo)) <= muns, "attribution to an undefined municipality"
    assert set(g.objects(None, ONT.websiteHost)) | set(g.objects(None, ONT.mainMailDomain)) <= hosts
    for a in g.subjects(RDF.type, EARL.Assertion):
        assert len(list(g.objects(a, EARL.result))) == 1
    blank = {t for t in g if isinstance(t[0], BNode) or isinstance(t[2], BNode)}
    prov_graph = Graph().parse(RDF_DIR / "prov.ttl")
    assert len(blank) <= sum(1 for t in prov_graph if isinstance(t[0], BNode) or isinstance(t[2], BNode)), \
        "blank nodes outside prov.ttl"

    # Index the results: (host, test) -> outcome code.
    outcome = {}
    for a in g.subjects(RDF.type, EARL.Assertion):
        r = g.value(a, EARL.result)
        outcome[(g.value(a, EARL.subject), g.value(a, EARL.test))] = g.value(r, EARL.outcome)
    web_tests = set(ont.subjects(RDF.type, ONT.WebTest))
    for m in muns:
        for h in g.objects(m, ONT.websiteHost):
            assert all((h, t) in outcome for t in web_tests), f"website host {h} lacks web results"

    # Competency questions 2 and 3 on the graph.
    cq2 = {m for m in muns if any(outcome.get((g.value(m, ONT.mainMailDomain), t)) in is_fail for t in CORE)}
    cq3 = {m for m in muns if all(outcome[(h, t)] in is_pass for h in g.objects(m, ONT.websiteHost)
                                  for t in (ONT.https_redirect, ONT.hsts))}
    per_prov = defaultdict(lambda: [0, 0])
    for m in muns:
        p = str(g.value(g.value(m, ONT.inProvince), URIRef("http://www.w3.org/2000/01/rdf-schema#label")))
        per_prov[p][1] += 1
        per_prov[p][0] += m in cq3
    assert len(cq2) == ACCEPT["cq2"] and len(cq3) == ACCEPT["cq3"], (len(cq2), len(cq3))

    out = RDF_DIR / "fairified.ttl"
    g.namespace_manager.bind("d", D, override=True)
    g.namespace_manager.bind("ont", ONT, override=True)
    g.serialize(out, format="turtle")
    with open(out, "rb") as f, gzip.GzipFile(RDF_DIR / "fairified.ttl.gz", "wb", mtime=0) as z:
        z.write(f.read())
    log = {"triples": len(g), "counts": counts,
           "outcome_codes": dict(Counter(str(o).split("#")[1] for o in g.objects(None, EARL.outcome))),
           "cq2_municipalities_failing_core_mail_test": len(cq2),
           "cq3_municipalities_passing_https_redirect_and_hsts": len(cq3),
           "cq3_per_province": dict(sorted(per_prov.items())),
           "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (out, RDF_DIR / "fairified.ttl.gz")}}
    (RDF_DIR / "merge_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: log[k] for k in ("triples", "counts", "cq2_municipalities_failing_core_mail_test",
                                          "cq3_municipalities_passing_https_redirect_and_hsts")}, indent=1))


if __name__ == "__main__":
    main()

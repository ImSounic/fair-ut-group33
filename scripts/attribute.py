"""Attribute hosts to municipalities by explicit rules, and derive each municipality's main hosts.

Inputs:  data/extracted/hosts.csv, data/extracted/results_long.csv, data/linking/wikidata_municipalities.json
Outputs (data/extracted/):
  attribution.csv     one row per host: rule, municipality (TOOI, CBS, Wikidata), service domain
  municipalities.csv  one row per municipality: identifiers, province, main website and mail domain
  attribution_log.json

Rules (first match wins; d = host without one leading "www."; reg(x) = last two labels):
  R1 official host    d equals the host of an official website (Wikidata P856)
  R2 official domain  reg(d) equals the registrable domain of an official website
  R3 name domain      the first label of reg(d) is the normalised name of exactly one municipality
  R4 name label       d has >= 3 labels and its first label is the normalised name of exactly one
                      municipality; reg(d) is recorded as the service domain
  ambiguous           an R3/R4 key matches several municipalities (candidates are listed)
  none                no rule applies

Main website (decision D1, 13 Oct 2026): the host of P856, ignoring language subdomains and
preferring root URLs. If that host is a subdomain other than www (3 municipalities), the website is
the registrable domain instead. Website hosts = {bare, www.bare} present in the web table.
Main mail domain = the registrable form (without www.) of the main website.
"""
import collections
import csv
import hashlib
import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

LINKING = C.ROOT / "data" / "linking" / "wikidata_municipalities.json"
TOOI_BASE = "https://identifier.overheid.nl/tooi/id/"
RULES_VERSION = "1.0"
CORE_MAIL_TESTS = ("dkim", "dmarc", "spf", "starttls", "dnssec_mx", "dane")
PASS_CODES = {"passed", "info", "warning"}  # earl:Pass, following the publisher's counting rule


def strip_www(h: str) -> str:
    return h[4:] if h.startswith("www.") else h


def reg(h: str) -> str:
    return ".".join(h.split(".")[-2:])


def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def url_host(u: str) -> str:
    return (urllib.parse.urlparse(u).hostname or "").lower()


def load_municipalities():
    rows = json.loads(LINKING.read_bytes())["results"]["bindings"]
    mun = {}
    for b in rows:
        q = b["municipality"]["value"]
        m = mun.setdefault(q, {"qid": q, "label": b["label"]["value"], "tooi": TOOI_BASE + b["tooi"]["value"],
                               "cbs": "GM" + b["cbsCode"]["value"], "province": b["provinceLabel"]["value"],
                               "province_qid": b["province"]["value"], "sites": set()})
        m["sites"].add(b["website"]["value"])
    return mun


def main_host(urls) -> str:
    parts = [(url_host(u), urllib.parse.urlparse(u).path) for u in urls]
    parts = [(h, p) for h, p in parts if not re.match(r"^[a-z]{2}\.", h)]  # language subdomains
    cands = sorted({h for h, p in parts if p in ("", "/")}) or sorted({h for h, p in parts})
    assert len(cands) == 1, (urls, cands)
    return cands[0]


def main():
    mun = load_municipalities()
    hosts = list(csv.DictReader(open(C.EXTRACTED_DIR / "hosts.csv", encoding="utf-8")))
    host_set = {h["host"] for h in hosts}
    web_hosts = {h["host"] for h in hosts if h["in_web"] == "1"}

    official = {}
    for q, m in mun.items():
        for u in m["sites"]:
            h = strip_www(url_host(u))
            assert official.get(h, q) == q, f"official host {h} shared by two municipalities"
            official[h] = q
    offreg = collections.defaultdict(set)
    for h, q in official.items():
        offreg[reg(h)].add(q)
    assert all(len(v) == 1 for v in offreg.values()), "registrable domain shared by municipalities"
    keys = collections.defaultdict(set)
    for q, m in mun.items():
        keys[key(m["label"])].add(q)
    for h, q in official.items():
        k = key(reg(h).split(".")[0])
        if len(k) >= 4:
            keys[k].add(q)

    def attribute(h):
        d = strip_www(h)
        if d in official:
            return "R1", {official[d]}, ""
        if reg(d) in offreg:
            return "R2", offreg[reg(d)], ""
        m = keys.get(key(reg(d).split(".")[0]), set())
        if m:
            return ("R3" if len(m) == 1 else "ambiguous"), m, ""
        m = keys.get(key(d.split(".")[0]), set())
        if m and d.count(".") >= 2:
            return ("R4" if len(m) == 1 else "ambiguous"), m, reg(d)
        return "none", set(), ""

    # Main website and mail domain per municipality (decision D1).
    main_rows, website_of, mail_of = [], {}, {}
    adjusted = []
    for q, m in sorted(mun.items(), key=lambda x: x[1]["cbs"]):
        p856 = main_host(m["sites"])
        bare = strip_www(p856)
        if bare != reg(bare):  # non-www subdomain: use the registrable domain
            adjusted.append((m["label"], p856, reg(bare)))
            bare = reg(bare)
        site = sorted({bare, "www." + bare} & web_hosts)
        assert site, f"no website host of {m['label']} in the web table"
        assert bare in host_set, f"main mail domain {bare} not in the tables"
        website_of[q], mail_of[q] = site, bare
        main_rows.append([m["tooi"], m["cbs"], m["qid"], m["label"], m["province"], m["province_qid"],
                          p856, " ".join(site), bare])
    assert len(adjusted) == 3, adjusted

    out, counts = [], collections.Counter()
    for h in sorted(host_set):
        rule, ms, sd = attribute(h)
        counts[rule] += 1
        one = next(iter(ms)) if len(ms) == 1 and rule != "ambiguous" else None
        out.append([h, rule,
                    mun[one]["tooi"] if one else "", mun[one]["cbs"] if one else "",
                    mun[one]["qid"] if one else "", mun[one]["label"] if one else "",
                    sd, " ".join(sorted(mun[x]["tooi"] for x in ms)) if rule == "ambiguous" else "",
                    int(one is not None and h in website_of[one]), int(one is not None and mail_of[one] == h)])
    for q in mun:  # every main host must be attributed to its own municipality
        for h in website_of[q] + [mail_of[q]]:
            r = next(o for o in out if o[0] == h)
            assert r[2] == mun[q]["tooi"], (h, r)

    hdr_a = ["host", "rule", "municipality_tooi", "municipality_cbs", "municipality_wikidata",
             "municipality_label_nl", "service_domain", "candidates", "is_website_host", "is_main_mail_domain"]
    hdr_m = ["tooi", "cbs_code", "wikidata", "label_nl", "province_label_nl", "province_wikidata",
             "p856_main_host", "website_hosts", "main_mail_domain"]
    for name, hdr, rows in (("attribution.csv", hdr_a, out), ("municipalities.csv", hdr_m, main_rows)):
        with open(C.EXTRACTED_DIR / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(hdr)
            w.writerows(rows)

    # Acceptance values of CQ2 and CQ3 from the tables (re-checked later with SPARQL on the RDF).
    res = {(r["host"], r["test_slug"]): r["outcome_code"]
           for r in csv.DictReader(open(C.EXTRACTED_DIR / "results_long.csv", encoding="utf-8"))}
    cq2 = {q for q in mun if any(res.get((mail_of[q], t)) == "failed" for t in CORE_MAIL_TESTS)}
    cq3 = {q for q in mun if all(res[(h, t)] in PASS_CODES for h in website_of[q] for t in ("https_redirect", "hsts"))}
    per_prov = collections.Counter(mun[q]["province"] for q in mun)
    prov_ok = collections.Counter(mun[q]["province"] for q in cq3)
    service_domains = collections.Counter(o[6] for o in out if o[1] == "R4")
    log = {
        "rules_version": RULES_VERSION,
        "wikidata_export_sha256": hashlib.sha256(LINKING.read_bytes()).hexdigest(),
        "municipalities": len(mun), "hosts": len(out), "counts": dict(counts),
        "coverage": round(sum(counts[r] for r in ("R1", "R2", "R3", "R4")) / len(out), 4),
        "ambiguous": [[o[0], o[7]] for o in out if o[1] == "ambiguous"],
        "website_adjusted_to_registrable_domain": adjusted,
        "service_domains_r4": len(service_domains), "top_service_domains": service_domains.most_common(8),
        "cq2_municipalities_failing_core_mail_test": len(cq2),
        "cq3_municipalities_passing_https_redirect_and_hsts": len(cq3),
        "cq3_per_province": {p: [prov_ok[p], per_prov[p]] for p in sorted(per_prov)},
    }
    (C.EXTRACTED_DIR / "attribution_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(log, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

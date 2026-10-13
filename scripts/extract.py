"""Extract the municipal web and e-mail tables from the checksummed appendix snapshot.

Outputs (data/extracted/):
  municipal_web.csv, municipal_mail.csv  wide tables as published, two web labels corrected
  results_long.csv                       one row per host and test (input for OpenRefine)
  hosts.csv                              one row per host
  extraction_log.json                    checksums, counts, label correction, versions

Run: .venv/bin/python scripts/extract.py   (from the repository root or anywhere)
"""
import csv
import hashlib
import json
import platform
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import lxml
import lxml.html

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

# Published headers, duplicated labels included: the script stops if the publisher changes them.
TABLES = {
    "web": {
        "h3_id": "3_15_resultaten_webstandaarden_gemeenten",
        "heading": "3.15. resultaten webstandaarden gemeenten",
        "section": "3.15",
        "published": ["Domein", "TLS NCSC web", "IPv6 web", "RPKI web", "DNSSEC", "IPv6 web", "RPKI web"],
        "corrected": ["Domein", "TLS NCSC web", "HTTPS redirect", "HSTS", "DNSSEC", "IPv6 web", "RPKI web"],
        "slugs": [None, "tls", "https_redirect", "hsts", "dnssec", "ipv6_web", "rpki_web"],
        "rows": 1857,
    },
    "mail": {
        "h3_id": "4_15_resultaten_e-mailstandaarden_gemeenten",
        "heading": "4.15. resultaten e-mailstandaarden gemeenten",
        "section": "4.15",
        "published": ["Domein", "DKIM", "DMARC policy", "SPF policy", "STARTTLS NCSC", "DNSSEC MX", "DANE", "IPv6 MX", "RPKI MX"],
        "corrected": ["Domein", "DKIM", "DMARC policy", "SPF policy", "STARTTLS NCSC", "DNSSEC MX", "DANE", "IPv6 MX", "RPKI MX"],
        "slugs": [None, "dkim", "dmarc", "spf", "starttls", "dnssec_mx", "dane", "ipv6_mx", "rpki_mx"],
        "rows": 1867,
    },
}
HOST_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_heading(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\u2010", "-").replace("\u2011", "-")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().lower()


def norm_host(s: str) -> str:
    h = s.strip().lower().rstrip(".")
    if not h.isascii():
        h = h.encode("idna").decode("ascii")
    assert HOST_RE.match(h), f"invalid host name: {h!r}"
    return h


def parse_table(doc, spec):
    h3 = doc.xpath(f"//h3[@id='{spec['h3_id']}']")
    assert len(h3) == 1, f"heading {spec['h3_id']} not found exactly once"
    assert norm_heading(h3[0].text_content()) == spec["heading"], norm_heading(h3[0].text_content())
    table = h3[0].xpath("following-sibling::table[1]")[0]
    header = [th.text_content().strip() for th in table.xpath("./thead//th")]
    assert header == spec["published"], f"header changed: {header}"
    col_ids = [th.get("id") for th in table.xpath("./thead//th")]
    rows = []
    for tr in table.xpath("./tbody/tr"):
        th = tr.xpath("./th[@scope='row']")
        tds = tr.xpath("./td")
        assert len(th) == 1 and len(tds) == len(header) - 1
        row_id = th[0].get("id")
        values = []
        for col_id, td in zip(col_ids[1:], tds):
            assert td.get("headers") == f"{row_id} {col_id}", (row_id, col_id, td.get("headers"))
            v = td.text_content().strip()
            assert v in C.OUTCOME_CODES, f"unknown outcome code {v!r} in {row_id}"
            values.append(v)
        rows.append({"row_id": row_id, "host": norm_host(th[0].text_content()), "values": values})
    assert len(rows) == spec["rows"], (spec["section"], len(rows))
    hosts = [r["host"] for r in rows]
    assert len(set(hosts)) == len(hosts), "duplicate host in table"
    return col_ids, rows


def write_csv(path: Path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    raw = C.APPENDIX.read_bytes()
    assert sha256(raw) == C.APPENDIX_SHA256, "appendix snapshot does not match its checksum"
    doc = lxml.html.fromstring(raw.decode("utf-8"))
    C.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    parsed, excluded, long_rows, col_ids_of = {}, Counter(), [], {}
    for service, spec in TABLES.items():
        col_ids, rows = parse_table(doc, spec)
        col_ids_of[service] = col_ids
        kept = []
        for r in rows:
            if sha256(r["host"].encode("ascii")) in C.EXCLUDED_HOST_SHA256:
                excluded[service] += 1
                continue
            kept.append(r)
        assert excluded[service] == 1, f"exclusion must match exactly one {service} row"
        kept.sort(key=lambda r: r["host"])
        parsed[service] = kept
        write_csv(C.EXTRACTED_DIR / f"municipal_{service}.csv", spec["corrected"],
                  [[r["host"], *r["values"]] for r in kept])
        for r in kept:
            for i, v in enumerate(r["values"], start=1):
                corrected = spec["published"][i] != spec["corrected"][i]
                long_rows.append([
                    f"{C.EDITION}-{r['host']}-{spec['slugs'][i]}", r["host"], service, spec["slugs"][i],
                    spec["published"][i], spec["corrected"][i], "yes" if corrected else "",
                    v, spec["section"], r["row_id"], col_ids[i], C.EDITION, C.REFERENCE_DATE,
                ])

    long_rows.sort(key=lambda r: (r[1], r[2], r[3]))
    ids = [r[0] for r in long_rows]
    assert len(ids) == len(set(ids)), "assertion ids are not unique"
    assert len(long_rows) == 1856 * 6 + 1866 * 8 == 26064, len(long_rows)
    write_csv(C.EXTRACTED_DIR / "results_long.csv",
              ["assertion_id", "host", "service", "test_slug", "label_published", "label_corrected",
               "label_was_corrected", "outcome_code", "source_section", "source_row_id", "source_col_id",
               "edition", "reference_date"], long_rows)

    web = {r["host"] for r in parsed["web"]}
    mail = {r["host"] for r in parsed["mail"]}
    all_hosts = sorted(web | mail)
    bare = lambda h: h[4:] if h.startswith("www.") else h  # noqa: E731
    registrable = lambda h: ".".join(h.split(".")[-2:])  # noqa: E731
    write_csv(C.EXTRACTED_DIR / "hosts.csv",
              ["host", "bare_host", "registrable_domain", "in_web", "in_mail", "has_www_twin"],
              [[h, bare(h), registrable(h), int(h in web), int(h in mail),
                int((h.startswith("www.") and bare(h) in web | mail) or ("www." + h) in web | mail)]
               for h in all_hosts])

    outputs = sorted(C.EXTRACTED_DIR.glob("*.csv"))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=C.ROOT, capture_output=True,
                                text=True).stdout.strip() or None
    except OSError:
        commit = None
    log = {
        "source": {"file": C.APPENDIX.name, "sha256": C.APPENDIX_SHA256, "bytes": len(raw)},
        "edition": C.EDITION, "reference_date": C.REFERENCE_DATE,
        "rows_published": {s: t["rows"] for s, t in TABLES.items()},
        "rows_kept": {s: len(parsed[s]) for s in TABLES},
        "excluded": {"sha256": sorted(C.EXCLUDED_HOST_SHA256), "rows_per_table": dict(excluded),
                     "reason": "host name contains the name of a living person (data minimisation)"},
        "hosts": {"total": len(all_hosts), "web_only": len(web - mail), "mail_only": len(mail - web),
                  "both": len(web & mail)},
        "assertions": len(long_rows),
        "outcome_codes": {s: dict(Counter(v for r in parsed[s] for v in r["values"])) for s in TABLES},
        "label_correction": [
            {"table": s, "position": i + 1, "column_id": col_ids_of[s][i], "published": t["published"][i],
             "corrected": t["corrected"][i]}
            for s, t in TABLES.items() for i in range(len(t["published"]))
            if t["published"][i] != t["corrected"][i]],
        "outputs": {p.name: sha256(p.read_bytes()) for p in outputs},
        "software": {"python": platform.python_version(), "lxml": lxml.__version__, "git_commit": commit},
    }
    (C.EXTRACTED_DIR / "extraction_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: log[k] for k in ("rows_kept", "hosts", "assertions", "label_correction")}, indent=1))


if __name__ == "__main__":
    main()

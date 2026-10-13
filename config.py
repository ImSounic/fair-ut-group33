"""Single source of truth for identifiers and constants of the Group 33 FAIRification.

The w3id edition segment is an assumption until the lecturer confirms it: the 2025-2026
rules of the course namespace were retired on 2026-08-05 (perma-id/w3id.org PR #6501).
Changing BASE and re-running the pipeline re-mints every IRI.
"""
from pathlib import Path

BASE = "https://w3id.org/FAIR-course-UT/2026-2027/group33/"
DATA_NS = BASE + "data#"
ONT_NS = BASE + "ont#"
ONT_IRI = BASE + "ont"

EDITION = "2026H1"            # the "begin 2026" edition of the measurement
REFERENCE_DATE = "2025-12-31"  # results reflect the state on this date (report 1a, section 8)

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "source"
APPENDIX = SOURCE_DIR / "20260611-1b-bijlage-meting-informatieveiligheidstandaarden-begin-2026-OBDO.html"
APPENDIX_SHA256 = "27d0c4665a3b7bf15d9bbb6f7d44b0675a8eb2f988463ad89d55b03cd768ed04"
EXTRACTED_DIR = ROOT / "data" / "extracted"

# One municipal subdomain contains the name of a living person; it is excluded from all
# derived data (data minimisation). Matched by hash so the name is not repeated here.
EXCLUDED_HOST_SHA256 = {"84b089a62db0e1e8ba0482485f91972ae5578569196a4b768d70af651263adbf"}

OUTCOME_CODES = ("passed", "failed", "warning", "info", "error", "not_tested",
                 "no_mx", "not_applicable", "unreachable", "untestable")

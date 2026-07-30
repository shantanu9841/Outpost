"""Demo-mode source: seeded sample data behind the same Source interface.

This is what runs a business campaign to completion with zero keys pasted,
per the demo-mode non-negotiable. It is not a special case in discovery —
just another Source, and from its own point of view reading a bundled JSON
file never fails: search() always returns status=OK. Whether the caller is
using seed data as a genuine choice or as a fallback (and why) is something
only discover() knows — see app/sources/__init__.py.
"""

import json
from pathlib import Path

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "seeds"


class SeedSource(Source):
    name = "seed"

    def __init__(self, kind: str):
        self.kind = kind  # "business" or "creator"

    def search(self, brief: Brief) -> SourceResult:
        if self.kind != "business":
            # Creator seed data arrives in Slice 5.
            return SourceResult([], SourceStatus.OK, "seed", "seed", None)

        companies = json.loads((SEEDS_DIR / "companies.json").read_text())
        if brief.target_countries:
            companies = [c for c in companies if c.get("country") in brief.target_countries]
        candidates = [self._to_candidate(company) for company in companies]
        return SourceResult(candidates, SourceStatus.OK, "seed", "seed", None)

    def evidence(self, candidate: Candidate) -> dict:
        return candidate.raw

    @staticmethod
    def _to_candidate(company: dict) -> Candidate:
        location = ", ".join(
            part
            for part in (company.get("city"), company.get("state"), company.get("country"))
            if part
        ) or None

        return Candidate(
            source="seed",
            external_id=None,
            name=company["name"],
            handle_or_domain=company.get("domain"),
            reach=company.get("employees"),
            location=location,
            raw=company,
        )

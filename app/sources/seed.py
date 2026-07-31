"""Demo-mode source: seeded sample data behind the same Source interface.

This is what runs a business campaign to completion with zero keys pasted,
per the demo-mode non-negotiable. It is not a special case in discovery —
just another Source. Reading a bundled JSON file *usually* succeeds, but it
is still I/O over a real file, so this honors the Source "never raises"
contract: a missing file, invalid JSON, an unexpected top-level shape, or a
malformed row comes back as a typed SourceResult(status=SEED_ERROR), never an
exception. Whether seed data is a genuine choice or a fallback (and why) is
something only discover() knows — see app/sources/__init__.py.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.models import Brief, Candidate
from app.sources.base import Source, SourceResult, SourceStatus, coerce_int

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "seeds"


def normalize_evidence(raw: dict) -> dict:
    """Map a seed company row to the source-neutral evidence shape.

    Fit-scoring (app/agent/scoring.py) reads only this shape, never a seed
    row's own field names — so evidence reads identically regardless of
    which source produced the target.
    """
    return {
        "name": raw.get("name"),
        "industry": raw.get("industry"),
        "employees": coerce_int(raw.get("employees")),
        "country": raw.get("country"),
        "domain": raw.get("domain"),
    }


class SeedSource(Source):
    name = "seed"

    def __init__(self, kind: str):
        self.kind = kind  # "business" or "creator"

    def search(self, brief: Brief) -> SourceResult:
        if self.kind != "business":
            # Creator seed data arrives in Slice 5; nothing to read yet.
            return self._result([], SourceStatus.OK, None)

        try:
            raw_text = (SEEDS_DIR / "companies.json").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return self._result(
                [], SourceStatus.SEED_ERROR, f"could not read seed data ({type(exc).__name__})"
            )

        try:
            companies = json.loads(raw_text)
        except json.JSONDecodeError:
            return self._result([], SourceStatus.SEED_ERROR, "seed data was not valid JSON")

        if not isinstance(companies, list):
            return self._result(
                [], SourceStatus.SEED_ERROR, "seed data was not a list of companies"
            )

        if brief.target_countries:
            companies = [
                c
                for c in companies
                if isinstance(c, dict) and c.get("country") in brief.target_countries
            ]

        candidates = []
        for company in companies:
            if not isinstance(company, dict):
                return self._result(
                    [], SourceStatus.SEED_ERROR, "seed data contained a malformed row"
                )
            try:
                candidates.append(self._to_candidate(company))
            except (KeyError, TypeError, ValueError, ValidationError):
                return self._result(
                    [], SourceStatus.SEED_ERROR, "seed data contained a malformed company row"
                )
        return self._result(candidates, SourceStatus.OK, None)

    def _result(self, candidates, status, reason) -> SourceResult:
        return SourceResult(candidates, status, "seed", "seed", reason)

    def evidence(self, candidate: Candidate) -> dict:
        return normalize_evidence(candidate.raw)

    @staticmethod
    def _to_candidate(company: dict) -> Candidate:
        # Seed data is curated by us, not an external provider — a blank
        # name here is a genuine data-quality bug in seeds/companies.json,
        # not messy real-world input to paper over. Reject it through the
        # existing SEED_ERROR path (never persist a malformed target)
        # instead of silently substituting a fallback the way Apollo's
        # untrusted, external data does.
        name = company["name"]  # missing key -> KeyError -> SEED_ERROR, same as before
        if not isinstance(name, str) or not name.strip():
            raise ValueError("seed company row had a blank name")

        location = ", ".join(
            part
            for part in (company.get("city"), company.get("state"), company.get("country"))
            if part
        ) or None

        return Candidate(
            source="seed",
            external_id=None,
            name=name,
            handle_or_domain=company.get("domain"),
            reach=company.get("employees"),
            location=location,
            raw=company,
        )

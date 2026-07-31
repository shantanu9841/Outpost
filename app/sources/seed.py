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
from app.sources.base import Source, SourceResult, SourceStatus, canonical_name, coerce_int

SEEDS_DIR = Path(__file__).resolve().parent.parent.parent / "seeds"


def normalize_evidence(raw: dict) -> dict:
    """Map a seed company row to the source-neutral business evidence shape.

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


def normalize_creator_evidence(raw: dict) -> dict:
    """Map a seed creator row to the source-neutral creator evidence shape
    (SLICE_5_PLAN.md §6.1) — the same shape YouTubeSource/ApifySource
    produce, so scoring's creator heuristic reads identically regardless of
    which source produced the target.
    """
    return {
        "name": canonical_name(raw.get("name")),
        "niche": raw.get("niche"),
        "followers": coerce_int(raw.get("followers")),
        "country": raw.get("country"),
        "handle": raw.get("handle"),
        "platform": raw.get("_outpost_platform"),
    }


class SeedSource(Source):
    name = "seed"

    def __init__(self, kind: str):
        self.kind = kind  # "business" or "creator"

    def search(self, brief: Brief) -> SourceResult:
        if self.kind == "creator":
            return self._search_creators()
        return self._search_businesses(brief)

    def _search_businesses(self, brief: Brief) -> SourceResult:
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

    def _search_creators(self) -> SourceResult:
        # Unlike business seed, creator seed is never pre-filtered by
        # target_countries: SLICE_5_PLAN.md §7.4's geographic-mismatch row
        # must reach scoring so the heuristic's country component can score
        # it low with a truthful reason — filtering it out at discovery
        # would hide the exact discrimination the seed spread exists to
        # demonstrate.
        try:
            raw_text = (SEEDS_DIR / "creators.json").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            return self._result(
                [], SourceStatus.SEED_ERROR, f"could not read seed data ({type(exc).__name__})"
            )

        try:
            creators = json.loads(raw_text)
        except json.JSONDecodeError:
            return self._result([], SourceStatus.SEED_ERROR, "seed data was not valid JSON")

        if not isinstance(creators, list):
            return self._result(
                [], SourceStatus.SEED_ERROR, "seed data was not a list of creators"
            )

        candidates = []
        for creator in creators:
            if not isinstance(creator, dict):
                return self._result(
                    [], SourceStatus.SEED_ERROR, "seed data contained a malformed row"
                )
            try:
                candidates.append(self._to_creator_candidate(creator))
            except (KeyError, TypeError, ValueError, ValidationError):
                return self._result(
                    [], SourceStatus.SEED_ERROR, "seed data contained a malformed creator row"
                )
        return self._result(candidates, SourceStatus.OK, None)

    def _result(self, candidates, status, reason) -> SourceResult:
        return SourceResult(candidates, status, "seed", "seed", reason)

    def evidence(self, candidate: Candidate) -> dict:
        if self.kind == "creator":
            return normalize_creator_evidence(candidate.raw)
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

    _CREATOR_PLATFORMS = ("youtube", "instagram", "tiktok")

    @classmethod
    def _to_creator_candidate(cls, creator: dict) -> Candidate:
        # Same discipline as _to_candidate: seeds/creators.json is curated by
        # us, so a blank name or an unrecognized platform is a real
        # data-quality bug in that file, not messy external input — reject
        # it through SEED_ERROR rather than guessing a fallback.
        name = creator["name"]  # missing key -> KeyError -> SEED_ERROR
        if not isinstance(name, str) or not name.strip():
            raise ValueError("seed creator row had a blank name")

        platform = creator.get("platform")
        if platform not in cls._CREATOR_PLATFORMS:
            raise ValueError("seed creator row had an unrecognized platform")

        # Controlled provenance marker (SLICE_5_PLAN.md §6.1), set from the
        # row's own validated platform value — never left for a live
        # provider's raw field to set, the same rule YouTubeSource/
        # ApifySource follow for their own candidates.
        raw = {**creator, "_outpost_platform": platform}

        return Candidate(
            source="seed",
            external_id=None,
            name=name,
            handle_or_domain=creator.get("handle"),
            reach=coerce_int(creator.get("followers")),
            location=creator.get("country"),
            raw=raw,
        )

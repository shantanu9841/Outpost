# Slice 4 Plan — Drafting, approval queue, pipeline

Plan for Slice 4 (SPEC.md §6). This document is the single source of truth for
Slice 4's design. No implementation has started — this commit contains only
`SLICE_4_PLAN.md` and a `collaboration.md` log entry.

This is the **v2.2** plan: v1 (`2ded7e9`) was revised to v2 for seven
owner-approved SDE 2 corrections (§0.1), to v2.1 for five further
owner-flagged blocking findings against v2 (§0.2), then to v2.2 for two more
blocking findings against v2.1 (§0.3) — a real circular import in the shared
body-length validator, and a concurrency gap where "same transaction" made
each mutation atomic with its own audit but did not stop two concurrent
requests from both reading the same pre-mutation state. All fourteen tighten
Slice 4 toward the non-negotiables (#4 audit, #5 structured output, #6
isolation) and SPEC §4/§6's "references the cited evidence"; none expand scope
beyond SPEC.md.

## 0. Collaboration & model status

- **SDE 1** (this session) authored v1 on the stronger reasoning model
  (Opus 4.8), including the drafting prompt (§4.2), because the drafting voice is
  the one genuinely writing-heavy part of this slice and SPEC.md mandates
  applying the `beautiful-prose` and `humanizer` skills to it. The v2 revision
  was likewise a planning-only pass on Opus; **no code had changed.** The v2.1
  and v2.2 revisions — five, then two more, blocking findings against the prior
  version — were made on **Sonnet** after the owner switched the session; both
  remain planning-only (**no code has changed**) and every finding was grounded
  against the actually-committed Slice 2/3 code before being folded in, the
  same discipline the v2 pass used.
- Recommended **execution model: Sonnet** — with the prompt, state machines,
  grounding gate, and atomic-audit design settled here, implementation is
  mechanical. This is the model the owner has already switched to for this
  session; stated again at the top of implementation so the owner can
  reconfirm before code begins (CLAUDE.md).
- Per `collaboration.md` rule 6: implementation begins only after the owner
  confirms this plan has no further outstanding changes. §12 lists the
  interpretive decisions this plan makes, so the owner can veto any before code.
- **Precondition:** Slice 3 (and both hardening passes) is complete and committed
  (`fc5bc62` on `codex/sde-1-slice-2-hardening`, working tree clean, 100 tests
  green). Slice 4 builds on that state (branch choice — continue here vs. merge
  to `main` first — is the owner's call, per rule 6).
- Non-negotiables in play (CLAUDE.md): **#4 a human approves every send and
  every action is audited** — this is the slice where that rule earns its
  keep, and this plan makes each mutation and its audit row **atomic** (§8);
  #2 demo mode always completes (drafting must work with zero keys); #5
  structured output validated with retry; #6 workspace isolation, now enforced
  at the **database boundary**, not only in the route (§5, §6); the `memory`
  rule (draft once per target, then reuse — never silently re-draft a known
  target), now also backed by a **DB uniqueness guarantee** (§5); the
  `Local data` rule; and the `Not building` rule — **nothing sends.** Approving
  a draft changes a status. It never transmits a message.

### 0.1 What changed from v1 (the seven corrections)

1. **State machines are enforced, not just enum-validated.** Explicit draft and
   stage transition maps (§3.1) are shared by the DB guard, the routes, and the
   tests. Illegal transitions (e.g. `queued → live`, re-approving an approved
   draft) fail as controlled conflicts (409), never silently succeed and never
   write a misleading audit row.
2. **Approve commits the text currently in the textarea.** The approval submit
   carries the current textarea body; if it differs from the stored text it
   becomes `edited_body` in the *same* atomic operation that approves — a human
   never loses an unsaved edit by forgetting to press Save (§5 `approve_draft`,
   §6, §7.1).
3. **LLM drafts are grounded in the target's stored Slice 3 evidence, not just
   "names the company".** `OutreachDraft` now carries `evidence_key` /
   `evidence_value`; a runtime gate verifies the pair matches one of the
   target's stored grounded fit reasons, the body actually references that
   value, and the recipient identity is named when one exists (§4.1, §4.4).
4. **The heuristic states evidence neutrally and never invents fit.** No
   "the kind of partner we work best with"; it reports a fact from the stored
   evidence or the Brief and makes one concrete ask (§4.3).
5. **Campaign-detail links follow the draft lifecycle** — Draft outreach / Draft
   again / link-to-Approvals / link-to-Pipeline — and never link an approved or
   rejected draft to a queue page that excludes it (§6.2).
6. **Uniqueness and tenancy are enforced in the database.** `add_draft` uses an
   `INSERT … SELECT` tenancy guard, a partial unique index allows at most one
   non-rejected draft per `(workspace_id, target_id)`, and every join qualifies
   both `workspace_id`s (§5).
7. **Each mutation and its audit row commit in one transaction** (§8): on
   failure neither remains; on success exactly one audit row is written with the
   correct `workspace_id` / `campaign_id` / `target_id` / `draft_id`.

### 0.2 What changed from v2 to v2.1 (five blocking findings)

8. **A target can no longer be advanced by direct POST without an approved
   draft.** `set_target_stage` now requires a workspace-scoped approved draft
   for the target before allowing *any* transition, including the implicit
   first move off `queued` — closing a gap where the pipeline's stated
   approval gate (§3.1) was enforced only by `list_pipeline_targets` filtering
   what's *displayed*, not by what the DB would *accept* (§3.1, §5).
9. **The draft-creation route has a defined, scoped loader.** A new
   `db.get_target(workspace_id, target_id)` joins nothing extra by itself but
   is scoped identically to every other Slice 4 function; the route composes
   it with the existing `db.get_campaign` to build the `Brief` the drafting
   module needs, and both lookups are tested against a cross-workspace id (§5,
   §6).
10. **Human-submitted draft bodies are validated server-side**, not trusted as
    submitted. `save_draft_body` and `approve_draft` both reject a blank or
    over-long body before any mutation, via the same length bound
    `OutreachDraft.body_is_reasonable` already enforces on the model, made into
    one shared function both call (§4.1, §5).
11. **`draft.created`'s audit row now explains the drafting outcome.**
    `add_draft` takes the `DraftResult`'s `status` and `reason`, so the atomic
    audit row records whether Gemini succeeded, no key existed, the grounding
    gate rejected the model's draft, or a provider error caused the fallback —
    not just that *a* draft was created (§4, §5, §8).
12. **Only the specific active-draft race is swallowed.** `add_draft` catches
    `sqlite3.IntegrityError` and re-raises it as a dedicated
    `ActiveDraftExists` only when the failure matches the
    `one_active_draft_per_target` index; every other integrity failure
    propagates unmapped, so an unrelated constraint violation is never
    silently treated as a harmless double-submit (§5, §6).

### 0.3 What changed from v2.1 to v2.2 (two more blocking findings)

13. **The shared body-length validator moved to `app/models.py`, closing a
    real circular import.** v2.1 planned `validate_draft_body` inside
    `app/agent/drafting.py`, but `OutreachDraft` (which needs to call it from
    its own field validator) lives in `app/models.py` — `models → drafting →
    models`. The function now lives directly in `app/models.py`; `OutreachDraft`
    calls it in the same module (no import at all), and `db.py` imports it
    from `app.models`, exactly where `db.py` already imports `Candidate` from
    today. `drafting.py` needs no import of it whatsoever, since every
    `OutreachDraft` it constructs — LLM or heuristic — is validated by the
    schema at construction time (§4.1).
14. **"Same transaction" made a mutation atomic with its own audit row, but
    did not by itself stop two concurrent requests from both reading the same
    pre-mutation state and both succeeding.** `save_draft_body`, `approve_draft`,
    `reject_draft`, and `set_target_stage` no longer read the current
    status/stage in Python and then decide whether to write — each now issues
    one **conditional `UPDATE ... WHERE ... AND status/stage IN (allowed
    source states)`** and inspects `cursor.rowcount` to learn, atomically,
    whether the transition it asked for was actually legal *at the moment the
    write lock was granted* — not at the moment a prior read happened. This
    relies on SQLite's own default writer serialization (§5) rather than
    inventing a new locking scheme, and closes the race where two simultaneous
    approvals could both read `pending`, both "decide" it was legal, and both
    write a `draft.approved` audit row. Two new real two-connection retained
    tests (§11.1) exercise this directly.

---

## 1. Goal and done-when (SPEC.md §6)

Generate a personalized draft per target selected for outreach, referencing the
cited evidence. Drafts enter the approval queue as pending. A human edits,
approves, or rejects; each action is audited. Approved targets appear on a
pipeline board (queued, contacted, replied, live, declined) with stage changes
by button.

**Done when:** a draft can be generated, edited, approved or rejected with the
audit trail recording each step exactly once, and an approved target — showing
the approved (edited, if edited) text — appears on the pipeline board. Nothing
sends on its own.

---

## 2. What already exists (reused unchanged)

- `target` table already carries `stage TEXT NOT NULL DEFAULT 'queued'` (added
  in Slice 2's schema for exactly this slice) — the pipeline column lives here,
  **no migration to the target table needed**.
- `audit` table already carries `campaign_id`, `target_id`, and `draft_id`
  columns — draft and stage actions write to all of them directly, **no
  migration to the audit table needed**.
- The pipeline-stage design tokens (`--pl-queued` … `--pl-declined`, each with a
  `-subtle` background, in both themes) **already exist in `tokens.css`** — the
  board uses them directly, no token additions.
- `llm.generate_structured(schema, system, user, settings)` is reused unchanged
  for the LLM drafting path (returns a validated schema, `None` with no key, or
  raises `LLMError`). It retries **JSON/schema** failures with a corrective
  second attempt — it does **not** and cannot check semantic grounding (that is
  §4.4's job, layered on top). `GEMINI_MODEL` names the model for `model_used`.
- `target.fit_reasons_json` (grounded citations from Slice 3, already verified
  against real evidence by `scoring._is_grounded` and `assert_grounded` before
  persistence) is the evidence the draft references — no re-derivation, and the
  §4.4 gate reuses that already-verified grounding transitively.
- `app/sources/base.py`'s `DEFAULT_NAME` (`"Unknown company"`) is the canonical
  no-name sentinel every source collapses a blank name to — §4.4's identity
  logic tests against it rather than re-deriving the string.

The **only new table is `draft`** (SPEC.md §3), added idempotently in `db.init()`
like every other table, together with one partial unique index (§5). `eval`
remains a Slice 6 table and is not created here.

---

## 3. Data model — the `draft` table (`app/db.py`)

Added to `db.init()` as `CREATE TABLE IF NOT EXISTS` (additive, safe on every
startup, same pattern as the existing tables). Exactly SPEC.md §3's columns:

```sql
CREATE TABLE IF NOT EXISTS draft (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  INTEGER NOT NULL REFERENCES workspace(id),
    target_id     INTEGER NOT NULL REFERENCES target(id),
    body          TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',  -- pending|edited|approved|rejected
    edited_body   TEXT,
    model_used    TEXT,                                -- "gemini-3.6-flash" or "heuristic"
    cost_tokens   INTEGER,                             -- populated in Slice 6 (routing/cost)
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

And, in the same `init()`, a **partial unique index** enforcing at most one
non-rejected draft per target (correction 6):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS one_active_draft_per_target
    ON draft (workspace_id, target_id)
    WHERE status != 'rejected';
```

SQLite supports partial (`WHERE`-clause) unique indexes. A rejected draft is
excluded from the index, so re-drafting after a rejection is always allowed
(§6.2); an approved or pending/edited draft occupies the slot, so a second
concurrent draft request for the same target raises `sqlite3.IntegrityError` at
the SQL level rather than creating a duplicate active draft — `add_draft` (§5)
catches that and re-raises it as the typed `ActiveDraftExists` (finding 12,
§0.2) before it ever reaches a route. This is the authoritative guard under a
double-submit race; the §6 memory check is the friendly UX layer on top of it,
not the guarantee.

`cost_tokens` is created now (the column is part of SPEC's schema) but left
`NULL` this slice — `llm.py` does not yet record token cost; that is Slice 6's
explicit job. Recording it now would be a fabricated number.

### 3.1 Two distinct state machines, explicitly enforced

Draft status and target stage are **separate** machines and must not be
conflated. Both are enforced by explicit transition maps (module constants in
`db.py`), shared identically by the DB guard, the routes, and the tests, so
"what is tested is what runs" (the Slice 2 audit-map discipline):

**Draft status** (`draft.status`):

```python
DRAFT_STATUSES = ("pending", "edited", "approved", "rejected")

DRAFT_TRANSITIONS = {
    "pending":  {"edited", "approved", "rejected"},
    "edited":   {"edited", "approved", "rejected"},
    "approved": set(),   # terminal for that draft
    "rejected": set(),   # terminal for that draft
}
```

- A rejected target may receive a **new** draft (a new row); the rejected draft
  row itself never changes again.
- Editing an already-approved or already-rejected draft, or re-approving /
  re-rejecting, is a controlled failure (409) that writes **no** audit row and
  makes no change.

**Target stage** (the existing `target.stage`):

```python
STAGES = ("queued", "contacted", "replied", "live", "declined")
STAGE_SET = set(STAGES)

STAGE_TRANSITIONS = {
    "queued":    {"contacted", "declined"},
    "contacted": {"replied", "declined"},
    "replied":   {"live", "declined"},
    "live":      set(),    # terminal this slice
    "declined":  set(),    # terminal this slice
}
```

- An invalid jump such as `queued → live` fails as a controlled 409 **even
  though `live` is a valid enum value** — enum membership is necessary but not
  sufficient; the transition map is the real authority.
- A same-stage request (e.g. `contacted → contacted`) is an idempotent no-op:
  no change, **no** `target.stage_changed` audit row (a same-stage "change"
  would be a misleading audit entry — §12 decision 3).
- **The stage machine does not apply at all until a draft is approved for that
  target** (finding 8, §0.2). `set_target_stage` requires a workspace-scoped
  **approved** draft to exist for `(workspace_id, target_id)` before evaluating
  `STAGE_TRANSITIONS` at all — otherwise it raises `NotFound`, identically to a
  missing or cross-workspace target. This closes a gap the v2 plan left open:
  `list_pipeline_targets` only *displaying* targets with an approved draft is
  not the same as the database *refusing* to move an unapproved target's stage
  by a direct POST. Treating "not yet admitted" the same as "not found" (rather
  than inventing a distinct status code) avoids leaking, via the response
  itself, whether a target exists but is simply unapproved.

The gate between the two machines: **approving a draft admits its target to the
pipeline board, and only an admitted target's stage can ever change** (§7.2).
Before any approved draft, a target is a scored candidate on the campaign page,
is *not* on the board, and its `stage` column cannot be moved by any route.
This is the plan's central interpretive decision (§12, decision 1).

Controlled-response contract (shared by every §6 route, §5 DB function, and
§11 test):

| Condition | Response |
|---|---|
| Target/draft id from another workspace, or missing | resolves to not-found → redirect to the list page (never a leak, never a 500) |
| Stage-change attempt on a target with no approved draft | resolves to not-found (same as above — the target isn't yet a pipeline entity) → redirect to `/pipeline` |
| Malformed enum input (`stage`, `action`) | FastAPI `Literal` typing → **422** |
| Blank or over-long human-submitted draft body | **422**, no mutation, no audit (finding 10) |
| Valid enum value but illegal current-state transition | **409** (controlled conflict), no mutation, no audit |
| Double-submit race creating a second active draft (the `one_active_draft_per_target` index) | `ActiveDraftExists` → redirect to `/approvals` (the winning draft is already there), no error page (finding 12) |
| Any other `sqlite3.IntegrityError` on draft creation | propagates unmapped (a real bug, not a race) — never silently treated as a duplicate (finding 12) |

---

## 4. Drafting module (`app/agent/drafting.py`)

Mirrors `intake.py`/`scoring.py`'s status-carrying shape.

```python
class DraftStatus(str, Enum):
    LLM_OK = "llm_ok"                    # drafted by the model AND passed the §4.4 grounding gate
    NO_GEMINI_KEY = "no_gemini_key"      # no key anywhere -> heuristic template
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"
    HEURISTIC_FALLBACK = "heuristic_fallback"  # model replied schema-valid but failed the §4.4 grounding gate

@dataclass
class DraftResult:
    body: str
    model_used: str          # GEMINI_MODEL on LLM_OK, "heuristic" otherwise
    status: DraftStatus
    reason: str | None       # sanitized, safe for audit; see below for when it's set

def draft_outreach(brief: Brief, target: dict, settings: dict[str, str],
                   *, known_invalid_key_reason: str | None = None) -> DraftResult: ...
```

`reason` is set (not just `None`-on-success) whenever the audit needs more than
the bare status to explain what happened (finding 11, §0.2): the existing
credential/provider-error cases (`exc.message`), and now also
`HEURISTIC_FALLBACK`, where `reason` is set to a short, fixed, non-sensitive
string (e.g. `"model draft did not pass the grounding check"`) so the
`draft.created` audit row (§5, §8) can distinguish "the model never ran" from
"the model ran and its draft was rejected" — both currently collapse to
`model_used == "heuristic"` alone, which finding 4/11 flagged as insufficient.
`LLM_OK` still has `reason = None` (nothing to explain).

- `known_invalid_key_reason` reuses the Slice-3-hardening discipline: if a
  caller already knows this Gemini key is rejected, skip the live call. (It
  won't fire in this slice's route — drafting is the only model call on that
  path — but the parameter keeps the shape uniform and future-proofs a combined
  flow.)
- `target` is the persisted target row as a dict, carrying `name`,
  `handle_or_domain`, `reach`, `raw_json`, and **`fit_reasons_json`** (the
  Slice 3 grounded citations). The draft references what scoring already
  verified, closing the loop between the two slices.
- The evidence pair the draft cites (`evidence_key`/`evidence_value`) is
  **validation metadata**, used only to gate the body at runtime. It is **not**
  persisted as a new `draft` column — the draft table stays exactly SPEC's shape
  (§3) — unless a later slice gives a concrete reason to store it.

### 4.1 Structured schema (`app/models.py`)

The 20–1500 character bound used below is a **module-level function in
`app/models.py`** (not in `drafting.py` — finding 13, §0.3), so it has exactly
one definition with no import cycle:

```python
def validate_draft_body(text: str) -> str:
    """Shared bound for both a model-authored and a human-submitted draft
    body. Raises ValueError on failure; callers translate that into the
    error shape appropriate to their layer (a Pydantic ValidationError here,
    db.InvalidDraftBody in app/db.py)."""
    stripped = (text or "").strip()
    if len(stripped) < 20:
        raise ValueError("draft body is too short to be a real message")
    if len(stripped) > 1500:
        raise ValueError("draft body is too long for an outreach message")
    return stripped


class OutreachDraft(BaseModel):
    body: str
    evidence_key: str
    evidence_value: str

    @field_validator("evidence_key", "evidence_value")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("evidence_key and evidence_value are required")
        return v

    @field_validator("body")
    @classmethod
    def body_is_reasonable(cls, v: str) -> str:
        return validate_draft_body(v)
```

The model must return the message **and** the one evidence pair it chose to
ground it. Schema shape (non-blank fields, length bounds) is enforced here and
driven by `generate_structured`'s existing two-shot retry (non-negotiable #5).
**Truth** — that the pair is real and the body uses it — is a separate runtime
check (§4.4), exactly as Slice 3 separates `FitReason`'s schema from
`_is_grounded`'s runtime check.

`app/db.py`'s `save_draft_body` and `approve_draft` import `validate_draft_body`
directly from `app.models` — exactly where `db.py` already imports `Candidate`
from today (finding 10, §0.2; finding 13, §0.3) — and call it on a
human-submitted body before any mutation. A **human**-submitted body is held
to the same bound as a model-authored one: a blank or whitespace-only approval
would defeat "a human approves every send" just as surely as a blank model
draft would, and one shared function means the two paths cannot drift to
different bounds by accident. `drafting.py` never imports
`validate_draft_body` at all — every `OutreachDraft` it constructs, whether
from the LLM or the §4.3 heuristic, already runs the bound via the schema at
construction time, so there is nothing left for `drafting.py` to call
directly. This placement (in `app/models.py`, not `app/agent/drafting.py`)
is what avoids the `models → drafting → models` cycle v2.1 would have
introduced: `models.py` now has zero dependency on `app.agent.*` for this
function, and `db.py`'s existing, unidirectional `db → models` import
(already used for `Candidate`) covers the human-body path with no new edge
in the import graph.

### 4.2 The drafting prompt (authored from `beautiful-prose` + `humanizer` + The Mom Test)

`SYSTEM_PROMPT`, baked into `drafting.py`. The rules below are distilled from the
two skills SPEC.md names, plus Mom-Test directness. The prompt now also asks the
model to **return the evidence pair it used**, so the §4.4 gate can verify it:

```
You write one short outreach message from a business to a prospective partner
it wants to work with. A person will read every message before anything is
sent, and will reject anything that reads like a form letter.

You are given a few verified facts about this company, each as a key and an
exact value. Choose exactly one of those facts and build the message around it.
Reference that value in the message using the exact words given. Never invent a
fact, and never use a fact that was not given to you.

Address the company by name at least once, using the name given.

Make exactly one clear, small ask: a short reply, a quick call, a sample. Not a
meeting invite with five options. Not "let me know if you're interested."

Voice:
- Plain declarative sentences. Vary their length. A short one can land hard.
- Concrete nouns, strong verbs. Name the thing.
- No em dashes. Use periods and commas.
- No "not just X, it's Y" reversals.
- No opener flattery ("I love what you're doing", "huge fan"), no corporate
  filler ("reaching out", "excited to connect", "explore synergies", "at its
  core", "in today's landscape"), no emojis, straight quotes only.
- 60 to 110 words. A greeting, one or two sentences of specific relevance, one
  ask, a sign-off line the sender will fill in.

Return the message body, and the single evidence key and value you built it on.
```

The prompt is the same for both target types; §4.3's heuristic differs only in
which evidence field it leads with. Creator-specific tuning (handles, platform)
arrives with the creator sources in Slice 5.

### 4.3 Deterministic heuristic (demo-mode / no-key path) — neutral and truthful

`_heuristic_draft(brief, target) -> OutreachDraft` builds a usable,
evidence-referencing message with zero keys, so demo mode completes. It reads
the target's **stored grounded fit reasons** (Slice 3's `fit_reasons_json`),
picks the first one, and states its evidence value **neutrally** — it never
claims the fact proves a good fit, because a stored reason may in fact describe a
*poor* fit (e.g. `"Industry doesn't match the brief's niche"`, evidence
`industry = "Software"`; or `"Not located in a targeted country (Canada)"`).

Neutral, evidence-backed lead sentence, keyed by the chosen reason's
`evidence_key` (correction 4):

| evidence_key | neutral lead (every value comes verbatim from the stored reason) |
|---|---|
| `industry` | `I noticed {name} works in {evidence_value}.` |
| `employees` | `I saw that {name} has about {evidence_value} people.` |
| `country` | `I saw that {name} is based in {evidence_value}.` |
| `domain` / `name` (identity-only) | a neutral line naming the company that does **not** assert fit |

The full template:

```
Hi {greeting_name},

{neutral_lead_sentence}

We make {brief.product}. Would you be open to a short reply to see if it's
worth a quick call?

Best,
[Your name]
```

- `{brief.product}` is the sender's offer, taken verbatim from the parsed Brief
  — a fact about the sender, not an invented claim about the recipient.
- Every interpolated recipient fact is the stored reason's exact
  `evidence_value`. No phrase asserts the recipient is an ideal partner, the
  right size, a targeted market, or anywhere the sender is "expanding."
- `{greeting_name}` / `{name}` is the recipient identity per §4.4 (the target's
  real name, or a handle/domain when the name is the `DEFAULT_NAME` sentinel, or
  a generic `"there"` when neither is meaningful).
- The returned `OutreachDraft` carries the chosen reason's
  `evidence_key`/`evidence_value`, so the §4.4 gate passes it by construction
  (the body literally contains the value, and the identity is named).

Post-Slice-3 every target has at least one stored grounded reason
(`assert_grounded` guarantees it before persistence), so the heuristic always
has a real fact to cite. The heuristic is a demo-mode stand-in for real copy,
stated plainly — the LLM path is the real writer when a key is present.

### 4.4 Grounding gate (the prose analog of Slice 3 grounding)

The old v1 "name-only" gate is **removed**. A model draft is trusted only if it
passes a runtime grounding check against the target's **stored, already-verified**
fit reasons (correction 3). `_is_draft_grounded(draft: OutreachDraft, target:
dict) -> bool` returns `True` iff **all** of:

1. **The cited pair is real for this target.** `(draft.evidence_key,
   draft.evidence_value)` matches one of the target's stored
   `fit_reasons_json` entries' `(evidence_key, evidence_value)` under a
   normalized comparison (`strip().lower()`, the same `_norm` shape Slice 3
   uses). This transitively inherits Slice 3's guarantee that the pair grounds
   against real evidence — the draft can only cite a fact scoring already
   verified. A **fabricated** pair, or one belonging to **another** target,
   matches nothing here and fails.
2. **The cited value is non-blank** (defense in depth; the stored reasons are
   already non-blank).
3. **The body references that value.** Documented normalized comparison:
   lowercase both body and `evidence_value`, collapse internal whitespace to
   single spaces, strip, then require the normalized value to be a substring of
   the normalized body. (Known limitation: a short numeric value like `"12"`
   could substring-match incidentally; this gate is deliberately lighter than
   Slice 3's exact citation match because prose is paraphrasable, but it is
   still grounded in a **verified** stored value, not free text — §12
   decision 4.)
4. **The recipient identity is named when one meaningfully exists.** Let
   `identity` be `target["name"]` unless it equals `DEFAULT_NAME`
   (`"Unknown company"`), in which case `identity = target["handle_or_domain"]`
   if present. If a meaningful `identity` exists, require it (normalized
   substring) in the body. If **no** meaningful identity exists (name is the
   sentinel and no handle/domain), the identity check is skipped **but 1–3 still
   apply** — an anonymous-recipient draft is kept only when it is grounded in a
   verified evidence value, never merely because the name check was skipped.

Flow:

- **Schema-invalid** model output → the existing `generate_structured` two-shot
  retry (already in place). If still invalid → heuristic fallback.
- **Schema-valid but ungrounded** (`_is_draft_grounded` is `False`) → drafting
  returns the **heuristic** body (grounded by construction, §4.3) with
  `status = HEURISTIC_FALLBACK`, `model_used = "heuristic"`. `generate_structured`'s
  retry does **not** cover this — semantic grounding is checked here, after
  schema validation, and falls back deterministically.
- **Schema-valid and grounded** → keep the model body, `status = LLM_OK`,
  `model_used = GEMINI_MODEL`.

---

## 5. DB functions (`app/db.py`)

All `workspace_id`-scoped, same tenant-isolation discipline as every existing
function (forgetting the scope is a `TypeError`, never a silent leak). Every
join qualifies **both** `draft.workspace_id` and `target.workspace_id`
(correction 6). Each mutating function writes its audit row in the **same
transaction** as the mutation (correction 7, §8) via a shared internal
`_insert_audit(conn, …)` helper that writes on the open connection without
committing; the function commits once at the end, so a mutation and its audit
row are all-or-nothing.

### 5.1 Concurrency: conditional `UPDATE` + `rowcount`, not read-then-decide (finding 14, §0.3)

"Same transaction" (above) makes a mutation atomic with **its own audit row**.
It does not, by itself, stop two concurrent requests from each reading
`status = 'pending'`, each independently deciding the transition is legal, and
each writing — which would produce two `draft.approved` audit rows for one
draft, violating the terminal-state and exactly-once requirements finding 14
flagged. `save_draft_body`, `approve_draft`, `reject_draft`, and
`set_target_stage` do **not** read the current status/stage in Python and then
issue a separate `UPDATE`. Each instead issues **one conditional `UPDATE`**
whose `WHERE` clause encodes every source state the transition map allows,
and inspects `cursor.rowcount`:

```python
# approve_draft's core statement (illustrative — save_draft_body and
# reject_draft follow the same shape with a fixed target status and no
# edited_body logic; set_target_stage's shape is below).
cur = conn.execute(
    """
    UPDATE draft
    SET status = 'approved',
        edited_body = CASE WHEN ? = body THEN edited_body ELSE ? END
    WHERE workspace_id = ? AND id = ? AND status IN ('pending', 'edited')
    """,
    (submitted_body, submitted_body, workspace_id, draft_id),
)
if cur.rowcount == 1:
    # This request's UPDATE is the one that got the write lock while the
    # row still matched the WHERE clause -- the transition really was legal
    # at the moment it took effect, not just at some earlier read. Safe to
    # write the audit row in this same transaction and commit.
    ...
else:
    # rowcount == 0: some further read (see below) distinguishes NotFound
    # from InvalidTransition for the response -- but the mutation itself
    # already, atomically, did not happen.
    ...
```

The `edited_body` `CASE` compares `submitted_body` against the draft's own
**immutable** `body` column (set once at creation, never written by
`save_draft_body`/`approve_draft`/`reject_draft`) rather than against a prior
read of `edited_body` — reading an immutable column carries no race, so this
folds "did the human change the text" into the same atomic statement instead
of needing a preliminary `SELECT`. (This is a minor, deliberate refinement of
correction 2's "flags inline edits" wording: the flag now means "differs from
the originally drafted body," which is race-free and — since it also survives
a prior Save intact — a clearer signal than "differs from whatever a possibly
different prior request last saved.")

`save_draft_body` and `reject_draft` follow the identical shape with a fixed
target `status` and no `CASE`. `set_target_stage` folds the §0.2/finding-8
approved-draft gate into the **same** atomic statement via a correlated
`EXISTS`, so there is no preliminary read in the success path at all:

```python
allowed_current = [s for s, nxt in STAGE_TRANSITIONS.items() if new_stage in nxt]
cur = conn.execute(
    f"""
    UPDATE target
    SET stage = ?
    WHERE workspace_id = ? AND id = ?
      AND stage IN ({",".join("?" * len(allowed_current))})
      AND EXISTS (
        SELECT 1 FROM draft
        WHERE draft.workspace_id = target.workspace_id
          AND draft.target_id = target.id
          AND draft.status = 'approved'
      )
    """,
    (new_stage, workspace_id, target_id, *allowed_current),
)
```

On `rowcount == 0` for any of the four functions, the mutation is already,
atomically, known not to have happened — a **diagnostic** follow-up `SELECT`
(safe to run after the fact, since it cannot retroactively change what already
didn't happen) distinguishes the controlled response: row absent/wrong
workspace → `NotFound`; row present but current state not in the transition's
allowed set → `InvalidTransition` (409) for a draft action, or (for a stage
change) `NotFound` if there's no approved draft yet (§3.1) or, if the current
stage already equals `new_stage`, the same-stage no-op (`False`, no audit,
correction 1).

**Why a conditional `UPDATE` instead of `BEGIN IMMEDIATE`:** each of these
four functions performs exactly one mutating statement (plus, only on success,
one audit `INSERT`) as its sole write. Python's `sqlite3` module's default
`isolation_level` (unchanged from the existing `get_connection()`, which sets
none) begins an implicit transaction lazily, at the first `INSERT`/`UPDATE`/
`DELETE` — which is exactly this conditional `UPDATE` — and that statement
itself re-checks the authoritative row state at the instant it acquires
SQLite's write lock, not at some earlier Python-side read. Two concurrent
connections' `UPDATE`s on the same row cannot both proceed at once: SQLite
serializes writers, so the second either sees the row already changed by the
first (and its `WHERE` clause correctly fails to match, `rowcount == 0`) or
runs first itself — either way, exactly one succeeds. This holds without an
explicit `BEGIN IMMEDIATE`, and is simpler to reason about than one, because
the single statement's `WHERE` clause **is** the concurrency guard — there is
no separate "read" step whose result could go stale. The subsequent audit
`INSERT` (same connection, same still-open transaction) cannot be interleaved
with another writer either, since the write lock taken by the `UPDATE` is held
until `commit()`. Python's `sqlite3` default connection `timeout` (5 seconds,
unchanged) is far more than these single-statement transactions ever need to
wait for each other; a request that still can't acquire the lock inside that
window raises `sqlite3.OperationalError: database is locked`, which is not
specially handled — an honest limitation of a single-file local SQLite app
(§12, §13), not something this slice engineers around.

Four small typed exceptions signal controlled failures to the routes (kept in
`db.py`, imported by `main.py` and the tests):

```python
class NotFound(Exception): ...            # id absent, in another workspace, or (for a stage
                                           # change) not yet admitted to the pipeline -> route redirects
class InvalidTransition(Exception): ...    # illegal state change -> route returns 409
class InvalidDraftBody(Exception): ...     # blank/over-long human-submitted body -> route returns 422
class ActiveDraftExists(Exception): ...    # the one_active_draft_per_target race -> route redirects
```

`ActiveDraftExists` (finding 12, §0.2) is deliberately narrow: `add_draft`
catches `sqlite3.IntegrityError` and re-raises it as `ActiveDraftExists` only
when the error's message identifies the `one_active_draft_per_target` index (or
equivalently, both `draft.workspace_id` and `draft.target_id` as the offending
columns — SQLite names the columns or the index in a `UNIQUE constraint failed`
message, and this is the only unique constraint on `draft`). Any other
`IntegrityError` (e.g. a future foreign-key violation) is **not** caught here
and propagates as a genuine 500 — silently mapping every integrity failure to
"someone double-submitted" would hide a real bug behind a harmless-looking
redirect.

Functions:

```python
def get_target(workspace_id, target_id) -> Row | None
    # SELECT * FROM target WHERE workspace_id = ? AND id = ?. Scoped like every
    # other tenant read. The draft-creation route (§6) uses this, then
    # db.get_campaign(workspace_id, target["campaign_id"]) (already exists,
    # Slice 2), to load the Brief the drafting module needs
    # (Brief.model_validate_json(campaign["brief_json"])) (finding 9, §0.2).

def add_draft(workspace_id, target_id, body, model_used, status, reason=None,
              actor="agent") -> int
    # INSERT ... SELECT tenancy guard: inserts only if the target row exists in
    # THIS workspace. rowcount == 0 -> raise NotFound (no leak, no orphan draft).
    # status/reason come straight from DraftResult (finding 11, §0.2): the
    # draft.created audit detail is built as status.value alone, or
    # "{status.value}: {reason}" when reason is set -- so the atomic audit row
    # always records WHY this body was produced (llm_ok / no_gemini_key /
    # invalid_gemini_key / gemini_error / heuristic_fallback), not just that a
    # draft now exists. sqlite3.IntegrityError from the partial unique index ->
    # re-raised as ActiveDraftExists (finding 12). Writes draft.created audit +
    # the new draft in one transaction. Returns the new draft id.

def get_draft(workspace_id, draft_id) -> Row | None                       # scoped

def get_active_draft_for_target(workspace_id, target_id) -> Row | None     # latest non-rejected draft, or None (memory/UX check)

def has_approved_draft(workspace_id, target_id) -> bool
    # EXISTS (SELECT 1 FROM draft WHERE workspace_id=? AND target_id=? AND
    # status='approved'). Public and independently testable (finding 8, §0.2);
    # set_target_stage performs the equivalent check inside its own
    # transaction rather than calling this and reopening a connection, but the
    # two must and do agree -- covered by a retained test that calls both.

def list_pending_drafts(workspace_id) -> list[Row]
    # status IN ('pending','edited'); joins target (both workspace_ids qualified)
    # for name/fit/campaign context. This is the Approvals queue and the nav count.

def save_draft_body(workspace_id, draft_id, edited_body, actor="human") -> None
    # validate_draft_body(edited_body) first (finding 10, §0.2) -> raises
    # InvalidDraftBody on blank/over-long, before touching the DB. Then the
    # conditional UPDATE ... WHERE status IN ('pending','edited') (§5.1,
    # finding 14) -> rowcount==1: sets edited_body, status='edited', writes
    # draft.edited audit, one txn. rowcount==0: a diagnostic read distinguishes
    # NotFound (missing/cross-workspace) from InvalidTransition (already
    # approved/rejected).

def approve_draft(workspace_id, draft_id, submitted_body, actor="human") -> None
    # validate_draft_body(submitted_body) first (finding 10) -> InvalidDraftBody
    # on blank/over-long, before touching the DB -- a crafted blank-body POST
    # cannot approve empty text. Then the conditional UPDATE ... WHERE status IN
    # ('pending','edited') (§5.1, finding 14): sets status='approved' and, via a
    # CASE comparing submitted_body against the row's own immutable body column,
    # sets edited_body = submitted_body only when it differs from the original
    # draft (correction 2 — no lost edits, computed race-free in the same
    # statement). rowcount==1 -> write ONE draft.approved audit (detail flags
    # inline edits when the body differed from the original) in the same
    # transaction. rowcount==0 -> diagnostic read for NotFound vs
    # InvalidTransition, same as save_draft_body.

def reject_draft(workspace_id, draft_id, actor="human") -> None
    # Conditional UPDATE ... WHERE status IN ('pending','edited') sets
    # status='rejected' (§5.1, finding 14). rowcount==1 -> draft.rejected audit,
    # one txn. rowcount==0 -> diagnostic NotFound/InvalidTransition, as above.
    # (Reject discards whatever text was in the textarea -- there is nothing to
    # validate or save.)

def list_pipeline_targets(workspace_id) -> list[Row]
    # Targets with an approved draft. GROUP BY target.id so each target appears
    # AT MOST ONCE; the approved draft text is chosen deterministically
    # (MAX(draft.id) among that target's approved drafts), returning
    # COALESCE(edited_body, body). Carries stage, name, fit_score, campaign_id.
    # Both workspace_ids qualified.

def set_target_stage(workspace_id, target_id, new_stage, actor="human") -> bool
    # Conditional UPDATE ... WHERE stage IN (allowed source stages for
    # new_stage) AND EXISTS (an approved draft for this target) (§5.1,
    # finding 14) -- folds the finding-8 approved-draft gate into the same
    # atomic statement, no preliminary read needed for the success path.
    # rowcount==1 -> target.stage_changed audit (detail "old -> new") in one
    # transaction; returns True. rowcount==0 -> a diagnostic read distinguishes:
    # target missing/cross-workspace/no-approved-draft -> NotFound (identical
    # response to a missing target; see §3.1's rationale for not distinguishing
    # the two); current stage already equals new_stage -> no-op, returns False,
    # NO audit (correction 1); anything else -> InvalidTransition (409).
```

- The audit row every function writes includes the correct `workspace_id`,
  `campaign_id`, `target_id`, and `draft_id`: the draft functions look up the
  target's `campaign_id` (and `target_id`) via the scoped join in the same
  transaction; the stage function reads `campaign_id` from the target row
  (an immutable field once set, so reading it — even after the conditional
  `UPDATE` above — carries no race).
- `STAGES`, `STAGE_SET`, `STAGE_TRANSITIONS`, `DRAFT_STATUSES`, and
  `DRAFT_TRANSITIONS` (§3.1) are module constants in `db.py` — one source of
  truth for the DB guard, the routes, and the tests.
- `validate_draft_body` (§4.1) is imported from `app.models` — one definition
  of the 20–1500 character bound, used by the Pydantic schema for model output
  and by `db.py` for human-submitted bodies alike (finding 10, §0.2; moved out
  of `app.agent.drafting` in finding 13, §0.3, to avoid a circular import).
- The existing `db.add_audit` (separate connection/commit) stays for the Slice
  2/3 intake/discovery/scoring rows; it is refactored to delegate to the shared
  `_insert_audit` helper so there is one audit-insert code path. Slice 4's new
  actions must be atomic with their mutation, so they never call the standalone
  `add_audit` — they audit inside their own transaction.

---

## 6. Routes (`app/main.py`)

Each route is `workspace`-scoped via the existing `get_current_workspace`
dependency. A `db.NotFound` from any function is caught and redirected (the
not-found contract — this now also covers a stage-change attempt on a target
with no approved draft, §3.1); a `db.InvalidTransition` is caught and returned
as `HTTPException(status_code=409)`; a `db.InvalidDraftBody` is caught and
returned as `HTTPException(status_code=422)` (finding 10); a
`db.ActiveDraftExists` on draft creation redirects to `/approvals` (finding 12,
§3.1 race row) — any other `sqlite3.IntegrityError` is **not** caught here and
propagates as a 500.

```
POST /targets/{target_id}/draft
    - Load the target: target = db.get_target(workspace, target_id); None ->
      redirect /campaigns (NotFound-shaped, finding 9). Load its campaign via
      the existing db.get_campaign(workspace, target["campaign_id"]) and parse
      Brief.model_validate_json(campaign["brief_json"]) — the same brief
      Slice 2/3 already persisted, now given to drafting for the first time.
    - MEMORY / UX check: if get_active_draft_for_target(...) is not None,
      redirect to /approvals (the existing active draft is already there) —
      do NOT create a second. This is the friendly layer; the partial unique
      index is the authoritative guard behind it.
    - Else draft_outreach(brief, target, settings) -> DraftResult; add_draft(
      workspace, target_id, result.body, result.model_used, result.status,
      result.reason) — the atomic draft.created audit now carries the drafting
      outcome (finding 11). ActiveDraftExists (lost the race, finding 12) ->
      redirect /approvals. NotFound -> redirect /campaigns. Success -> /approvals.

GET  /approvals
    - list_pending_drafts(workspace): each row an editable card (§7.1).

POST /drafts/{draft_id}/action
    - action: DraftAction = Form(...)   # Literal["save","approve","reject"] -> 422 on garbage
    - body: str = Form(...)             # the CURRENT textarea contents, always submitted
    - Dispatch (one form, three submit buttons — correction 2):
        save    -> save_draft_body(workspace, draft_id, body)
        approve -> approve_draft(workspace, draft_id, body)   # body captured if changed
        reject  -> reject_draft(workspace, draft_id)          # body ignored; reject is terminal
    - InvalidDraftBody -> 422 (finding 10, save/approve only — reject never
      validates body). InvalidTransition -> 409. NotFound -> redirect
      /approvals. Else -> /approvals.

GET  /pipeline
    - list_pipeline_targets(workspace) grouped into the five stage columns (§7.2).

POST /targets/{target_id}/stage
    - stage: PipelineStage = Form(...)  # Literal over STAGES -> 422 on garbage
    - set_target_stage(...). NotFound -> redirect /pipeline (covers both "no
      such target in this workspace" and "target has no approved draft yet",
      finding 8 — same response, so neither is distinguishable from the
      other). InvalidTransition -> 409. Same-stage -> no-op (returns False, no
      audit). Else -> /pipeline.
```

### 6.1 Shared nav context

`base.html` shows an **Approvals** count pill on every page, so the pending
count must be in every page's context. A small helper `nav_context(workspace) ->
dict` returns `{workspace, workspaces, approvals_count}`; each route spreads it
into its template context. This is a minor, mechanical refactor of the existing
`{workspace, workspaces}` context and future-proofs the Slice 6 nav counts.
`approvals_count = len(list_pending_drafts(workspace_id))`.

### 6.2 Campaign-detail lifecycle links (`GET /campaigns/{id}`, correction 5)

`campaign_detail` gains, per target row, one contextual call-to-action derived
from that target's draft state. The targets query gains a `LEFT JOIN` over
`draft` computing, per target: `has_any_draft`, the `active_draft_id` (latest
non-rejected), and the `latest_status`. A helper `_draft_cta(state) -> dict`
maps state to `{label, kind, href|form}` exactly:

| Target draft state | CTA |
|---|---|
| No draft has ever existed | **Draft outreach** — POST `/targets/{id}/draft` |
| Latest draft rejected, no active draft | **Draft again** — POST `/targets/{id}/draft` (rejected never blocks a new draft) |
| Active draft is `pending` or `edited` | Link to that draft in **Approvals** (`/approvals#draft-{id}`) |
| Draft `approved` | Link to the target on **Pipeline** (`/pipeline#target-{id}`) |

- Rejected drafts remain visible in the campaign **Activity** history (§7.3),
  but never appear in the pending Approvals queue and are never linked there.
- An approved draft links to Pipeline (which includes it), a pending/edited
  draft links to Approvals (which includes it) — never the reverse (correction
  5: "do not link … to a queue page that excludes it").

---

## 7. UI

### 7.1 Approvals page (`approvals.html`, new)

A single column of pending/edited draft cards (the queue). Each card is **one
form** POSTing to `/drafts/{id}/action` (correction 2):
- Header: target name, fit pill (reusing Slice 3's `.fit--*` classes), and a
  link to its campaign.
- An editable `<textarea class="textarea" name="body">` pre-filled with
  `edited_body or body`.
- Three real submit buttons in one row, distinguished by `name="action"`:
  **Save** (`value="save"`, secondary), **Approve** (`value="approve"`,
  primary), **Reject** (`value="reject"`, destructive). Because all three submit
  the same form, the current textarea text always reaches the server — Approve
  never requires the human to press Save first.
- Empty state (reusing `.empty`): "No drafts waiting for review."

### 7.2 Pipeline board (`pipeline.html`, new)

Five columns in stage order (queued, contacted, replied, live, declined), each
headed by a pipeline pill in its `--pl-*` token with a mono count. Cards under
each column show the target name, fit, campaign link, the approved (edited)
draft text preview, and **contextual stage buttons** — one small `<button>` per
allowed next move (read straight from `STAGE_TRANSITIONS`), each its own tiny
POST form to `/targets/{id}/stage`:

- queued → [Contacted] [Decline]
- contacted → [Replied] [Decline]
- replied → [Live] [Decline]
- live → (terminal this slice)
- declined → (terminal this slice)

Only transitions in `STAGE_TRANSITIONS` are ever rendered, so the UI cannot
offer an illegal jump; the server still enforces it (defense in depth). Real
`<button>` elements: keyboard and focus for free, consistent with the Slice 3
caret decision. **Drag-and-drop is explicitly out of scope** — "button or drag"
in SPEC is satisfied by buttons, and drag is extra JS with no accessibility gain
(§12, decision 3). Empty board reuses `.empty`. Each card carries an
`id="target-{id}"` anchor for the §6.2 Pipeline deep-link.

### 7.3 Campaign detail additions

- A **Draft / status** cell per target row rendering the §6.2 CTA.
- A compact **Activity** list at the bottom: the campaign's audit rows rendered
  human-readably (action label + detail + timestamp), so the audit trail the
  done-when requires is *visible*, not just written. This is where rejected
  drafts remain visible (correction 5). Rendering uses an explicit
  `ACTION_LABELS` map (§8) — no enum-string interpolation, same discipline as
  the banner maps.

### 7.4 Nav (`base.html`)

Two new side-rail items after Campaigns: **Approvals** (with a mono count pill;
per design.md the backlog count is the one that inverts to solid `accent` when
non-zero) and **Pipeline**. Active-state styling reuses the existing
`rail__item--active` rule keyed on the path.

### 7.5 CSS (`app.css`)

Token-only additions: `.pipeline` (a horizontal-scrolling flex of columns —
must scroll inside its own container, never the page body), `.pl-col`,
`.pl-col__head` + the five stage-pill classes reading `--pl-*`, `.pl-card`,
`.draft-card` / `.approvals` layout, `.draft-status` chips, and an `.activity`
list. No invented colors; the stage pills follow design.md's pill spec (9999px
radius, 11px/600, 6px `currentColor` dot).

---

## 8. Audit (`app/audit_banners.py` + atomic DB writes)

Draft and stage actions are **human/agent actions, not campaign banners** — they
are written straight to the `audit` table with explicit action strings and are
*not* added to the `campaign_detail` banner filter (which stays intake /
discovery / scoring). Every such write happens **inside the same transaction as
its mutation** (§5, correction 7): on success exactly one audit row is written;
on any failure of the mutation, neither the state change nor the audit row
remains. The action strings, defined as module constants so they are greppable
and typo-proof:

| action | actor | written by (atomically, with the mutation) |
|---|---|---|
| `draft.created` | agent | `add_draft` (detail = `DraftResult.status.value`, plus `: {reason}` when set — e.g. `heuristic_fallback: model draft did not pass the grounding check`, `invalid_gemini_key: <sanitized reason>` — finding 11, §0.2) |
| `draft.edited` | human | `save_draft_body` |
| `draft.approved` | human | `approve_draft` (detail flags inline edits when `submitted_body` differs from the draft's original `body`, computed race-free in the same statement — §5.1) |
| `draft.rejected` | human | `reject_draft` |
| `target.stage_changed` | human | `set_target_stage` (detail = "queued -> contacted"); **no row on a same-stage no-op** |

Each row carries the correct `workspace_id`, `campaign_id`, `target_id`, and
`draft_id` (the draft actions resolve `campaign_id`/`target_id` through the
scoped join; the stage action reads `campaign_id` from the target row).

For the §7.3 Activity list, an explicit `ACTION_LABELS: dict[str, str]` maps each
action (including the existing intake/discovery/scoring ones) to a human phrase
("Draft approved", "Stage changed", …). A helper `label_for(action)` returns the
phrase or a sensible default, so an unmapped action never crashes the page.

---

## 9. Demo mode, structured output, and the non-negotiables (how each is met)

- **#2 demo mode:** zero keys → `draft_outreach` uses the §4.3 heuristic (which
  is grounded by construction against the target's stored reasons); editing,
  approving, and the whole pipeline are pure DB/UI with no model call. The full
  slice demos start to finish with no keys.
- **#4 human approves every send + audit:** a draft is inert text until a human
  acts; approve/reject/edit/stage each write **exactly one** audit row **in the
  same transaction** as the change (§8), and this holds even under two
  concurrent requests for the same draft or target — the conditional-`UPDATE`
  design (§5.1, finding 14) means only one request's mutation can ever match,
  so exactly one audit row is written, never two, and the terminal states
  (approved/rejected/live/declined) stay genuinely terminal under a race, not
  just under sequential use. **Nothing is ever transmitted** — "approved" is a
  status, and marking "contacted" is the owner recording that *they* reached
  out (SPEC §7: real send integration is out of scope). A target's stage
  cannot move at all until a human has approved a draft for it — enforced by
  `set_target_stage` itself, not only by what the pipeline page displays
  (finding 8, §0.2) — and neither Save nor Approve can persist a blank or
  malformed human edit (finding 10, §0.2).
- **#5 structured output:** the LLM path returns a validated `OutreachDraft`
  (body + evidence pair) with the existing two-shot retry, then the §4.4
  grounding gate on top.
- **#6 isolation:** every draft/pipeline query and mutation is `workspace_id`
  scoped, and enforced at the **DB boundary** — `add_draft`'s `INSERT … SELECT`
  cannot insert against another workspace's target, and every join qualifies
  both `workspace_id`s (§5). §11 verifies a second workspace sees none of it and
  cannot mutate across the boundary.
- **memory:** the §6 UX check plus the §3 partial unique index together mean a
  target has at most one active draft; the board and queue read persisted rows,
  never re-generate; re-drafting is allowed only after a rejection.

---

## 10. Files changed / created (implementation phase, not this commit)

**New:**
- `app/agent/drafting.py` (schema-driven LLM path + neutral heuristic + §4.4
  grounding gate). Does **not** define or import `validate_draft_body`
  (finding 13, §0.3) — every `OutreachDraft` it builds is validated by the
  schema at construction time.
- `app/templates/approvals.html`, `app/templates/pipeline.html`.
- `tests/test_slice4_drafting.py` (retained — §11.1).

**Modified:**
- `app/models.py` — `OutreachDraft` (body + evidence_key + evidence_value);
  module-level `validate_draft_body` (finding 13, §0.3 — moved here from
  `drafting.py` to avoid a `models → drafting → models` cycle).
- `app/db.py` — `draft` table + partial unique index in `init()`; `get_target`
  (finding 9); the §5/§5.1 draft/pipeline functions (atomic mutation+audit,
  tenancy guard, conditional-`UPDATE` transition guards with `rowcount`
  checks — finding 14 — body validation via `app.models.validate_draft_body`,
  the approved-draft gate folded into `set_target_stage`'s own `UPDATE`);
  `has_approved_draft` (finding 8); `STAGES`/`STAGE_SET`/`STAGE_TRANSITIONS`/
  `DRAFT_STATUSES`/`DRAFT_TRANSITIONS` constants;
  `NotFound`/`InvalidTransition`/`InvalidDraftBody`/`ActiveDraftExists`
  (findings 8/10/12); the shared `_insert_audit` helper (`add_audit`
  refactored to delegate to it).
- `app/main.py` — the §6 routes (including the single `/drafts/{id}/action`
  dispatcher and its `DraftAction` literal, the target/brief loader for
  `POST /targets/{id}/draft`, and the `InvalidDraftBody`/`ActiveDraftExists`
  handlers); `nav_context` helper; the §6.2 `campaign_detail` draft-CTA join +
  `_draft_cta`; Activity list.
- `app/audit_banners.py` — the §8 action constants + `ACTION_LABELS`/`label_for`.
- `app/templates/base.html` — Approvals + Pipeline nav items with the count pill.
- `app/templates/campaign_detail.html` — Draft/status cell per target + Activity list.
- `app/static/css/app.css` — pipeline board, approval cards, stage pills, draft
  status chips, activity list (tokens only).
- `PROGRESS.md`, `DECISIONS.md`, `collaboration.md` at slice end.

`tokens.css` and the `target`/`audit` schemas need **no** changes (§2). **This
commit** touches only `SLICE_4_PLAN.md` and `collaboration.md`.

---

## 11. Verification (proportional to risk)

### 11.1 Retained tests (`tests/test_slice4_drafting.py`)

Mocked (no real provider call, no real key), temp SQLite, no `outpost.db`
writes. Covering every correction. Items 20–21 (finding 14, §0.3) are the
exception to "mocked": they need two *real*, separate `sqlite3` connections
against the same on-disk temp file (never `:memory:`, which is not shared
across connections) to actually exercise SQLite's writer serialization —
consistent with every other test here already using a real temp file rather
than an in-memory DB.

1. **Schema:** `OutreachDraft` rejects a blank/too-short/over-long body and a
   blank `evidence_key`/`evidence_value`; accepts a normal message with a pair.
2. **Allowed & forbidden draft transitions** (correction 1): `DRAFT_TRANSITIONS`
   permits pending/edited → edited/approved/rejected; `save_draft_body` /
   `approve_draft` / `reject_draft` raise `InvalidTransition` from approved or
   rejected; an illegal call writes **no** audit row and makes no change.
3. **Allowed & forbidden stage transitions** (correction 1): every legal step in
   `STAGE_TRANSITIONS` succeeds; `queued → live` and every other illegal jump
   raises `InvalidTransition` even though `live` is a valid enum; the route's
   typed `PipelineStage`/`DraftAction` return 422 on non-enum input; a same-stage
   request is a no-op with no `target.stage_changed` audit row.
4. **Approving unsaved textarea text** (correction 2, DB-level and route-level):
   `approve_draft(submitted_body=changed)` sets `edited_body` and approves in one
   call; a TestClient POST to `/drafts/{id}/action` with `action=approve` and a
   **changed** `body` (no prior Save) results in the changed text on
   `/pipeline`.
5. **Runtime evidence grounding for LLM drafts** (correction 3): valid cited
   key/value that the body uses → kept (`LLM_OK`); **fabricated** pair → fallback
   (`HEURISTIC_FALLBACK`); pair belonging to **another** target → fallback; body
   **omitting** its claimed value → fallback.
6. **Unknown-name / domain identity handling** (correction 3): a meaningful name
   must be referenced; when name is `DEFAULT_NAME` the domain is used; when
   neither exists the identity check is skipped **but** an ungrounded body still
   falls back (no free-pass for anonymous recipients).
7. **Negative evidence → neutral heuristic prose** (correction 4): a target
   whose only stored reason is a *poor-fit* fact (e.g. industry mismatch, or
   out-of-range size) produces a heuristic body that states the fact neutrally
   and never calls the target an ideal partner, the right size, or a targeted
   market; the body still contains the exact evidence value and names the
   company; `model_used == "heuristic"`.
8. **Credential paths:** `None` → heuristic/`NO_GEMINI_KEY`;
   `LLMError(INVALID_KEY)` → heuristic/`INVALID_GEMINI_KEY`, reason set;
   `LLMError(ERROR)` → heuristic/`GEMINI_ERROR`; `known_invalid_key_reason`
   skips the live call. Never raises.
9. **Re-draft after rejection** (corrections 5 & 6): `get_active_draft_for_target`
   ignores a rejected draft; a new `add_draft` after a rejection succeeds; the
   campaign-detail CTA for a rejected-with-no-active target is **Draft again**.
10. **One-active-draft concurrency / uniqueness** (correction 6, refined by
    finding 12): a second `add_draft` while an active (pending/edited/approved)
    draft exists raises `ActiveDraftExists` (not a bare `sqlite3.IntegrityError`
    — the partial unique index's failure is caught and re-raised specifically);
    the route maps `ActiveDraftExists` to an `/approvals` redirect. A separate
    test asserts that a *different*, unrelated `IntegrityError` (e.g. a foreign
    key violation from a bad `target_id`, simulated directly) is **not** caught
    as `ActiveDraftExists` and propagates.
11. **Pipeline target deduplication** (correction 6): `list_pipeline_targets`
    returns a target at most once and returns its approved `edited_body` when
    present; a target only appears after approval, never before.
12. **DB-boundary tenant isolation** (correction 6): `add_draft` for a target in
    another workspace raises `NotFound` (INSERT … SELECT inserts zero rows); a
    cross-workspace draft id cannot be read, edited, approved, rejected, or
    reached by stage change; a second workspace's Approvals/Pipeline/counts show
    none of the first's rows.
13. **Atomic mutation + audit** (correction 7): each successful mutation writes
    exactly one audit row with the correct workspace/campaign/target/draft ids; a
    simulated failure (e.g. an illegal transition, or a patched
    `_insert_audit`/commit raising) leaves **neither** the state change **nor**
    an audit row.
14. **Lifecycle CTA mapping** (correction 5): `_draft_cta` returns Draft outreach
    / Draft again / Approvals link / Pipeline link for the four states, and never
    links an approved or rejected draft to Approvals.
15. **Nothing sends** (SPEC §7): drafting, approving, and advancing a target make
    **zero** outbound calls — a test patches `httpx.post` (and asserts no other
    network client is used) and confirms the approve/stage/reject paths never
    invoke it; "contacted" is only a stored stage, not a transmission.
16. **Unapproved target cannot be advanced by direct POST** (finding 8, §0.2): a
    target with no draft, and separately a target with only a pending/edited/
    rejected draft, both raise `NotFound` from `set_target_stage` for every
    stage in `STAGE_TRANSITIONS["queued"]` — including a direct DB-level call
    bypassing the route, and a `TestClient` POST to `/targets/{id}/stage`
    proving no stage mutation and no `target.stage_changed` audit row result.
    `has_approved_draft` is asserted to agree with `set_target_stage`'s own
    internal check on the same fixtures.
17. **Scoped target/brief loader** (finding 9, §0.2): `get_target` returns
    `None` for a cross-workspace or nonexistent id; a `TestClient` POST to
    `/targets/{id}/draft` for a target in another workspace redirects without
    creating a draft; for a real target, the route-level test confirms the
    `Brief` passed to `draft_outreach` matches the campaign's persisted
    `brief_json`.
18. **Human-submitted body validation** (finding 10, §0.2): `save_draft_body`
    and `approve_draft` both raise `InvalidDraftBody` for a blank, whitespace-
    only, or over-1500-character body, with no mutation and no audit row in
    each case; a `TestClient` POST to `/drafts/{id}/action` with an empty
    `body` and `action=approve` returns 422 and the draft's stored status is
    unchanged. `reject_draft` is confirmed to ignore `body` entirely (no
    validation, since nothing is being saved).
19. **`draft.created` audit explains the outcome** (finding 11, §0.2): for each
    of `LLM_OK`, `NO_GEMINI_KEY`, `INVALID_GEMINI_KEY`, `GEMINI_ERROR`, and
    `HEURISTIC_FALLBACK`, `add_draft`'s resulting audit row's `detail` contains
    the status value (and the sanitized reason when one is set); a route-level
    test confirms a model draft that fails the §4.4 grounding gate produces a
    `draft.created` row distinguishable from a genuine `NO_GEMINI_KEY` run, even
    though both end up with `model_used == "heuristic"`.
20. **Concurrent double-approve produces exactly one approval** (finding 14,
    §0.3): a `pending` draft is set up in the shared temp SQLite file; two
    threads, each opening its own `sqlite3` connection via `db.get_connection()`
    (exactly as two real requests would), call `db.approve_draft(...)` with
    slightly different `submitted_body` values, released as close to
    simultaneously as a thread `Barrier` allows. Asserts: exactly one call
    returns normally and the other raises `InvalidTransition`; the draft's
    final `status` is `approved` exactly once (never toggled or corrupted);
    exactly **one** `draft.approved` audit row exists, and its `detail`/final
    `edited_body` correspond to whichever call actually won — never a mix of
    both, and never two rows. The same shape is repeated for two concurrent
    `reject_draft` calls, and for one concurrent `approve_draft` +
    `reject_draft` pair on the same `pending` draft (exactly one of the two
    terminal states wins, the other gets `InvalidTransition`).
21. **Concurrent stage submission cannot bypass the transition machine**
    (finding 14, §0.3), two sub-cases, both via two separate connections on a
    target with an approved draft, currently `queued`: (a) two threads
    simultaneously call `db.set_target_stage(..., "contacted")` with the
    *same* requested stage — exactly one returns `True`, the other is a
    same-stage no-op (`False`, since by the time its `UPDATE` runs the stage
    already reads `contacted`), and never two `target.stage_changed` audit
    rows. (b) two threads simultaneously request *different* stages that are
    each individually legal from `queued` (`"contacted"` and `"declined"` —
    both are in `STAGE_TRANSITIONS["queued"]`, so this genuinely exercises the
    race rather than the already-illegal jump item 3 covers) — exactly one
    succeeds (`True`) and lands the target on whichever stage won; the other
    raises `InvalidTransition` (not a no-op — its requested stage differs from
    the one that actually landed), because by the time its `UPDATE` runs the
    target is no longer `queued`. Either way, the target ends on exactly one
    of the two requested stages, never both, and never a third.

### 11.2 Manual / live verification

- **No-key path:** in a scratch zero-key workspace, draft a target (heuristic),
  see it in Approvals, **type a change into the textarea and click Approve
  without pressing Save first**, and confirm the Pipeline card in Queued shows
  the **edited** text (correction 2); advance it through Contacted/Replied/Live
  and Decline another; attempt an illegal jump by crafting a direct POST and
  confirm a 409 with no stage change and no audit row; confirm the audit trail
  (direct `outpost.db` query) shows **exactly one** row per action and the
  Activity list matches; the Approvals nav count reflects the queue. Computed-
  style check that the five stage pills resolve to their `--pl-*` tokens in both
  themes.
- **Live Gemini (required — a mock can't prove the prompt yields a human,
  grounded draft):** one drafted target against a freshly rotated Gemini key
  pasted through Settings only (located by length/timestamp, never read),
  confirming `model_used == GEMINI_MODEL`, a body that reads human, names the
  company, and references a real stored evidence value (the §4.4 gate passed
  live), and — per the Slice 2/3 rule — no credential anywhere in console, audit
  `detail`, `git diff`, `git log`, or tracked files.
- At most two screenshots for the whole slice, after every check passes. No
  `outpost.db` rows deleted or reset; verification adds normal product data only.

---

## 12. Decisions this plan makes (for owner review)

1. **Board membership = an approved draft.** A target joins the pipeline board
   when one of its drafts is approved; before that it is a scored candidate on
   the campaign page only. (Alternative: every discovered target on the board
   from discovery. Rejected — it makes "approve" meaningless and clutters the
   board with un-pursued candidates.)
2. **Approvals and Pipeline are workspace-level pages** (side-nav items with a
   count), not per-campaign tabs — matching the "command center" framing and the
   design.md side-nav pattern. (A per-campaign board is the alternative.)
3. **Stage changes are accessible buttons, not drag; a same-stage request is an
   idempotent no-op with no audit row.** SPEC's "button or drag" is satisfied by
   buttons; a same-stage "change" writes nothing because a stage-change audit for
   a stage that didn't change would be misleading (correction 1).
4. **Prose grounding is a runtime gate against stored Slice 3 evidence**
   (correction 3), using a documented normalized-substring comparison for the
   body. It is lighter than Slice 3's exact citation match because prose is
   paraphrasable, but every kept draft still cites a **verified** stored value
   and names the recipient when one exists; ungrounded drafts fall back to the
   always-grounded heuristic. (Known limitation: a short numeric value could
   substring-match incidentally — accepted for a demo gate.)
5. **`cost_tokens` is created but left NULL**, populated in Slice 6 when `llm.py`
   records token cost. Writing a number now would be fabricated.
6. **Drafts are generated on demand, per selected target** (SPEC: "per target
   selected for outreach"), not auto-at-discovery — honoring the memory rule and
   keeping the human in control of what gets drafted.
7. **Approving inline-edited text writes a single `draft.approved` audit row**
   (its detail flags that the body was edited at approval), not a separate
   `draft.edited` **plus** `draft.approved`. The human performed one action
   (Approve); the edit is captured in `edited_body` and visible in Activity. This
   keeps "exactly one audit row per action" (correction 7) true. (Alternative:
   two rows. Flagged for owner preference.)
8. **Slice 4 state-changing DB functions write their audit row inside the same
   transaction as the mutation**, unlike Slice 2/3 where the route calls
   `db.add_audit` separately afterward. Correction 7 requires the mutation and
   its audit to be all-or-nothing, which a separate connection/commit cannot
   guarantee. (This is also logged in §13 for DECISIONS.md.)
9. **The approval card is one form with three action buttons**
   (`/drafts/{id}/action`, `action` ∈ save/approve/reject), correction 2's stated
   preference, rather than three separate endpoints — so the current textarea
   body always reaches the server with whichever action is taken.
10. **A stage-change attempt on a target with no approved draft resolves to the
    same `NotFound` response as a missing/cross-workspace target** (finding 8),
    rather than a distinguishable status. Alternative: a dedicated
    `NotAdmitted` exception mapped to its own code (e.g. 403 or a different
    404 variant). Rejected for this slice — the two cases share the same
    correct user action (there's nothing to advance), and not distinguishing
    them avoids the response itself confirming whether a given id exists in
    this workspace at all.
11. **Human-submitted draft bodies (Save and Approve) are held to the same
    20–1500 character bound as the model's own output** (finding 10), via one
    shared `validate_draft_body`. Alternative: a looser or absent bound for
    humans, on the theory that a person editing text should be trusted more
    than a model. Rejected — "a human approves every send" (non-negotiable #4)
    is not satisfied by a blank approval, and reusing the model's already-
    reasoned bound is simpler than inventing a second one.
12. **The grounding-gate fallback (`HEURISTIC_FALLBACK`) sets a fixed,
    non-sensitive `reason` string** (finding 11) rather than including any
    detail about *what* the model returned (its actual body is never a safe
    thing to echo into an audit `detail` — it's arbitrary text). The audit
    explains *that* the model's draft was rejected and *why the category is*
    "grounding," not exactly what the model wrote.
13. **`add_draft` identifies the `one_active_draft_per_target` race by matching
    the `sqlite3.IntegrityError` message text** (finding 12), since SQLite
    does not raise a distinctly-typed exception per constraint. This is
    slightly brittle to a SQLite message-format change across versions, but is
    the only mechanism SQLite's Python driver offers short of a second query
    to check "does a non-rejected draft already exist" before every insert
    (redundant with the index itself, and reintroduces the exact race the
    index exists to close). Flagged as a known limitation (§13).
14. **Concurrency safety for the four mutation functions is a conditional
    `UPDATE ... WHERE <allowed source states>` plus a `cursor.rowcount` check,
    not an explicit `BEGIN IMMEDIATE`** (finding 14, §5.1). Alternative: open
    every mutating function with `conn.execute("BEGIN IMMEDIATE")` to take the
    write lock before any read. Rejected — with exactly one mutating statement
    per function, the conditional `UPDATE`'s `WHERE` clause already **is** the
    concurrency guard (SQLite re-checks it at write-lock time, not at an
    earlier read), so a second, separate locking step would be redundant
    machinery for the same guarantee, and would still need the same
    `rowcount`-style check afterward to know whether the caller's intended
    transition actually happened. If a future function in this module ever
    needs more than one mutating statement per transaction, `BEGIN IMMEDIATE`
    (or a compensating check) should be revisited then — this decision is
    scoped to functions that mutate exactly one row with exactly one
    statement.
15. **`validate_draft_body` lives in `app/models.py`, not `app/agent/drafting.py`**
    (finding 13, §0.3) — closing a real circular import (`models → drafting →
    models`) that v2.1 would have shipped. This is a straightforward
    placement fix rather than a judgment call with a real alternative: the
    function's only two callers are `OutreachDraft`'s own validator (same
    module, needs no import) and `db.py` (which already imports from
    `app.models` for `Candidate`), so `app/models.py` is the only location
    that serves both without introducing a new edge in the import graph.

---

## 13. Decisions to log in DECISIONS.md (at slice completion, not this commit)

- Draft status and target stage are two separate state machines with explicit,
  shared transition maps; approving a draft is the gate that admits its target to
  the pipeline board; illegal transitions are controlled 409s, not silent
  successes, and never write a misleading audit row.
- Drafts are generated on demand per selected target and once per active target
  (re-draft only after a rejection), honoring the memory non-negotiable — now
  backed by a partial unique index, not only a route check.
- LLM draft grounding is a runtime gate against the target's stored Slice 3
  citations (the draft must cite a verified evidence pair, use its value in the
  body, and name the recipient when one exists); a deterministic, neutral
  heuristic guarantees an evidence-referencing draft with zero keys so demo mode
  completes, and never turns a poor-fit fact into a positive claim.
- The drafting voice prompt is derived from `beautiful-prose` + `humanizer` +
  Mom-Test directness, and asks the model to return the evidence pair it used so
  grounding can be verified.
- Pipeline stage changes are accessible buttons; drag is deferred; a same-stage
  request is a no-op with no audit row.
- Each Slice 4 mutation and its audit row commit in one transaction (a departure
  from Slice 2/3's separate `add_audit` call), because non-negotiable #4 requires
  the action and its audit to be all-or-nothing.
- Tenant isolation and one-active-draft uniqueness are enforced at the database
  boundary (`INSERT … SELECT` tenancy guard, partial unique index, both
  `workspace_id`s qualified in every join), not only in the route.
- Nothing sends: approval is a status change and "contacted" records that the
  human reached out — real message send stays out of scope (SPEC §7).
- `cost_tokens` column exists from this slice but is populated in Slice 6.
- A target's pipeline stage cannot change until one of its drafts is approved —
  enforced by `set_target_stage` itself (an approved-draft existence check
  inside the same transaction as the stage read), not only by what
  `list_pipeline_targets` chooses to display. A stage-change attempt on an
  unapproved target is indistinguishable from a missing/cross-workspace one
  (both resolve to `NotFound`), a deliberate choice to avoid the response
  itself confirming a target's existence in another state.
- Human-submitted draft bodies (Save and Approve) are validated against the
  same 20–1500 character bound as the model's own drafted output, via one
  shared function — a blank approval would defeat the human-approval
  non-negotiable as surely as a blank model draft would.
- The `draft.created` audit row records the drafting outcome (`DraftResult`'s
  status and sanitized reason), not just that a draft now exists — so
  "no key," "key rejected," "provider error," and "model draft failed the
  grounding gate" are all distinguishable in the audit trail even though
  several of them share `model_used == "heuristic"`.
- `add_draft` maps only the specific `one_active_draft_per_target` unique-index
  violation to a dedicated `ActiveDraftExists` exception (identified by
  matching the SQLite error message, since SQLite does not raise a distinctly
  typed exception per constraint); every other integrity failure propagates
  unmapped rather than being silently treated as a harmless double-submit.
- The four Slice 4 mutation functions (`save_draft_body`, `approve_draft`,
  `reject_draft`, `set_target_stage`) enforce their transition guards via a
  conditional `UPDATE ... WHERE <allowed source states>` plus a
  `cursor.rowcount` check, not a read-then-decide pattern and not an explicit
  `BEGIN IMMEDIATE` — the `WHERE` clause is re-evaluated at the moment SQLite
  grants the write lock, so two concurrent requests for the same draft or
  target cannot both succeed; only one `rowcount == 1`, and the audit row is
  written exactly once. `set_target_stage` folds the approved-draft gate into
  the same statement via a correlated `EXISTS`.
- `validate_draft_body` lives in `app/models.py`, called directly by
  `OutreachDraft`'s own field validator (same module) and imported by
  `app/db.py` for human-submitted bodies — not in `app/agent/drafting.py`,
  which would have created a `models → drafting → models` circular import.

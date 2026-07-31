# Slice 4 Plan — Drafting, approval queue, pipeline

Plan for Slice 4 (SPEC.md §6). This document is the single source of truth for
Slice 4's design. No implementation has started — this commit contains only
`SLICE_4_PLAN.md` and a `collaboration.md` log entry.

This is the **v2** plan: the original v1 (`2ded7e9`) was reviewed and revised for
seven owner-approved SDE 2 corrections (§0.1). The corrections tighten Slice 4
toward the non-negotiables (#4 audit, #5 structured output, #6 isolation) and
SPEC §4/§6's "references the cited evidence"; none expand scope beyond SPEC.md.

## 0. Collaboration & model status

- **SDE 1** (this session) authored v1 on the stronger reasoning model
  (Opus 4.8), including the drafting prompt (§4.2), because the drafting voice is
  the one genuinely writing-heavy part of this slice and SPEC.md mandates
  applying the `beautiful-prose` and `humanizer` skills to it. This v2 revision
  is likewise a planning-only pass on Opus; **no code has changed.**
- Recommended **execution model: Sonnet** — with the prompt, state machines,
  grounding gate, and atomic-audit design settled here, implementation is
  mechanical. Stated again at the top of implementation so the owner can confirm
  the switch before code begins (CLAUDE.md).
- Per `collaboration.md` rule 6: implementation begins only after the owner
  confirms this plan has no further outstanding changes. §12 lists the
  interpretive decisions this plan makes, so the owner can veto any before code.
- **Precondition:** Slice 3 (and both hardening passes) is complete and committed
  (`fc5bc62` on `codex/sde-1-slice-2-hardening`, working tree clean, 100 tests
  green). Slice 4 builds on that state (branch choice — continue here vs. merge
  to `main` first — is the owner's call, per rule 6).
- Non-negotiables in play (CLAUDE.md): **#4 a human approves every send and
  every action is audited** — this is the slice where that rule earns its
  keep, and this v2 makes each mutation and its audit row **atomic** (§8);
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
concurrent draft request for the same target raises `sqlite3.IntegrityError`
rather than creating a duplicate active draft. This is the authoritative guard
under a double-submit race; the §6 memory check is the friendly UX layer on top
of it, not the guarantee.

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

The gate between the two machines: **approving a draft admits its target to the
pipeline board** (§7.2). Before any approved draft, a target is a scored
candidate on the campaign page and is *not* on the board. This is the plan's
central interpretive decision (§12, decision 1).

Controlled-response contract (shared by every §6 route, §5 DB function, and
§11 test):

| Condition | Response |
|---|---|
| Target/draft id from another workspace, or missing | resolves to not-found → redirect to the list page (never a leak, never a 500) |
| Malformed enum input (`stage`, `action`) | FastAPI `Literal` typing → **422** |
| Valid enum value but illegal current-state transition | **409** (controlled conflict), no mutation, no audit |
| Double-submit race creating a second active draft | `IntegrityError` → redirect to `/approvals` (the winning draft is already there), no error page |

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
    reason: str | None       # sanitized, safe for audit; None unless a failure occurred

def draft_outreach(brief: Brief, target: dict, settings: dict[str, str],
                   *, known_invalid_key_reason: str | None = None) -> DraftResult: ...
```

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

```python
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
        text = (v or "").strip()
        if len(text) < 20:
            raise ValueError("draft body is too short to be a real message")
        if len(text) > 1500:
            raise ValueError("draft body is too long for an outreach message")
        return text
```

The model must return the message **and** the one evidence pair it chose to
ground it. Schema shape (non-blank fields, length bounds) is enforced here and
driven by `generate_structured`'s existing two-shot retry (non-negotiable #5).
**Truth** — that the pair is real and the body uses it — is a separate runtime
check (§4.4), exactly as Slice 3 separates `FitReason`'s schema from
`_is_grounded`'s runtime check.

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

Two small typed exceptions signal controlled failures to the routes (kept in
`db.py`, imported by `main.py` and the tests):

```python
class NotFound(Exception): ...           # id absent or in another workspace -> route redirects
class InvalidTransition(Exception): ...   # illegal state change -> route returns 409
```

Functions:

```python
def add_draft(workspace_id, target_id, body, model_used, actor="agent") -> int
    # INSERT ... SELECT tenancy guard: inserts only if the target row exists in
    # THIS workspace. rowcount == 0 -> raise NotFound (no leak, no orphan draft).
    # The partial unique index raises sqlite3.IntegrityError if an active draft
    # already exists (double-submit race). Writes draft.created audit + the new
    # draft in one transaction. Returns the new draft id.

def get_draft(workspace_id, draft_id) -> Row | None                       # scoped

def get_active_draft_for_target(workspace_id, target_id) -> Row | None     # latest non-rejected draft, or None (memory/UX check)

def list_pending_drafts(workspace_id) -> list[Row]
    # status IN ('pending','edited'); joins target (both workspace_ids qualified)
    # for name/fit/campaign context. This is the Approvals queue and the nav count.

def save_draft_body(workspace_id, draft_id, edited_body, actor="human") -> None
    # transition guard: current status must allow 'edited' (pending|edited).
    # Sets edited_body, status='edited'; writes draft.edited audit; one txn.
    # Illegal (approved/rejected) -> InvalidTransition. Missing -> NotFound.

def approve_draft(workspace_id, draft_id, submitted_body, actor="human") -> None
    # transition guard: current status must allow 'approved' (pending|edited).
    # If submitted_body (the CURRENT textarea text) differs from the stored
    # (edited_body or body), set edited_body = submitted_body in THIS operation
    # (correction 2 — no lost edits). Set status='approved'. Write ONE
    # draft.approved audit (detail flags "approved with inline edits" when the
    # body changed). All in one transaction.

def reject_draft(workspace_id, draft_id, actor="human") -> None
    # transition guard allows 'rejected' from pending|edited. status='rejected';
    # draft.rejected audit; one txn. Illegal -> InvalidTransition.

def list_pipeline_targets(workspace_id) -> list[Row]
    # Targets with an approved draft. GROUP BY target.id so each target appears
    # AT MOST ONCE; the approved draft text is chosen deterministically
    # (MAX(draft.id) among that target's approved drafts), returning
    # COALESCE(edited_body, body). Carries stage, name, fit_score, campaign_id.
    # Both workspace_ids qualified.

def set_target_stage(workspace_id, target_id, new_stage, actor="human") -> bool
    # Reads current stage + campaign_id scoped to this workspace (missing ->
    # NotFound). Same stage -> no-op, returns False, NO audit (correction 1).
    # new_stage not in STAGE_TRANSITIONS[current] -> InvalidTransition (409).
    # Else UPDATE stage + target.stage_changed audit (detail "old -> new") in one
    # transaction; returns True.
```

- The audit row every function writes includes the correct `workspace_id`,
  `campaign_id`, `target_id`, and `draft_id`: the draft functions look up the
  target's `campaign_id` (and `target_id`) via the scoped join in the same
  transaction; the stage function reads `campaign_id` from the target row it
  already fetched.
- `STAGES`, `STAGE_SET`, `STAGE_TRANSITIONS`, `DRAFT_STATUSES`, and
  `DRAFT_TRANSITIONS` (§3.1) are module constants in `db.py` — one source of
  truth for the DB guard, the routes, and the tests.
- The existing `db.add_audit` (separate connection/commit) stays for the Slice
  2/3 intake/discovery/scoring rows; it is refactored to delegate to the shared
  `_insert_audit` helper so there is one audit-insert code path. Slice 4's new
  actions must be atomic with their mutation, so they never call the standalone
  `add_audit` — they audit inside their own transaction.

---

## 6. Routes (`app/main.py`)

Each route is `workspace`-scoped via the existing `get_current_workspace`
dependency. A `db.NotFound` from any function is caught and redirected (the
not-found contract); a `db.InvalidTransition` is caught and returned as
`HTTPException(status_code=409)`; a `sqlite3.IntegrityError` on draft creation
redirects to `/approvals` (§3.1 race row).

```
POST /targets/{target_id}/draft
    - MEMORY / UX check: if get_active_draft_for_target(...) is not None,
      redirect to /approvals (the existing active draft is already there) —
      do NOT create a second. This is the friendly layer; the partial unique
      index is the authoritative guard behind it.
    - Else draft_outreach(brief, target, settings) -> DraftResult; add_draft(...)
      (which writes draft.created atomically). IntegrityError (lost the race) ->
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
    - InvalidTransition -> 409. NotFound -> redirect /approvals. Else -> /approvals.

GET  /pipeline
    - list_pipeline_targets(workspace) grouped into the five stage columns (§7.2).

POST /targets/{target_id}/stage
    - stage: PipelineStage = Form(...)  # Literal over STAGES -> 422 on garbage
    - set_target_stage(...). InvalidTransition -> 409. NotFound -> redirect
      /pipeline. Same-stage -> no-op (returns False, no audit). Else -> /pipeline.
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
| `draft.created` | agent | `add_draft` |
| `draft.edited` | human | `save_draft_body` |
| `draft.approved` | human | `approve_draft` (detail flags inline edits when the body changed at approval) |
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
  same transaction** as the change (§8); **nothing is ever transmitted** —
  "approved" is a status, and marking "contacted" is the owner recording that
  *they* reached out (SPEC §7: real send integration is out of scope).
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
  grounding gate).
- `app/templates/approvals.html`, `app/templates/pipeline.html`.
- `tests/test_slice4_drafting.py` (retained — §11.1).

**Modified:**
- `app/models.py` — `OutreachDraft` (body + evidence_key + evidence_value).
- `app/db.py` — `draft` table + partial unique index in `init()`; the §5
  draft/pipeline functions (atomic mutation+audit, tenancy guard, transition
  guards); `STAGES`/`STAGE_SET`/`STAGE_TRANSITIONS`/`DRAFT_STATUSES`/
  `DRAFT_TRANSITIONS` constants; `NotFound`/`InvalidTransition`; the shared
  `_insert_audit` helper (`add_audit` refactored to delegate to it).
- `app/main.py` — the §6 routes (including the single `/drafts/{id}/action`
  dispatcher and its `DraftAction` literal); `nav_context` helper; the §6.2
  `campaign_detail` draft-CTA join + `_draft_cta`; Activity list.
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
writes. Covering every correction:

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
10. **One-active-draft concurrency / uniqueness** (correction 6): a second
    `add_draft` while an active (pending/edited/approved) draft exists raises
    `sqlite3.IntegrityError` (the partial unique index); the route maps that to a
    `/approvals` redirect, not a duplicate.
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

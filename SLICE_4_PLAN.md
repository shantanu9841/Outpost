# Slice 4 Plan — Drafting, approval queue, pipeline

Plan for Slice 4 (SPEC.md §6). This document is the single source of truth for
Slice 4's design. No implementation has started — this commit contains only
`SLICE_4_PLAN.md` and a `collaboration.md` log entry.

## 0. Collaboration & model status

- **SDE 1** (this session) created this plan on the stronger reasoning model
  (Opus 4.8), and authored the drafting prompt here rather than deferring that
  judgment to execution — the drafting voice is the one genuinely
  writing-heavy part of this slice, and SPEC.md mandates applying the
  `beautiful-prose` and `humanizer` skills to it. Both skills were loaded
  during planning; §4.2 is the result.
- Recommended **execution model: Sonnet** — with the prompt and state machine
  settled here, implementation is mechanical. Stated again at the top of
  implementation so the owner can confirm the switch before code begins
  (CLAUDE.md).
- Per `collaboration.md` rule 6: implementation begins only after the owner
  confirms this plan has no further outstanding changes. §12 lists the
  interpretive decisions this plan makes, so the owner can veto any before code.
- **Precondition:** Slice 3 (and its hardening pass) is complete and committed
  (`b48ee4a` on `codex/sde-1-slice-2-hardening`, working tree clean, 72 tests
  green). Slice 4 builds on that state (branch choice — continue here vs. merge
  to `main` first — is the owner's call, per rule 6).
- Non-negotiables in play (CLAUDE.md): **#4 a human approves every send and
  every action is audited** — this is the slice where that rule earns its
  keep; #2 demo mode always completes (drafting must work with zero keys); #5
  structured output validated with retry; #6 workspace isolation; the `memory`
  rule (draft once per target, then reuse — never silently re-draft a known
  target); the `Local data` rule; and the `Not building` rule — **nothing
  sends.** Approving a draft changes a status. It never transmits a message.

---

## 1. Goal and done-when (SPEC.md §6)

Generate a personalized draft per target selected for outreach, referencing the
cited evidence. Drafts enter the approval queue as pending. A human edits,
approves, or rejects; each action is audited. Approved targets appear on a
pipeline board (queued, contacted, replied, live, declined) with stage changes
by button.

**Done when:** a draft can be generated, edited, approved or rejected with the
audit trail recording each step, and an approved target shows on the pipeline
board. Nothing sends on its own.

---

## 2. What already exists (reused unchanged)

- `target` table already carries `stage TEXT NOT NULL DEFAULT 'queued'` (added
  in Slice 2's schema for exactly this slice) — the pipeline column lives here,
  **no migration to the target table needed**.
- `audit` table already carries `target_id` and `draft_id` columns — draft and
  stage actions write to them directly, **no migration to the audit table
  needed**. `db.add_audit(workspace_id, campaign_id, actor, action, detail,
  target_id, draft_id)` already accepts both.
- The pipeline-stage design tokens (`--pl-queued` … `--pl-declined`, each with a
  `-subtle` background, in both themes) **already exist in `tokens.css`** — the
  board uses them directly, no token additions.
- `llm.generate_structured(schema, system, user, settings)` is reused unchanged
  for the LLM drafting path (returns a validated schema, `None` with no key, or
  raises `LLMError`). `GEMINI_MODEL` names the model for the `model_used` column.
- `target.fit_reasons_json` (grounded citations from Slice 3) is the evidence
  the draft references — no re-derivation, the draft reads what scoring stored.

The **only new table is `draft`** (SPEC.md §3), added idempotently in `db.init()`
like every other table. `eval` remains a Slice 6 table and is not created here.

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

`cost_tokens` is created now (the column is part of SPEC's schema) but left
`NULL` this slice — `llm.py` does not yet record token cost; that is Slice 6's
explicit job. Recording it now would be a fabricated number.

### 3.1 Two distinct state machines

Draft status and target stage are **separate** and must not be conflated:

- **Draft status** (the `draft.status` column): `pending → edited → approved`
  or `pending/edited → rejected`. About one piece of outreach copy.
- **Target stage** (the existing `target.stage` column): `queued → contacted →
  replied → live`, with `declined` as a side exit. About where a prospect sits
  in the funnel.

The gate between them: **approving a draft admits its target to the pipeline
board** (§7). Before any approved draft, a target is a scored candidate on the
campaign page and is *not* on the board. This is the plan's central interpretive
decision (§12, decision 1).

---

## 4. Drafting module (`app/agent/drafting.py`)

Mirrors `intake.py`/`scoring.py`'s status-carrying shape.

```python
class DraftStatus(str, Enum):
    LLM_OK = "llm_ok"                    # drafted by the model, personalized
    NO_GEMINI_KEY = "no_gemini_key"      # no key anywhere -> heuristic template
    INVALID_GEMINI_KEY = "invalid_gemini_key"
    GEMINI_ERROR = "gemini_error"
    HEURISTIC_FALLBACK = "heuristic_fallback"  # model replied but failed the personalization gate

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
  caller already knows this Gemini key is rejected (it won't in this slice's
  route, since drafting is the only model call on that path, but the parameter
  keeps the shape uniform and future-proofs a combined flow), skip the live call.
- `target` is the persisted target row as a dict, carrying `name`,
  `handle_or_domain`, `reach`, `raw_json`, and `fit_reasons_json`. Evidence for
  the prompt is the **grounded fit reasons** Slice 3 stored — the draft
  references what scoring already verified, closing the loop between the two
  slices.

### 4.1 Structured schema (`app/models.py`)

```python
class OutreachDraft(BaseModel):
    body: str

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

Single-field, but validated and retried through `llm.generate_structured`
(non-negotiable #5). A one-line "message" or an essay both fail validation and
drive the existing two-shot retry, then the heuristic fallback.

### 4.2 The drafting prompt (authored from `beautiful-prose` + `humanizer` + The Mom Test)

`SYSTEM_PROMPT`, baked into `drafting.py`. The rules below are distilled from the
two skills SPEC.md names, plus Mom-Test directness (talk about the recipient's
world, make one concrete ask, don't pitch in the abstract):

```
You write one short outreach message from a business to a prospective partner
it wants to work with. A person will read every message before anything is
sent, and will reject anything that reads like a form letter.

Ground the message in the specific evidence given about this company. Reference
at least one concrete fact about them by name — their industry, their size, what
they do. Never invent a fact that isn't in the evidence.

Make exactly one clear, small ask: a short reply, a quick call, a sample. Not a
meeting invite with five options. Not "let me know if you're interested."

Voice:
- Plain declarative sentences. Vary their length. A short one can land hard.
- Concrete nouns, strong verbs. Name the thing.
- Address the company by name at least once.
- No em dashes. Use periods and commas.
- No "not just X, it's Y" reversals.
- No opener flattery ("I love what you're doing", "huge fan"), no corporate
  filler ("reaching out", "excited to connect", "explore synergies", "at its
  core", "in today's landscape"), no emojis, straight quotes only.
- 60 to 110 words. A greeting, one or two sentences of specific relevance, one
  ask, a sign-off line the sender will fill in.

Write only the message body. No subject line, no notes.
```

The prompt is the same for both target types; §4.3's heuristic differs only in
which evidence field it leads with. Creator-specific tuning (handles, platform)
arrives with the creator sources in Slice 5.

### 4.3 Deterministic heuristic (demo-mode / no-key path)

`_heuristic_draft(brief, target) -> str` builds a usable, evidence-referencing
message with zero keys, so demo mode completes. It reads the target's **stored
grounded fit reason** (Slice 3's `fit_reasons_json`) to get one true evidence
fact, and names the company — guaranteeing "references the cited evidence" by
construction, not by hope:

```
Hi {name} team,

We make {product}. {evidence_sentence} That's the kind of {audience_noun} we
work best with, so {name} stood out.

Would you be open to a short reply to see if it's worth a quick call?

Best,
[Your name]
```

- `{evidence_sentence}` is composed from the first grounded fit reason, keyed by
  its `evidence_key`: industry → "You work in {value}."; employees → "At about
  {value} people, you're the size of partner we ship with."; country → "You're
  based in {value}, where we're expanding."; name-only fallback → "We came
  across {value} while looking for partners." Every branch quotes the exact
  stored evidence value, so the message references real, cited evidence.
- If the target has no stored fit reasons at all (shouldn't happen post-Slice-3,
  but handled), the evidence sentence is dropped and the message still names the
  company and states the ask — honest, not fabricated.

The heuristic is a demo-mode stand-in for real copy, stated plainly — the LLM
path is the real writer when a key is present.

### 4.4 Personalization gate (the prose analog of Slice 3 grounding)

Slice 3 could check a citation's exact value against evidence because citations
are discrete. A prose draft "referencing evidence" is not reliably
substring-checkable (a model may paraphrase "third-party logistics" as "your
logistics operation"). So the gate here is deliberately lighter and honest: a
model draft must **name the company** (case-insensitive substring of
`target.name`) when a real name is available. A draft that never names the
recipient is not personalized. On failure, `generate_structured`'s retry has
already fired; drafting then returns the **heuristic** body (which always names
them) with `status = HEURISTIC_FALLBACK` and `model_used = "heuristic"`. When
`target.name` is absent or the Slice-3 default `"Unknown company"`, the gate is
skipped (there is nothing meaningful to check), and the model body is kept.

Documented as lighter than Slice 3's grounding, and why (§12, decision 4).

---

## 5. DB functions (`app/db.py`)

All `workspace_id`-scoped, same tenant-isolation discipline as every existing
function (forgetting the scope is a `TypeError`, never a silent leak):

```python
def add_draft(workspace_id, target_id, body, model_used) -> int          # status defaults 'pending'
def get_draft(workspace_id, draft_id) -> Row | None
def get_active_draft_for_target(workspace_id, target_id) -> Row | None    # latest non-rejected draft, or None
def list_pending_drafts(workspace_id) -> list[Row]                        # status in (pending, edited); joins target for context
def update_draft_body(workspace_id, draft_id, edited_body) -> None        # sets edited_body, status='edited'
def set_draft_status(workspace_id, draft_id, status) -> None             # 'approved' | 'rejected'
def list_pipeline_targets(workspace_id) -> list[Row]                      # targets with an approved draft, + their stage
def set_target_stage(workspace_id, target_id, stage) -> None             # validates stage against the allowed set
```

- `list_pipeline_targets` is the board's data source: targets that have **at
  least one approved draft**, each carrying its `stage`, `name`, `fit_score`,
  `campaign_id`, and the approved draft's final text (`edited_body` if present
  else `body`) for the card. Isolation and campaign scoping via the join's
  `WHERE workspace_id = ?`.
- `set_target_stage` guards `stage in {queued, contacted, replied, live,
  declined}` and raises on anything else (defense in depth behind the route's
  typed parameter), and scopes the `UPDATE` by `workspace_id AND id` so a stray
  id from another workspace updates nothing (the Slice 1 guarantee).
- `STAGES` (the ordered tuple) and `STAGE_SET` live as module constants so the
  route, the DB guard, and the template all read one source of truth.

---

## 6. Routes (`app/main.py`)

Each route is `workspace`-scoped via the existing `get_current_workspace`
dependency and fetches the target/draft *within* the workspace before acting
(an id from another workspace resolves to `None` → redirect, never a leak).
Every mutating route writes an audit row (§8) before redirecting.

```
POST /targets/{target_id}/draft
    - Load the target in this workspace (404-ish redirect if not found).
    - MEMORY GUARD: if get_active_draft_for_target(...) is not None, do NOT
      create a second draft — redirect to /approvals (the existing draft is
      already there). Draft once per target; re-draft only after a rejection.
    - Else: draft_outreach(brief, target, settings) -> DraftResult;
      add_draft(...); audit "draft.created" (actor=agent, target_id, draft_id,
      detail=DraftResult.reason); redirect to /approvals.

GET  /approvals
    - list_pending_drafts(workspace): each row rendered as an editable card
      (target name + fit + campaign link, a <textarea> of edited_body|body,
      Save / Approve / Reject).

POST /drafts/{draft_id}/edit      -> update_draft_body; audit "draft.edited";   -> /approvals
POST /drafts/{draft_id}/approve   -> set_draft_status('approved'); audit "draft.approved"; -> /approvals
POST /drafts/{draft_id}/reject    -> set_draft_status('rejected'); audit "draft.rejected"; -> /approvals

GET  /pipeline
    - list_pipeline_targets(workspace) grouped into the five stage columns.

POST /targets/{target_id}/stage
    - stage: PipelineStage = Form(...)   # Literal type -> FastAPI 422 on garbage,
      the same controlled-422 pattern Slice 2 used for target_type.
    - set_target_stage(...); audit "target.stage_changed" (detail="{old} -> {new}");
      redirect to /pipeline.
```

`campaign_detail` (existing `GET /campaigns/{id}`) gains, per target row, either
a **Draft outreach** button (POST to `/targets/{id}/draft`) or, if a draft
already exists, its status ("Pending review" / "Approved" / "Rejected") linking
to `/approvals`. The targets query is extended with a `LEFT JOIN` to the active
draft so the template stays logic-light.

### 6.1 Shared nav context

`base.html` shows an **Approvals** count pill on every page, so the pending
count must be in every page's context. A small helper
`nav_context(workspace) -> dict` returns `{workspace, workspaces,
approvals_count}`; each route spreads it into its template context. This is a
minor, mechanical refactor of the existing `{workspace, workspaces}` context and
future-proofs the Slice 6 nav counts. `approvals_count = len(list_pending_drafts)`.

---

## 7. UI

### 7.1 Approvals page (`approvals.html`, new)

A single column of pending/edited draft cards (the queue). Each card:
- Header: target name, fit pill (reusing Slice 3's `.fit--*` classes), and a
  link to its campaign.
- An editable `<textarea class="textarea">` pre-filled with `edited_body or body`.
- Three controls in one row: **Save** (POST edit), **Approve** (primary),
  **Reject** (destructive/ghost). Save and Approve can be one form with two
  submit buttons, or two small forms — either keeps every action a real button.
- Empty state (reusing `.empty`): "No drafts waiting for review."

### 7.2 Pipeline board (`pipeline.html`, new)

Five columns in stage order (queued, contacted, replied, live, declined), each
headed by a pipeline pill in its `--pl-*` token with a mono count. Cards under
each column show the target name, fit, campaign link, and **contextual stage
buttons** — one small `<button>` per sensible next move, each its own tiny POST
form to `/targets/{id}/stage`:

- queued → [Contacted] [Decline]
- contacted → [Replied] [Decline]
- replied → [Live] [Decline]
- live → (terminal this slice)
- declined → (terminal this slice)

Real `<button>` elements: keyboard and focus for free, consistent with the
Slice 3 caret decision. **Drag-and-drop is explicitly out of scope** for this
slice — "button or drag" in SPEC is satisfied by buttons, and drag is extra JS
with no accessibility gain (§12, decision 3). Empty board reuses `.empty`.

### 7.3 Campaign detail additions

- A **Draft / status** cell per target row (§6).
- A compact **Activity** list at the bottom: the campaign's audit rows rendered
  human-readably (action label + detail + timestamp), so the audit trail the
  done-when requires is *visible*, not just written. Rendering uses an explicit
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

## 8. Audit (`app/audit_banners.py` + route calls)

Draft and stage actions are **human/agent actions, not campaign banners** — they
are written straight to the `audit` table with explicit action strings and are
*not* added to the `campaign_detail` banner filter (which stays intake / discovery
/ scoring). The action strings, defined as module constants so they are greppable
and typo-proof:

| action | actor | written by |
|---|---|---|
| `draft.created` | agent | POST /targets/{id}/draft |
| `draft.edited` | human | POST /drafts/{id}/edit |
| `draft.approved` | human | POST /drafts/{id}/approve |
| `draft.rejected` | human | POST /drafts/{id}/reject |
| `target.stage_changed` | human | POST /targets/{id}/stage (detail = "queued -> contacted") |

For the §7.3 Activity list, an explicit `ACTION_LABELS: dict[str, str]` maps each
action (including the existing intake/discovery/scoring ones) to a human phrase
("Draft approved", "Stage changed", …). A helper `label_for(action)` returns the
phrase or a sensible default, so an unmapped action never crashes the page.

---

## 9. Demo mode, structured output, and the non-negotiables (how each is met)

- **#2 demo mode:** zero keys → `draft_outreach` uses the §4.3 heuristic;
  editing, approving, and the whole pipeline are pure DB/UI with no model call.
  The full slice demos start to finish with no keys.
- **#4 human approves every send + audit:** a draft is inert text until a human
  acts; approve/reject/edit/stage each write an audit row; **nothing is ever
  transmitted** — "approved" is a status, and marking "contacted" is the owner
  recording that *they* reached out (SPEC §7: real send integration is out of
  scope).
- **#5 structured output:** the LLM path returns a validated `OutreachDraft`
  with the existing two-shot retry.
- **#6 isolation:** every draft/pipeline query and mutation is `workspace_id`
  scoped; §11 verifies a second workspace sees none of it.
- **memory:** the §6 memory guard drafts once per target and reuses the stored
  draft; the board and queue read persisted rows, never re-generate.

---

## 10. Files changed / created (implementation phase, not this commit)

**New:**
- `app/agent/drafting.py` (schema-driven LLM path + heuristic + personalization gate).
- `app/templates/approvals.html`, `app/templates/pipeline.html`.
- `tests/test_slice4_drafting.py` (retained — §11.1).

**Modified:**
- `app/models.py` — `OutreachDraft`.
- `app/db.py` — `draft` table in `init()`; the §5 draft/pipeline functions;
  `STAGES`/`STAGE_SET` constants.
- `app/main.py` — the §6 routes; `nav_context` helper; `campaign_detail` draft
  cell + Activity list.
- `app/audit_banners.py` — the §8 action constants + `ACTION_LABELS`/`label_for`.
- `app/templates/base.html` — Approvals + Pipeline nav items with the count pill.
- `app/templates/campaign_detail.html` — Draft cell per target + Activity list.
- `app/static/css/app.css` — pipeline board, approval cards, stage pills, draft
  status chips, activity list (tokens only).
- `PROGRESS.md`, `DECISIONS.md`, `collaboration.md` at slice end.

`tokens.css` and the `target`/`audit` schemas need **no** changes (§2). **This
commit** touches only `SLICE_4_PLAN.md` and `collaboration.md`.

---

## 11. Verification (proportional to risk)

### 11.1 Retained tests (`tests/test_slice4_drafting.py`)

Mocked (no real provider call, no real key), temp SQLite, no `outpost.db` writes:

1. **Schema:** `OutreachDraft` rejects a blank/too-short body and a >1500-char
   body; accepts a normal message.
2. **Heuristic draft:** with zero keys, `draft_outreach` returns a body that
   names the target and quotes its stored grounded evidence value;
   deterministic; `model_used == "heuristic"`, `status == NO_GEMINI_KEY`.
3. **LLM path kept:** `generate_structured` mocked to a body that names the
   target → kept, `model_used == GEMINI_MODEL`, `status == LLM_OK`.
4. **Personalization gate:** `generate_structured` mocked to a body that never
   names the target → drafting returns the heuristic body,
   `status == HEURISTIC_FALLBACK`, `model_used == "heuristic"`. Gate skipped when
   `target.name` is `"Unknown company"` (model body kept).
5. **Credential paths:** `None` → heuristic/`NO_GEMINI_KEY`;
   `LLMError(INVALID_KEY)` → heuristic/`INVALID_GEMINI_KEY`, reason set;
   `LLMError(ERROR)` → heuristic/`GEMINI_ERROR`. Never raises.
6. **Draft lifecycle (DB):** `add_draft` → pending; `update_draft_body` → edited
   with `edited_body` set; `set_draft_status` approve/reject; `list_pending_drafts`
   excludes approved and rejected; `get_active_draft_for_target` ignores a
   rejected draft (so a re-draft is allowed only after rejection).
7. **Approval admits to the board:** `list_pipeline_targets` returns a target
   only after its draft is approved, not before; the card carries `edited_body`
   when present.
8. **Stage machine:** `set_target_stage` accepts each valid stage and rejects
   garbage; scoped by workspace; the route's typed `PipelineStage` returns 422
   on an invalid value.
9. **Routes (TestClient):** POST draft → one pending draft + `draft.created`
   audit; the memory guard makes a second POST *not* create a second active
   draft; approve → `approved` + `draft.approved` audit + target now on
   `/pipeline`; reject → `rejected`, target absent from `/pipeline`; stage POST
   advances the target and writes `target.stage_changed`.
10. **Isolation:** drafts, the queue, the board, and stage changes are all
    workspace-scoped; a second workspace sees none of them.

### 11.2 Manual / live verification

- **No-key path:** in a scratch zero-key workspace, draft a target (heuristic),
  see it in Approvals, edit it, approve it → it appears on the Pipeline board in
  Queued; advance it through Contacted/Replied/Live and Decline another; confirm
  every step wrote an audit row (direct `outpost.db` query) and the Activity list
  shows them; the Approvals nav count reflects the queue. Computed-style check
  that the five stage pills resolve to their `--pl-*` tokens in both themes.
- **Live Gemini (required — a mock can't prove the prompt yields a human draft):**
  one drafted target against a freshly rotated Gemini key pasted through Settings
  only (located by length/timestamp, never read), confirming `model_used ==
  GEMINI_MODEL`, a body that reads human and names the company, and — per the
  Slice 2/3 rule — no credential anywhere in console, audit `detail`,
  `git diff`, `git log`, or tracked files.
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
3. **Stage changes are buttons, not drag.** SPEC's "button or drag" is satisfied
   by accessible `<button>` controls; drag is deferred as extra JS with no
   accessibility benefit.
4. **A light personalization gate, not prose grounding.** The model draft must
   name the company; free prose can't be reliably value-checked the way Slice 3's
   discrete citations were. Failing drafts fall back to the always-personalized
   heuristic.
5. **`cost_tokens` is created but left NULL**, populated in Slice 6 when `llm.py`
   records token cost. Writing a number now would be fabricated.
6. **Drafts are generated on demand, per selected target** (SPEC: "per target
   selected for outreach"), not auto-at-discovery — honoring the memory rule and
   keeping the human in control of what gets drafted.

---

## 13. Decisions to log in DECISIONS.md (at slice completion, not this commit)

- Draft status and target stage are two separate state machines; approving a
  draft is the gate that admits its target to the pipeline board.
- Drafts are generated on demand per selected target and once per target
  (re-draft only after a rejection), honoring the memory non-negotiable.
- The drafting voice prompt is derived from `beautiful-prose` + `humanizer` +
  Mom-Test directness; a deterministic heuristic guarantees an
  evidence-referencing draft with zero keys so demo mode completes.
- A light personalization gate (the draft must name the company) is the
  prose-suitable analog of Slice 3's exact-value citation grounding; failing
  drafts fall back to the heuristic.
- Pipeline stage changes are accessible buttons; drag is deferred.
- Nothing sends: approval is a status change and "contacted" records that the
  human reached out — real message send stays out of scope (SPEC §7).
- `cost_tokens` column exists from this slice but is populated in Slice 6.

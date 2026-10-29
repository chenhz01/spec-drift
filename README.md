# spec-drift

Detect when a [spec-kit](https://github.com/github/spec-kit) spec stops describing current behaviour.

Zero dependencies. Single file. No LLM call. Runs in CI in under a second.

## Why

spec-kit's premise is one spec per feature. That works until feature 009 changes
the behaviour that feature 001 specified — and 001 is never updated. Nothing tells
you this happened. Over months, `specs/` becomes a mix of accurate and stale
documents with no way to tell them apart without reading all of them.

Consolidating everything into one master spec is the usual suggestion, but it
destroys the only record of *why* each feature existed. This tool takes the other
route: keep the history, **flag the drift**, let a human decide.

## Four checks

| | Check | Signal |
|---|---|---|
| **D1** | Unresolved clarifications | spec still contains `[NEEDS CLARIFICATION: ...]` |
| **D2** | Status vs. reality | `Status: Draft` but FRs already appear in source / `Implemented` but no FR has a test anchor |
| **D3** | FR lost its test anchor | an FR's distinctive terms appear in **no** test file |
| **D4** | Suspected supersession | FR of an older spec shares ≥45% of its distinctive terms with an FR of a newer spec that it never references |

D4 is the one that answers *"is spec 001 now outdated because of 009?"* — it
returns **candidates**, never verdicts.

## Usage

It's one file with no imports outside the stdlib — copy `spec_drift.py` into your repo
and run it. Nothing to install.

```bash
python spec_drift.py --root .                  # human-readable
python spec_drift.py --root . --json           # machine-readable
python spec_drift.py --root . --fail-on D3     # CI gate: exit 1 if any FR lost its anchor
```

Expects the standard layout:

```
specs/001-user-login/spec.md
specs/009-two-factor/spec.md
tests/...
src/...
```

## Try it on the bundled reproduction

The `demo/` directory reproduces the scenario from spec-kit#620 — a login spec that
is silently extended by a later 2FA spec:

```bash
python spec_drift.py --root demo
# → 8 findings: 6 high (D1 + D3), 2 mid (D2 + D4)
```

## Three filters that turned out to be mandatory

Building this, every naive version gave wrong answers. The three fixes:

1. **Strip comments and docstrings before matching.** A trailing comment reading
   `# nothing below covers: sign in with email` made the requirement look covered.
   It was the exact sentence saying it *wasn't*.
2. **Drop shared vocabulary (document frequency > 40%).** `email` and `password`
   appear in nearly every FR. One test mentioning "email" for a *format* check made
   every requirement look anchored. This filter alone moved the result from 3 findings to 7.
3. **Require two distinct terms to co-occur.** A test named
   `test_email_validation_rejects_missing_at` contains "rejects", which "matched" an
   unrelated requirement about rejecting reused OTPs.

The generalisable point: *"the vocabulary overlaps"* and *"the requirement is covered"*
are different claims. Plain grep cannot separate them.

## Validated on real projects, not just on my own fixture

The first version of D4 reported **406 findings** on a 35-spec project. That's not a strict
checker, that's a broken one — D4 compares every pair, and specs from the same project share
vocabulary by construction. Three fixes (threshold 34%→45%, one finding per pair, cap at 20)
brought it to 31.

| repo | specs | tests | first run | after fix |
|---|---|---|---|---|
| `thooams/uolt` | 35 | 103 | 406 | 31 |
| `XEBIA-ACE/New_Prompt_UMS` | 23 | 27 | 19 | 19 |
| `sardylan/live-qso-map` | 18 | 76 | 12 | 11 |

The signal that survived real data best was **D1** (unresolved `NEEDS CLARIFICATION`) and
**D2** (status says Draft, implementation already exists) — both are near-zero-ambiguity checks.
D3 and D4 need a human in the loop.

## Then I scanned the whole ecosystem, and found something more basic than drift

The 406→31 fix above was a calibration problem. Scanning every public repo I could find
that actually contains `specs/*/spec.md` turned up a different problem.

57 projects · 825 specs · 9,864 requirements:

| | |
|---|---|
| specs still marked `Draft` | **364 (44%)** |
| unresolved `[NEEDS CLARIFICATION: ...]` | **239, across 25 projects** |
| projects where *every* spec is `Draft` | **13** |
| projects with `specs/` but zero parseable FRs | **6** |

The number that reframes the question isn't the overlap count. It's the 44%.

If almost half the specs in the wild never reach any terminal state, then
*"is this spec still accurate?"* is not a question the data can answer — because no spec
was ever marked as accurate in the first place. **There is no "done" to drift away from.**

So the tool detects a symptom. Three changes would remove the cause, each about one line:

1. **A `Superseded-by:` header field.** Turns "this was replaced by something" from
   tribal knowledge into a queryable edge.
2. **`Status: Active` as a legal value.** Right now the only way out of `Draft` is
   `Implemented`, so 44% stay in `Draft` forever and the field stops carrying information.
3. **A gate: a non-`Draft` spec may not contain `[NEEDS CLARIFICATION]`.** 239 instances
   of that exist today.

The 6 projects with `specs/` but no parseable FRs are a separate warning: any checker
hard-coded to the `FR-###` pattern silently returns nothing on part of the ecosystem.

The scanner behind those numbers is `ecosystem_scan.py` in this repo — it reads only
public raw files, so the counts are reproducible.

## Honest limitations

- **Thresholds are the weak part.** 40% / 2-term / 45% are calibrated on 5 projects
  (2 synthetic, 3 real). That is not a lot.
- **D4 is lexical, not semantic.** Two requirements can share terms and still be
  independent. Treat output as a reading list, not a bug list.
- **Non-English specs are approximated.** Keyword extraction has no tokenizer; it slices
  CJK runs into 2–4 character chunks. Useful, not linguistically correct.
- **No SC (success criteria) checking yet.** SCs are usually not test-anchored by
  construction, so they need a different signal.
- **Whether the remaining findings are true positives is unverified.** The tool proved it
  can find *candidates*; it has not proved every candidate is real.

## Self-check

```bash
python selfcheck.py     # 14 assertions: must fire on demo/, must stay silent on clean/
```

A checker that only ever reports "looks fine" (or only ever reports problems) isn't
trustworthy. The self-check asserts both directions.

CI goes one step further: the `gate` job asserts that `--fail-on D3` **actually exits 1** on
`demo/` and **exits 0** on `clean/`. A gate that cannot fail is not a gate — this repository
is only useful if its own gate is proven to fire.

## Licence

Apache-2.0

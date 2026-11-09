# VirtualPLC — GitHub branch and release gates (verified 2026-11-08; eleven-check update verified 2026-11-09)

## Verified state: enforced (GitHub API, repo admin, 2026-11-08; ruleset 26796594 re-verified 2026-11-09: active, 0 bypass, 11 checks)

- Branch ruleset **26796594** `main-ci-pr-gate`: enforcement **active**, target
  `~DEFAULT_BRANCH`, `bypass_actors: []` (none). Emergency path: disable the
  ruleset and log it in #54. Rules:
  - `deletion`, `non_fast_forward`: main cannot be deleted or force-pushed.
  - `pull_request`: **0 required approvals** (solo owner; required external
    review is an independent policy choice, not a project gate).
  - `required_status_checks`, `strict=false`, eleven GitHub Actions
    (integration 15368) contexts: `build`; `test (ubuntu-latest, 3.10|3.11|3.12|3.13|3.14)`;
    `test (windows-latest, 3.10|3.11|3.12|3.13|3.14)`. The `test-macos` job is
    informational until green on main, then promoted by a ruleset update.
- Tag ruleset **26796603** `release-tag-immutability`: active, `refs/tags/v*`,
  rules `update`, `deletion`, `non_fast_forward`, no bypass. Creation stays
  allowed: the release workflow triggers on new `v*` tags.
- Verification: throwaway PR #66 could not be merged while the (then nine) checks were
  pending (closed). Effective main rules via API: `deletion`,
  `non_fast_forward`, `pull_request`, `required_status_checks`.
- Because `strict=false`, rebase each PR onto current main and get a fresh
  11/11 before merging (peer-agreed).
- Repository is **public**. Latest release **v0.7.0** (2026-11-09).
- Release workflow triggers on **push of `v*` tag**: version/tag assertion,
  full test, wheel build, PyPI publish via trusted identity, GitHub release
  assets. Its first step fails closed unless a `ci.yml` **push** run on
  `main` completed with `success` for the exact tagged commit, so tag only
  after main CI is green.

Ruleset reference:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release gate — intentionally manual

- **Do not create or push a `v*` tag without explicit user release
  authorization.** Doing so triggers `.github/workflows/release.yml`
  and can publish to PyPI when the `pypi` environment permits it.
- Confirm source commit is approved/merged on main, separate main CI
  is completed success (all required checks) at the exact candidate SHA, and
  `pyproject.toml` project.version equals the prospective tag.
- Release tags are immutable after creation (tag ruleset); review the
  source commit, built artifacts and release evidence. Never treat
  PyPI `skip-existing` as evidence that the intended artifact was
  published; compare artifact identities/version explicitly.
- No manufacturer PLC parity: the listed Mitsubishi AG-versus-AD
  and I-versus-E manual clauses remain NOT_VERIFIED. No production
  network, physical PLC or direct hardware use in these CI gates.

## Status

Governance tracker #54 is closed by this change: both rulesets are active and
verified above.

# VirtualPLC — GitHub branch and release gates (verified 2026-11-08)

## Verified state: enforced (GitHub API, repo admin, 2026-11-08)

- Branch ruleset **26796594** `main-ci-pr-gate`: enforcement **active**, target
  `~DEFAULT_BRANCH`, `bypass_actors: []` (none). Emergency path: disable the
  ruleset and log it in #54. Rules:
  - `deletion`, `non_fast_forward`: main cannot be deleted or force-pushed.
  - `pull_request`: **0 required approvals** (solo owner; required external
    review is an independent policy choice, not a project gate).
  - `required_status_checks`, `strict=false`, nine GitHub Actions
    (integration 15368) contexts: `build`; `test (ubuntu-latest, 3.10|3.11|3.12|3.13)`;
    `test (windows-latest, 3.10|3.11|3.12|3.13)`.
- Tag ruleset **26796603** `release-tag-immutability`: active, `refs/tags/v*`,
  rules `update`, `deletion`, `non_fast_forward`, no bypass. Creation stays
  allowed: the release workflow triggers on new `v*` tags.
- Verification: throwaway PR #66 could not be merged while the 9 checks were
  pending (closed). Effective main rules via API: `deletion`,
  `non_fast_forward`, `pull_request`, `required_status_checks`.
- Because `strict=false`, rebase each PR onto current main and get a fresh
  9/9 before merging (peer-agreed).
- Repository is **public**. Latest release **v0.5.0** (2026-10-30); later
  source features are unreleased.
- Release workflow triggers on **push of `v*` tag**: version/tag assertion,
  full test, wheel build, PyPI publish via trusted identity, GitHub release
  assets. It does **not** automatically require main CI's 9 checks.

Ruleset reference:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release gate — intentionally manual

- **Do not create or push a `v*` tag without explicit user release
  authorization.** Doing so triggers `.github/workflows/release.yml`
  and can publish to PyPI when the `pypi` environment permits it.
- Confirm source commit is approved/merged on main, separate main CI
  is completed success 9/9 at the exact candidate SHA, and
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

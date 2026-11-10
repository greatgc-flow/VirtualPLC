# VirtualPLC — GitHub branch and release gates (verified 2026-11-08; eleven-check update verified 2026-11-09)

## Verified state: enforced (GitHub API, repo admin, 2026-11-08; ruleset 26796594 re-verified 2026-11-09: active, 0 bypass, 11 checks)

- Branch ruleset **26796594** `main-ci-pr-gate`: enforcement **active**, target
  `~DEFAULT_BRANCH`, `bypass_actors: []` (none). Emergency path: disable the
  ruleset and record it in a new governance issue. Rules:
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
- Repository is **public**. Latest release **v0.11.0** (2026-11-10, UTC).
- Release workflow triggers on **push of `v*` tag**: version/tag assertion,
  full test, wheel build, PyPI publish via trusted identity, GitHub release
  assets. Its first step fails closed unless a `ci.yml` **push** run on
  `main` completed with `success` for the exact tagged commit, so tag only
  after main CI is green.
  It also fails closed before building or publishing unless `docs/HANDOFF.md`
  has a `## <date> release X.Y.Z — release-note source` section that follows the
  restricted format (plain Markdown, no code fences, links only as inline
  `[text](https://...)`; `tools/release_notes.py`). That body becomes the top
  of the GitHub release notes, unchanged.

Ruleset reference:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release gate — intentionally manual

- **Do not create or push a `v*` tag without explicit user release
  authorization.** Doing so triggers `.github/workflows/release.yml`
  and publishes to PyPI via trusted publishing. Since 2026-11-10 the GitHub
  `pypi` environment accepts deployments **only from tags matching `v*`**
  (custom deployment policy, verified via the environments API); there is no
  required reviewer. Together with the tag ruleset (no update/delete) and the
  workflow's fail-closed main-CI check, these are the publication gates.
- Release tooling is pinned in `requirements-release.txt` (build, twine) and
  used by both `ci.yml` and `release.yml`; Dependabot updates it.
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

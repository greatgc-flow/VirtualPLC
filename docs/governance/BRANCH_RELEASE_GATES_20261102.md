# VirtualPLC — GitHub branch and release gates (2026-11-02)

## Evidence: observed, not yet enforced

- This repository is **public**; latest confirmed main at review was
  `7ea3b718dd5aba848a9b9dc1e0b1642560e9b433`.
- GitHub branch API reported `protected=false`; repository rulesets API returned
  `[]`. Therefore no enforced main ruleset was observed at review.
- The branch-protection details endpoint returned HTTP 403
  `Resource not accessible by integration`: this is **not** proof
  that settings were created or modified. The connected GitHub app has
  no available admin write operation for repository rulesets.
- The newest exact-main push CI was run #41436034796: success **9/9**;
  Ubuntu Python 3.11 **7,159 PASS**. No open PRs. Latest release is
  **v0.5.0** (2026-10-30); source features after that date are unreleased.
- The release workflow currently triggers on **push of v* tag** and
  includes version/tag assertion, full test, wheel build, PyPI publish via
  trusted identity, then GitHub release assets. It does **not**
  automatically require the separate main CI's 9 check conclusions.

## Owner/admin UI checklist — not performed by this document

Follow GitHub's current official instructions:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository

1. Open `greatgc-flow/VirtualPLC` -> Settings -> Rules -> Rulesets
   (labels may vary). Create a new **branch ruleset** named
   `main-ci-pr-gate`, target default branch/main, set enforcement **Active**.
2. Require a pull request before merging; start at **0 required approvals**
   if the owner is a solo developer. A required external review is an
   independent policy choice, not a previously approved project gate.
3. Require these **nine existing CI checks** before merging, choosing
   GitHub Actions as expected provider when available:
   - build
   - test (ubuntu-latest, 3.10)
   - test (ubuntu-latest, 3.11)
   - test (ubuntu-latest, 3.12)
   - test (ubuntu-latest, 3.13)
   - test (windows-latest, 3.10)
   - test (windows-latest, 3.11)
   - test (windows-latest, 3.12)
   - test (windows-latest, 3.13)
4. Block force pushes and deletion of main. Do not add an unrestricted
   bypass list. Select any bypass only deliberately with owner review.
5. Create a separate **tag ruleset**, include `v*`. Allow deliberate
   *new* release tag creation but restrict updates/deletions of existing
   release tags. Do not restrict *all* creations or the release process
   would have no valid trigger.
6. Check that PRs cannot merge while a required check is pending or
   failing; verify the active ruleset UI and accessible ruleset API.
   A dry-run on a disposable test PR is preferable to bypassing main.
7. Record the active ruleset IDs/URLs, effective 9 check names,
   any bypass actors and verification date in issue #7; do not
   equate a document or a green CI run with enforcement.

Official ruleset rules reference:
https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Release gate — intentionally manual

- **Do not create or push a `v*` tag without explicit user release
  authorization.** Doing so triggers `.github/workflows/release.yml`
  and can publish to PyPI when the `pypi` environment permits it.
- Confirm source commit is approved/merged on main, separate main CI
  is completed success 9/9 at the exact candidate SHA, and
  `pyproject.toml` project.version equals the prospective tag.
- Confirm the release tag is immutable after creation, review the
  source commit, built artifacts and release evidence. Never treat
  PyPI `skip-existing` as evidence that the intended artifact was
  published; compare artifact identities/version explicitly.
- No manufacturer PLC parity: the listed Mitsubishi AG-versus-AD
  and I-versus-E manual clauses remain NOT_VERIFIED. No production
  network, physical PLC or direct hardware use in these CI gates.

## Acceptance / current blocker

Documentation and project handoff may be merged with ordinary PR checks.
Actual ruleset activation **remains open** in issue #7 because this
connection cannot write admin rules. Do not mark #7 complete until
the owner/admin applies and verifies both branch and tag policies.

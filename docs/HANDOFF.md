# Handoff (2026-10-23)

State: virtual-plc 0.3.0 released (PyPI + GitHub), main clean, CI green, 5,891 local tests pass.
Design: docs/DESIGN.md. Unverified-vs-real-PLC backlog: issue #2.

## Open items
1. Register PyPI trusted publisher (project virtual-plc, owner greatgc-flow, repo VirtualPLC, workflow release.yml, env pypi) so tag pushes auto-publish. Until then release.yml fails at `publish` (harmless).
2. User must revoke the PyPI token that was pasted in chat (never stored anywhere).
3. Re-run Gemini (ag) review after quota reset (~2026-10-24 09:00; `--writable` required).
4. oracle-watch.yml and the release publish path are unexercised on GitHub.
5. Verify unverified behaviors against manuals (end codes C200/C201, ASCII hex numbering, dword order, etc.).
6. Fork greatgc-flow/pymcprotocol (D:\Engram1\workspace\pymcprotocol; origin=fork, upstream=senrust): feature work not started.

## Working setup
- peerhub store: `D:\Engram1\.peerhub\core.db` (use `--db`); peers cc, cx, ag. Run `peerhub guide` first.
- cx sandbox has no network/pip; run installs/builds yourself (`.venv` in repo; build with `python -m build --no-isolation`).

## Standing rules (from user memory)
- Reuse peerhub sessions (`--stream`/`--request-id`); unanimous peer consensus for material decisions; "끝장토론" before implementation (TDD/SDD-ready).
- Minimize this terminal's tokens; delegate even small edits. Do NOT fall back to cc when cx/ag are quota-blocked; wait for reset (cc only for short reviews/ballots).
- AI-to-AI/code/docs in English; Korean to the user. Terse terminal output.
- Keep branches/workspace clean; update deps before release; remove over-engineering (github.com/greatgc-flow/VerySimpleGuide); log lessons as GitHub issues.
- Near limits: write handoff + print ONE-line continuation prompt. Never assume unverified facts; ask ambiguities in batches.

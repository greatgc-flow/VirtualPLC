# Session record 2026-11-10/11: MECE completeness review, releases from 0.8.0

Purpose: a single, collaboration-ready record of what was asked, how it was
analysed and designed, how the work was run across peers, and what resulted.
Authoritative current state stays in [HANDOFF](../HANDOFF.md) and the code;
this file explains *why* and *how*.

## 1. Requirements (owner, condensed)

| # | Requirement | Where it is satisfied |
|---|---|---|
| R1 | Review VirtualPLC completeness MECE and score every review item | §2 grid, §4 score history |
| R2 | Build a sample project (pymcprotocol + VirtualPLC) that users can understand and reuse | `examples/bottling_line/` |
| R3 | Cross-check mutual/recursive closure (vertical and horizontal), fix gaps, report scores; repeat until all are 100; then release | §2–§4, releases in §5 |
| R4 | Check peer quotas every turn; collaborate in parallel; spend under-used quota on reviewing finished work or preparing next work so each pool is used by its reset | §3.3 |
| R5 | When review loops cycle or stall, improve structure/design/environment and prepare permissions/tools/settings first | §3.4 |
| R6 | File lessons learned as issues in the owner's repositories | §5.3 |
| R7 | Audit and slim peer instructions that burn quota quickly; move workspace-only rules out of global locations | §6 (in progress) |
| R8 | Document requirements, analysis/design, process and results for collaboration | this file |
| R9 | Owner decisions 2026-11-11: P1 new `--stream` per task and no pasted guide/diag output; L1 quota check right before delegating; #78 keep `host, port, profile` / `profile` positional, include `Memory`, `DeprecationWarning` in 0.11.0 | §6, issue #78 |

## 2. Analysis and design

### 2.1 Review grid (MECE)

Rows (product areas, disjoint):
P1 wire protocol · P2 PLC state model · P3 transport & lifecycle ·
P4 fault injection · P5 interfaces (CLI, API, guide, README, sample) ·
P6 reference/oracle data · P7 delivery (packaging, CI, release, governance).

Columns (quality dimensions, disjoint): Q1 correctness · Q2 test adequacy ·
Q3 docs accuracy & closure · Q4 usability · Q5 safety · Q6 maintainability.

Cross-closure checks (the "recursive" part — every artefact points at, and is
pinned by, the others): C1 every CLI flag in guide + docs + test · C2 every
documented behavioural claim has a test · C3 every command/device has test +
doc · C4 every public API documented + tested · C5 every emitted end code
documented + tested · C6 README snippets execute · C7 version/metadata
consistent · C8 no dangling references (links, anchors, files, issue numbers).

### 2.2 Scoring rule

A cell is 100 only when the reviewer cannot name a concrete, verifiable
defect (file:line + repro + exact fix). From round 10 on, a **materiality
rule** applied: deduct only for defects that violate a documented contract or
are reachable from supported inputs (including the repository's own content);
out-of-contract hypotheticals are recommendations.

### 2.3 Key designs made in this session

| Topic | Decision | Rationale |
|---|---|---|
| Sample project | Five runnable steps; `plc_map.py` as the single device map; `plant.py` stands in for ladder logic as a second client; three failure policies (no reply → reconnect + retry idempotent calls; one-shot request bit → never re-send, report "outcome unknown"; PLC end code → never retry) | Teaches the decisions real PLC clients need; one writer per device avoids read-modify-write races |
| `Memory.write_atomic` (0.9.1) | Per-request `ChainMap` overlay, committed in place | 0.9.0 copied the whole device family per random write (≈80 ms at 4M points); overlay is O(request) and keeps atomicity and `max_cells` accounting |
| `max_cells` + SD203 | Server names SD203 when the CPU-state mirror needs the last free cell | The cap counts SD203; the old message did not explain the off-by-one |
| Release notes | HANDOFF `## <date> release X.Y.Z — release-note source` section is published **unchanged**; `tools/release_notes.py` only extracts and validates (no code fences; links only inline `[text](https://...)`) and fails the release before building | A translating Markdown parser kept growing edge cases; restricting the input contract removed the class of bugs |
| UDP fault actions (0.10.0) | `duplicate`, `truncate(n)`, `corrupt_header` applied after dispatch; reorder deferred | Datagram-native faults without cross-request state |
| UDP rate limit (0.10.0) | Opt-in token bucket per source IP, dropped right after `recvfrom` (before parse, fault plan and the shared request lock), `rate_limited` metric, 1024-peer LRU, persists across stop/start | Prevents a UDP flood from starving TCP clients; per-IP because source ports are cheap |
| Keyword-only API (#78) | Implemented in 0.11.0 (DeprecationWarning); 1.0 adds `*` and removes the shim (owner timeline) | No call in the repository breaks; owner decisions recorded 2026-11-11 (R9, #78) |

## 3. Process

### 3.1 Roles

| Role | Who | Notes |
|---|---|---|
| Coordinator | cc terminal (Sonnet/Opus) | Integrates, runs the full suite once per state, merges, tags |
| Implementers | Opus sub-agents in isolated git worktrees | TDD (RED → GREEN), PR only, no merge |
| Independent scorers | Fable (r6–r11) and Opus (r1–r5) | Read-only; different model from the author where possible |
| Cross-family check | ag (Gemini, G pool) | Newcomer review of the sample; 0.9.1 cross-check |

### 3.2 Loop

1. Score the grid with independent reviewers (rows split between reviewers).
2. Fix findings with TDD in parallel workers (file ownership split to avoid conflicts).
3. Re-score with a fresh or resumed reviewer; repeat until every cell is 100.
4. PR → required CI (11 checks) → squash merge → main CI → tag → release workflow → verify PyPI/GitHub hashes and a clean install.

### 3.3 Quota pacing

Every turn: `peerhub diag`. Pools under pace (e.g. cc C-7D/F-7D early in the
week) were spent on independent reviews and next-work preparation (#92, #93,
#94, #78 design) in parallel; pools forecast to exhaust before reset (cx X-7D,
ag A-7D, later ag G-7D) were rested.

### 3.4 Bottlenecks found and removed

| Bottleneck | Fix |
|---|---|
| Review rounds kept finding new edge cases in the release-notes parser | Narrowed the contract (validator only); materiality rule in briefs |
| Parallel full suites exhausted Windows ephemeral ports (WinError 10048) | Coordinator runs the suite once and hands the result to reviewers; owner widened the dynamic port range to 10000–65534 |
| cp949 console broke UTF-8 output (hidden by the 3.15 venv's UTF-8 mode) | Tool writes UTF-8 bytes; locale checks use `py -3.13` |
| Workflow validation needed ad-hoc venvs | `yq` on PATH; actionlint 1.7.12 installed (checksum verified) |
| Tag push / GitHub settings blocked by the auto-mode classifier | Narrow allow rules approved by the owner, removed after use |
| `socket.socketpair()` is AF_UNIX on Linux | Socket tests use a loopback TCP pair |
| `git add -A` committed agent worktrees as gitlinks | `.gitignore` ignores `.claude/worktrees/` |

## 4. Score history

| Round | Target | Result |
|---|---|---|
| r1–r3 | 0.7.0 tree | P1 80–94 … P7 87–97; C1 partial, C5/C8 fail |
| r4 | after fixes | 85–100 |
| r5 | 0.8.0 RC | 99.88 → last 3 findings fixed → 100 |
| sample | `examples/bottling_line` (ag) | 82 → 100 |
| r6 | 0.9.0 as released | 36 cells 100; P2/P3/P5/P7 96–99 |
| r7–r10 | 0.9.1 RC | 99.86 → 99.79 → 99.67 → (redesign) 99.81 → 99.93 → **100.00**; ag cross-check 100 |
| r11 | 0.10.0 candidate | 99.5 (two doc findings) → 99.9 (date finding) → re-score of the released commit: **100** |
| r12 | 0.11.0 candidate (#98) | 99.6 (shim warned on invalid calls) → fixed with a `bind()` oracle test → **100** |
| final | whole-product audit of v0.11.1 | 99.76 → six minor findings fixed in 0.11.2 |

## 5. Results

### 5.1 Releases

Dates are UTC release dates (GitHub `publishedAt`); the session ran into 2026-11-11 KST.

| Version | Date | Highlights |
|---|---|---|
| 0.8.0 | 2026-11-10 | MECE review fixes (~70 findings), bottling-line sample, closure tests |
| 0.9.0 | 2026-11-10 | `Memory(max_cells=N)` / `--max-cells`, opt-in TCP metrics |
| 0.9.1 | 2026-11-10 | Random-write overlay (perf), SD203 cap message, release-notes gate |
| 0.10.0 | 2026-11-10 | UDP fault actions, per-IP UDP rate limit, flaky-test fix |
| 0.11.0 | 2026-11-10 | `DeprecationWarning` for positional `Server`/`Memory` parameters after `profile` (#78 step 1; 1.0 enforces) |
| 0.11.1 | 2026-11-10 | `-v` logs one line per IP per 10 s for UDP rate-limit drops; rate limit × fault-action tests; troubleshoot hint (#95) |

### 5.2 Pull requests

#86 (0.8.0), #87, #89, #90 (0.9.0), #91 (0.9.1), #92, #93, #94, #96 (0.10.0), #97 (session record), #98, #99 (0.11.0), #100, #101 (0.11.1).

### 5.3 Issues filed (lessons learned / follow-ups)

- peerhub [#338](https://github.com/greatgc-flow/peerhub/issues/338) — show which store `diag` reads
- peerhub [#339](https://github.com/greatgc-flow/peerhub/issues/339) — `diag --plan` spend/hold/rest per pool
- peerhub [#345](https://github.com/greatgc-flow/peerhub/issues/345) — guide: review-loop best practices
- VirtualPLC [#95](https://github.com/greatgc-flow/VirtualPLC/issues/95) — UDP review follow-ups
- VirtualPLC [#78 comment](https://github.com/greatgc-flow/VirtualPLC/issues/78) — keyword-only API design

### 5.4 Open items

- #13 remaining: UDP reorder action.
- #78: 1.0 enforcement (add `*`, remove the shim).
- §6 peer-instruction diet (R7).

## 6. Peer instruction diet (R7)

Audit (2026-11-11 UTC): per-turn / per-ask payloads ranked by size × frequency.
The largest costs were the cc Artifact tool (~15K tokens per lead call), the cc
skill listing (~4K), unused Codex app connectors and plugin skills (~3–6K per
cx call), and a machine-global agy rules file that carried another workspace's
rules (including rules that contradict this workspace's peer usage).

| Item | Change | Measured effect |
|---|---|---|
| cx | `CODEX_HOME/config.toml` `[features]`: `apps`, `plugins`, `remote_plugin`, `image_generation`, `multi_agent` = false (backup kept) | first-call input 13.3K tokens (baseline 15.5–19.5K) |
| cc peers | `VirtualPLC/.claude/settings.local.json` (git-ignored): `enableArtifact` / `enableWorkflows` / `syncClaudeAiSkills` false, `skillOverrides` for unused skills; the lead session is unchanged | `claude -p` total input 20.4K (baseline 26.8K, −24%) |
| ag | global `~/.gemini/GEMINI.md` is workspace-neutral; workspace rules live in the workspace's own GEMINI.md | conflicting rules no longer reach this workspace's asks |
| lead memory | always-loaded index trimmed; overlapping quota notes merged; stale handoff memory replaced by a short state note | index 991 B → 724 B |

Owner decisions applied afterwards (2026-11-11): a new `--stream` per
independent task with reuse only for true follow-ups, and only the needed lines
of `peerhub guide` / `diag` output in prompts (session reuse had made cc asks
re-read ~0.7M input tokens at the median); quota checks run right before each
delegation instead of every turn.
Kept on purpose: safety rules, agy permission rules, the AGENTS.md
auto-injection (~0.8K once per session) and the VirtualPLC AGENTS.md.

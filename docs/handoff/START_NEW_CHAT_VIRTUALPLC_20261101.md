# VirtualPLC — NEW CHAT START / 2026-11-01

**User instruction:** Resume development from the last verified remote state.
Read this and `docs/HANDOFF.md` at HEAD; prioritize the **actual latest
GitHub main/PR/Issues/CI** over all commit hashes and summaries below.
User authorizes safe commits, new branches/issues/PRs, and reviewed squash
merges after passing gates. DO NOT publish to PyPI, connect to physical
equipment or production/factory network, manufacture vendor facts,
or silently change actual PLC communication semantics.

## First turn: required, concrete deliverables

1. Fetch latest remote `main` HEAD, list **all open PRs/issues**, recent
   Actions and actual workflow job results; check for work newer than
   this handoff. At last checkpoint before PR #43, main was
   `54e65cb3074187cd1adb2e006d28aeaf58948a2e`, independent
   postmerge [CI #41271965936](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41271965936)
   success 9/9 (Ubuntu/Windows Python3.10–3.13 plus build), Ubuntu3.11
   7,094 PASS. Only unrelated open PR was Dependabot #11.
2. Read `AGENTS.md`, `docs/HANDOFF.md`,
   `docs/research/RNCPU_MANUAL_PDF_EVIDENCE_KIT_20261101.md`,
   `docs/research/RNCPU_R04CPU_DUAL_MANUAL_REVISION_GATES_20261101.md`,
   `docs/DESIGN.md`, `tools/manual_revision_evidence.py`,
   `tests/test_manual_revision_evidence.py`, and relevant issues #14/#2/#25.
3. Confirm exact [PR #43](https://github.com/greatgc-flow/VirtualPLC/pull/43)
   status, final candidate SHA, 9-job PR CI and any merge; if not merged
   and 9/9 succeeds with source unchanged, squash merge and check new
   independent main push CI 9/9. If the candidate fails, read exact job
   logs, apply focused fix on branch and re-verify.
4. Provide Korean 3-line technical outcome and link the PR/CI/handoff
   comments. Clearly distinguish automated software tests from
   authentic manufacturer manual clause verification.

## Latest branch work awaiting exact CI

`fix/manual-evidence-source-integrity-20261101`, [PR #43](https://github.com/greatgc-flow/VirtualPLC/pull/43):
an independent patch to the **developer-only** offline manual PDF kit.
- Original PR #42 added local `tools/manual_revision_evidence.py`, only
  stdlib runtime dependencies; optional local `pdftotext`.
  Handles authentic source edition pairs Ethernet AD+AG, CPU E+I.
  Emits SHA256, weak edition label candidates, PDF page indices,
  bounded term snippets and `NOT_VERIFIED`. No automatic vendor
  certification and no source PDF tracked.
- Specific source-integrity gap: one identical document could be
  submitted as two revisions and PDF bytes could be replaced between
  initial digest and extraction, causing misleading evidence.
- TDD tests-only SHA
  `7aab81d3d9c018f97f7cc82603b389b755d4d0ed`;
  [RED CI #41276732098](https://github.com/greatgc-flow/VirtualPLC/actions/runs/41276732098)
  Ubuntu3.11: **7,095 PASS + 4 new expected failures**.
  New tests cover same path, byte-identical different filenames,
  identical bytes in different manual families, same-size mutation
  during extract and stable-source read-only regression.
- Implementation commit
  `8a545eb0eaeb94ec0de7e648cc9640be294a64fd` rejects
  duplicate SHA-256 across all edition roles and rechecks each source
  SHA+size after local text extraction. Existing valid input report
  JSON schema unchanged. Research/DESIGN/HANDOFF updated.
- **Do not mistake a successful intermediate commit's CI for full
  final candidate success**: check PR HEAD and actual final run.
- Source availability: authentic new AG/I PDF originals **not
  obtained**. Source catalogue publication is verified; manufacturer
  clauses AD↔AG / E↔I are **NOT_VERIFIED**. No PDF bytes/SHAs
  for vendor source originals exist in this session.

## Invariant architectural decisions / SSOT

- Independent PLC uses a separate OS process. Multiple TCP/UDP
  listeners within one process share one PLC memory/state.
- Runtime `virtual_plc/ethernet.py` owns Q/L/iQ-R runnable
  EthernetSettings and reexports the reference API;
  `virtual_plc/ethernet_reference.py` owns FX5/RnCPU
  **OFFLINE reference-only** manufacturer tables and validators.
  No upward reverse import; do not invent defaults for an unsupported
  hardware model. `virtual_plc/rncpu_reference.py` composes R04CPU
  opening, timer and port-slot checks.
- Exact model/scope required (R04CPU CPU built-in != RJ71EN71 network
  module). Distinguish configured GX Works3 user slots from
  simultaneous TCP clients, host/kernel timers from vendor module
  timers, SLMP server vs MELSOFT/GOT/CPU services, and vendor-safe
  ports vs simulator ephemeral socket port 0.
- Ethernet Application manual SH-081257ENG-**AD** previously scoped
  R04CPU pp.324–326, 329–330, 396–397, 554; current listed
  **AG 2026-10** clauses NOT_VERIFIED.
- CPU Module SH-082488ENG-**E** opening A031H remote STOP/RUN
  p.3, 684–685; current listed **I 2026-08** clauses NOT_VERIFIED.
  PR #41 added distinct `cpu_manual_revision` opt-in gate;
  never infer E/I parity. Both release/version gates stay
  `newer_revision_comparison=NOT_VERIFIED` until exact original
  manufacturer clause comparison, with PDF provenance.
- User preference VerySimpleGuide
  <https://github.com/greatgc-flow/VerySimpleGuide>:
  minimum independently testable modules, no gratuitous abstraction,
  recursive MECE, optional settings, null/empty/invalid types,
  CLI/doc example parity, TDD RED before GREEN.
- `AGENTS.md` has a 40-line enforced limit in
  `tests/test_guide.py` (don't exceed).
- Python 3.10–3.13 tested on Windows/Ubuntu. Complete gate:
  build + eight matrix tests **9/9 PR**, then squash merge,
  separate **9/9 exact SHA main push**; synthetic tests/pymcprotocol
  are not physical PLC validation. No PyPI release without explicit
  publish request.

## Future work (only when original source available)

1. Acquire authentic, full **AD+AG** and **E+I** manufacturer PDF
   pairs directly from official publication pages, preserving source
   URL, date, original SHA256 and license. Original copyright PDFs
   stay local, never commit them to public GitHub.
2. Execute developer-only offline CLI using local `pdftotext`
   and keep JSON evidence. Verify *actual* PDF page/table images and
   printed page numbers; keyword matches/identical counts are not
   proof of unchanged clauses.
3. Manual AD↔AG review: R04CPU built-in configured slot/port
   limits; reserved/system service ports; A038H timers, unit
   increments, defaults and inequalities; model/firmware scope.
   E↔I review: A031H Opening Method and remote STOP→RUN reconnect
   behavior. Document changes, page links and provenance.
4. Update source registry and tests **only with exact verified
   official evidence**. Physical PLC qualification remains a separate
   unmet gate under issue #2.

## Handoff hygiene

At the end of each substantial session, record current exact
remote head, PR state, exact CI jobs and tests, unresolved risks
and next steps in `docs/HANDOFF.md` or relevant issue #25/#14.
No blanket commit of secrets or personal user memory; only technical
decisions/provenance essential for next session. Check GitHub commit
proof after writes and keep local ephemeral work clean.

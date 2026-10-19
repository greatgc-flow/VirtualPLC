# M1 handoff — 2026-10-19

## Lineage
Initial research -> v1.1 recursive MECE design -> v1.2 208-case catalog -> total audit -> M1 Red/Green loopback prototype. No previous design version is silently declared tested or retired. The complete design, 208-case specification, and earlier audit are distributed in the current ChatGPT project package. This Git branch contains a minimal runnable vertical slice and a focused regression subset.

## Independently observed local evidence
- 19/19 memory-domain tests passed against the domain adapter.
- 45/45 3E Binary/TCP network cases passed against a spawned loopback process.
- 48/48 new independent unit/network regressions passed.
- 20/20 static audit tests passed.
- Suite reference validator: PASS (208 specified / 69 legacy ID links / 34 P0 requirement links).
- Exact JUnit CASE-ID gate report: 45 passes observed but UNATTESTED, with 154 P0 cases NOT_RUN (199 total).
- Full vendor fidelity: UNKNOWN, not PASSED. Release: HOLD.

These are three overlapping lenses, **not 112 unique P0 cases**.

## Known open gates (fail closed)
- G0-E: numeric end-code mapping and model/firmware-specific station, route and limits confirmation.
- G0-C: install/pin audited pymcprotocol version and compare raw captured wire transactions.
- G1: connect remaining runtime-adapter tests; 208 specified does NOT imply 208 executable.
- G2: broaden representative end-to-end and negative-path coverage beyond local prototype.
- G3: Windows/Linux real CI evidence, fuzz, resource limits, monitoring/security and bounded performance.
- G4: all 199 P0 evidence attested, gate approval and release candidate.

## Protocol references
- Mitsubishi Electric SLMP Reference Manual SH-080956ENG:
  https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf
- pymcprotocol documentation: https://pymcprotocol.netlify.app/
- Independent community reference 3E Binary mock server:
  https://genbapy.dev/articles/slmp-dummy-server-python

Read vendor manual as normative; independent community examples are not substitutes for field compatibility verification.

## Work discipline
1. Add a failing test for one contract.
2. Implement minimum change.
3. Re-run domain -> packet -> TCP tests.
4. Update traceability and test evidence; do not mark NOT_RUN as PASS.
5. Keep this branch separate from release-ready main until G0/G1/G2/G3/G4 pass.

## Public repository hygiene
No private PLC IPs, production topology, customer details, captures with secrets or business evidence. Keep tests local-only. Do not switch bind to 0.0.0.0 without a separate security architecture and explicit authorization.

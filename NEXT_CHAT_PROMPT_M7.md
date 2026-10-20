# VirtualPLC M7 continuation

Continue `greatgc-flow/VirtualPLC` from its **latest** branch and Draft PR #1. Start by verifying the GitHub SHA, PR status, Actions history, and the M6 package file-by-file SHA256. Read `docs/M6_PROGRESS.md`, `M6_REMAINING_P0.json`, `suite/catalog/test_cases.jsonl`, `scripts/run_m6.py`, `evidence/m6_gate.json` and original design. Do not roll back the fixed 208-case SSOT.

M6 local results: 261 pytest PASS (+5 unittest subtests), 173/199 unique P0 observed PASS, 26 NOT_RUN, zero attested, release HOLD. No real installed pinned pymcprotocol wheel, no validated Mitsubishi vendor error codes or Windows review; do not mark such cases green.

Next: independently obtain SHA256-verified official PyPI `pymcprotocol==0.3.0` wheel and run D/M raw capture tests; verify manufacturer profile end-codes; design opt-in supported routing; implement bounded receiver/load benchmarks, structured replay metadata, real Windows/Linux evidence, licensing and independent gate review. Keep GitHub PUBLIC data synthetic, Actions inactive, Draft PR unmerged and main untouched. Continue with Red→Green→Refactor and explicit CASE-ID evidence. If any requirement is contradictory (notably 1000-word load while cap is 960), record ADR and fail closed until resolved.

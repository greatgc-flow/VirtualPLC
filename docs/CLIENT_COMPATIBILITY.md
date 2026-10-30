# Client compatibility and verification boundaries

**Baseline:** VirtualPLC v0.5.0, `main` at `1ccf10be7352`, reviewed 2026-10-31 KST.

This is the **single version-specific contract** for interpreting client-facing
examples and regressions. It does not claim that a physical Mitsubishi PLC
implements any simulator-only policy. See [BEHAVIOR](BEHAVIOR.md),
[DESIGN](DESIGN.md), [manual provenance](manual/PROVENANCE.md), and issues
[#2](https://github.com/greatgc-flow/VirtualPLC/issues/2) /
[#5](https://github.com/greatgc-flow/VirtualPLC/issues/5).

| Target | Exact reference | Evidence in VirtualPLC | Claim |
| --- | --- | --- | --- |
| Upstream `pymcprotocol` | PyPI `pymcprotocol==0.3.0`; `requirements-dev.txt` pin | Real client + raw-protocol tests, CI OS/Python matrix | **Primary tested client contract** |
| `greatgc-flow/pymcprotocol` fork | [`46eb391a2116`](https://github.com/greatgc-flow/pymcprotocol/commit/46eb391a2116140763d863001a4fb5dbdbd85525), untagged fork main at this review | Fork's client improvements merged; no released artifact or independent VirtualPLC fork matrix verified here | **Experimental source snapshot; not the stock PyPI package** |
| Physical PLC hardware / vendor MC implementation | No hardware model + firmware + recording pair specified | Manual-derived vectors and explicitly unverified simulator policies only | **Unverified; do not connect to production/physical equipment for this simulator** |

## What changes between clients

For upstream `pymcprotocol==0.3.0`, observed limitations are intentional
regression targets, **not** valid MC response semantics:

- A single `recv(4096)` without complete framed-receive validation may return
  truncated data for large reads or on TCP fragmentation.
- Short or empty binary responses can be mistaken for success; response
  header/serial/length checks are not complete.
- ASCII device-number serialization in this client can use decimal text where
  vendor manuals specify hexadecimal for X/Y/B/W and related devices.
- Simulator's `--ascii-numbering compat` preserves pinned client interoperability;
  `--ascii-numbering manual` is the explicit vendor-oriented alternative.

The fork's main branch contains fixes for response framing, short responses,
error information, device numbering, limits and other client behavior, as
recorded in [the handoff](HANDOFF.md). **Do not infer** that a
`pip install pymcprotocol` installs those fixes; the fork had no published
release at the recorded checkpoint. Its source commit is not a validated
product-version contract until an installable artifact is published and
cross-tested.

## Validation policy

1. Keep `requirements-dev.txt` as the exact upstream oracle pin. Do not
   bump it implicitly when updating the fork or this documentation.
2. Run the existing `pytest` / CI matrix and the oracle drift watcher.
   Classify an upstream API change separately from a simulator regression.
3. When a tagged, installable fork artifact is available, add an **optional**
   independent fork compatibility check; never silently replace the upstream
   oracle. Record fork commit/tag, test result, transport (3E/4E,
   ASCII/binary), profile and known divergence.
4. Tag every new manual or real-PLC observation with provenance and firmware
   details before upgrading an `unverified` behavior to `verified`.
5. Keep one small sample per supported client version in the README, and
   avoid maintaining duplicated method/device tables in prose.

No runtime behavior changes are introduced by this document.

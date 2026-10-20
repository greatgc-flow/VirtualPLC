# M23 continuation — VirtualPLC

1. Verify current GitHub `greatgc-flow/VirtualPLC` Draft PR #1 and `main` separately. Do not merge or enable CI without explicit instruction.
2. Verify M22 ZIP CRC and every top-level `FILE_SHA256_MANIFEST.json` entry before using its `project/` source.
3. The M22 local runner `scripts/m22_soak.py` performs isolated-server-RSS measurements; local 1/4/8-client short soak 7,800 requests, zero observed errors. Regression 755 pytest + 5 unittest subtests, 183/199 P0 locally observed. These are **not** vendor/platform/independent acceptance.
4. Preserve external 16 P0 cases in `backlog/M20_BACKLOG.json`; do not request Windows runs repeatedly when no external evidence has arrived. No artificial passing of blocked gates.
5. Next M23 develop optional fault→retry/recovery and duration-bounded sustained-load time-series, MECE across connection/partial frame/recovery; no production PLC traffic, keep core lean, null/empty and timeout explicit, fail-closed evidence, no unsupported SLA.
6. Preserve one ZIP (including original M22 evidence and M21 prior) and verified GitHub Draft PR changes, without uploading sensitive runtime evidence to public GitHub.

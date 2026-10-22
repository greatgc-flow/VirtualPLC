# Migration to v2 M0

The old implementation remains at `archive/m1-m29`. The following files were
inspected with `git show archive/m1-m29:<path>`, without checking out the tag:

- `suite/catalog/test_cases.jsonl` (208 rows).
- `tests/compat/test_pymcprotocol_030.py`.
- `tests/compat/requirements-pymcprotocol.txt` (wheel hash).

`tests/data/scenarios.jsonl` contains ten deduplicated scenario inputs for M1,
not executable server tests. It preserves concrete actions and source labels,
without gates, evidence, priorities, requirements, or progress metadata. Catalog
expectations are design inputs, not independently verified protocol claims.
The old D9999 boundary is illustrative; M1 must use its configured range.

## Mapping to DESIGN T1–T18

| Seed | Migration decision |
|---|---|
| T1 | Carry the actual Type3E D100 roundtrip `[0x1995, 0x1202, 0x1130]`; merge CASE-0027/0109. Other D roundtrip permutations remain archived as redundant inputs. |
| T2 | Carry Type3E M10 `[1, 0, 1, 0, 1]`, including odd padding; merge CASE-0028/0110/0168 and the intent of CASE-0009–0011. |
| T3 | New v2 bit-device word packing test. Drop CASE-0014/0186's contrary expectation that M word access is unsupported. |
| T4 | New positive X/Y/B/W/ZR addressing tests. Drop CASE-0093's unsupported-X expectation. |
| T5 | Carry the range-overflow intent of CASE-0013/0062/0088–0090; share the partial-range input with T12. Do not inherit hardcoded profile limits or old error bodies. |
| T6 | Carry zero/oversize count intent of CASE-0013/0091/0189. Exact profile limits are M1 work. |
| T7 | Carry generic unsupported-command intent of CASE-0018/0184. The old unsupported-random-read assumption is limited to M1 (random commands arrive at M2). |
| T8 | New v2 Q-class rejection of iQ-R subcommands; assert only a nonzero end code until the error row is defined. |
| T9 | Carry bytewise fragmentation CASE-0003/0075/0172. Drop half/three-piece duplicates CASE-0173/0174. |
| T10 | Carry two coalesced requests CASE-0004/0022/0175, including FIFO write/read intent CASE-0205. Drop three-frame duplicates CASE-0076/0102/0176. |
| T11 | Carry EOF in header CASE-0073/0180 and payload CASE-0066/0074/0103/0181 as two distinct inputs. |
| T12 | Carry partial-range failure CASE-0090/0096/0190 and short payload CASE-0034/0117/0191: validate before any mutation. |
| T13 | Carry shared visibility CASE-0021/0101/0204 and overlapping writers plus reader CASE-0015/0094/0097/0206; readers see complete vectors. Drop reset races CASE-0016/0095 from M1 (control semantics deferred to M5). |
| T14 | New echo length 1/960 tests. |
| T15 | New CPU type name/code tests. |
| T16 | New large valid raw-socket response test. Do not inherit old caps as a server limit; 4096 is the client receive limit. |
| T17 | Carry the byte-comparison intent of CASE-0029/0111. Rewrite expected bytes by hand independently of codec, tables, and client. Old recorded requests are client observations, not independent protocol truth. |
| T18 | New M16 word-read address discriminator; supplements T3. |

The compact JSONL retains concrete inputs for T1/T2/T9–T13 only. Other rows
above document M1 test intentions, not completed coverage. Source CASE IDs are
provenance labels only; no old promotion status is carried forward.

## Dropped or deferred assets

Do not migrate `scripts/`, evidence, `M*_PROGRESS` documents, governance fields,
old server internals, snapshot/version APIs, TOML configuration, metrics,
benchmark/release workflows, or bulk fuzz permutations. Snapshot/seed atomicity
CASE-0017/0023/0024/0104/0105 is not a wire-visible M1 requirement. Legacy
remote-operation rejection, ASCII rejection, and 4E rejection are not permanent
capabilities: control, ASCII, and 4E arrive at M5, M3, and M4 respectively.
Fault injection is deferred to M7; virtual-clock/replay features are not in v2.
Malformed framing and disconnect/timeout details will be written with the M1
transport tests, without copying the old harness.

The compatibility module's environment-variable skip, capture writer, server
fixture, evidence output, and duplicate CASE parametrization are dropped.
M1 will use a real client, localhost, port 0, and deterministic cleanup.
Fixture labels follow DESIGN: `client-compat` for client behavior,
`manual-derived` for independent hand-authored vectors, with memory-based
manual claims marked `unverified`. No fixture is labelled a real PLC capture.

## Oracle and current environment

The PyPI 0.3.0 wheel SHA256 is recorded in `tests/oracle_pin.txt`, matching the
archived pin and the published
[PyPI release metadata](https://pypi.org/pypi/pymcprotocol/0.3.0/json).
The version test fails when the distribution is absent. If the wheel is kept
at `.venv/oracle/`, the test checks its hash and compares installed package
Python files to the wheel. Tests do not access the network.

During this M0 implementation, the local `.venv` was created with the installed
`virtualenv` because the supplied Python lacks stdlib `venv`. Shell access to
PyPI is blocked (disabled package index and an unavailable proxy). Neither
pytest nor pymcprotocol could be installed, so pytest validation is blocked.
The web tool could read PyPI metadata and upstream `mcprotocolconst.py`;
the device table copies that upstream file, but comparison with the installed
0.3.0 wheel remains pending. No substitute client or fabricated passing result
is used. The tables cover M1 devices plus the other hex-base families; later
device families and per-profile capabilities remain later milestone work.

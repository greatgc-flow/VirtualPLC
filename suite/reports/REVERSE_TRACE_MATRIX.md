# Requirements ↔ Cases — generated reverse crosswalk

SSOT: `suite/catalog/test_cases.jsonl`. 상태: **설계 연결 관계만 검증**, 실제 서버 TDD 미실행.

| Requirement | Phase | Component | Linked cases | Live wired | Outcome classes |
|---|---|---|---:|---:|---|
| FR-001 | P0 | transport | 6 | 1 | close_no_mutation, success |
| FR-002 | P0 | framer3e | 22 | 13 | close_no_mutation, reject_no_mutation, success |
| FR-003 | P0 | dispatcher | 15 | 7 | reject_no_mutation, success |
| FR-004 | P0 | codec3e | 17 | 7 | reject_no_mutation, success |
| FR-005 | P0 | profile | 9 | 0 | reject_no_mutation, success |
| FR-006 | P0 | memory | 22 | 15 | reject_no_mutation, success |
| FR-007 | P0 | codec3e | 22 | 15 | reject_no_mutation, success |
| FR-008 | P0 | transport | 13 | 8 | close_no_mutation, success |
| FR-009 | P0 | test_control | 4 | 0 | reject_no_mutation, success |
| FR-010 | P0 | config | 6 | 0 | reject_no_mutation, success |
| FR-011 | P0 | integration | 6 | 0 | success |
| FR-012 | P0 | framer3e | 14 | 8 | close_no_mutation |
| FR-013 | P0 | telemetry | 4 | 0 | success |
| FR-014 | P0 | validator | 21 | 14 | reject_no_mutation |
| FR-015 | P0 | codec3e | 4 | 0 | reject_no_mutation, success |
| FR-016 | P1 | faults | 3 | 0 | future_only |
| FR-017 | P1 | simulation | 2 | 0 | future_only |
| FR-018 | P2 | protocol_extra | 4 | 0 | future_only |
| NFR-001 | P0 | memory | 3 | 0 | success |
| NFR-002 | P0 | transport | 6 | 0 | close_no_mutation, success |
| NFR-003 | P0 | delivery | 3 | 0 | success |
| NFR-004 | P0 | security | 2 | 0 | close_no_mutation, reject_no_mutation |
| NFR-005 | P0 | governance | 2 | 0 | success |
| NFR-006 | P0 | telemetry | 2 | 0 | success |
| NFR-007 | P0 | config | 2 | 0 | success |
| SEC-001 | P0 | security | 3 | 0 | close_no_mutation, reject_no_mutation |
| SEC-002 | P0 | security | 4 | 1 | close_no_mutation, reject_no_mutation |
| SEC-003 | P0 | telemetry | 3 | 0 | close_no_mutation, success |
| SEC-004 | P0 | framer3e | 5 | 2 | close_no_mutation, reject_no_mutation |
| OPS-001 | P0 | transport | 3 | 0 | success |
| OPS-002 | P0 | telemetry | 4 | 0 | success |
| OPS-003 | P0 | delivery | 3 | 0 | success |
| OPS-004 | P0 | memory | 3 | 0 | success |
| GOV-001 | P0 | governance | 3 | 0 | reject_no_mutation, success |
| GOV-002 | P0 | governance | 3 | 0 | reject_no_mutation, success |
| GOV-003 | P0 | governance | 3 | 0 | reject_no_mutation, success |
| GOV-004 | P0 | governance | 3 | 0 | success |

## Risks → test cases

| Risk | Severity | CASE count | Trace examples |
|---|---|---:|---|
| RK01 | HIGH | 28 | CASE-0006, CASE-0007, CASE-0008, CASE-0012, CASE-0013, CASE-0014, CASE-0040 |
| RK02 | HIGH | 34 | CASE-0018, CASE-0019, CASE-0020, CASE-0034, CASE-0035, CASE-0036, CASE-0037 |
| RK03 | HIGH | 6 | CASE-0027, CASE-0028, CASE-0029, CASE-0109, CASE-0110, CASE-0111 |
| RK04 | HIGH | 17 | CASE-0009, CASE-0010, CASE-0011, CASE-0063, CASE-0082, CASE-0083, CASE-0084 |
| RK05 | HIGH | 54 | CASE-0015, CASE-0016, CASE-0017, CASE-0023, CASE-0024, CASE-0034, CASE-0035 |
| RK06 | HIGH | 43 | CASE-0003, CASE-0004, CASE-0005, CASE-0030, CASE-0031, CASE-0042, CASE-0043 |
| RK07 | HIGH | 3 | CASE-0038, CASE-0198, CASE-0199 |
| RK08 | CRITICAL | 17 | CASE-0001, CASE-0002, CASE-0045, CASE-0049, CASE-0050, CASE-0070, CASE-0071 |
| RK09 | MEDIUM | 3 | CASE-0059, CASE-0154, CASE-0155 |
| RK10 | MEDIUM | 3 | CASE-0057, CASE-0150, CASE-0151 |
| RK11 | MEDIUM | 17 | CASE-0025, CASE-0026, CASE-0041, CASE-0044, CASE-0048, CASE-0055, CASE-0065 |
| RK12 | HIGH | 7 | CASE-0032, CASE-0033, CASE-0051, CASE-0115, CASE-0116, CASE-0138, CASE-0139 |
| RK13 | HIGH | 9 | CASE-0012, CASE-0013, CASE-0014, CASE-0088, CASE-0089, CASE-0090, CASE-0091 |
| RK14 | MEDIUM | 12 | CASE-0046, CASE-0054, CASE-0058, CASE-0060, CASE-0069, CASE-0131, CASE-0144 |
| RK15 | MEDIUM | 10 | CASE-0021, CASE-0022, CASE-0101, CASE-0102, CASE-0103, CASE-0172, CASE-0173 |

## Primary domain → outcome distribution

| Domain | Success | Decoded reject | Frame close | Deferred |
|---|---:|---:|---:|---:|
| domain | 31 | 18 | 0 | 0 |
| end_to_end | 20 | 0 | 1 | 0 |
| governance | 16 | 3 | 0 | 0 |
| performance | 2 | 0 | 0 | 0 |
| platform | 3 | 0 | 0 | 0 |
| scenario | 0 | 0 | 0 | 5 |
| security | 5 | 6 | 12 | 0 |
| transport | 9 | 0 | 14 | 0 |
| wire | 25 | 31 | 3 | 4 |

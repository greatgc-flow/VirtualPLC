# 종/횡 추적 점검 — 기계 분석 리포트

## 정량 분포(기능/비기능/안전/운영/거버넌스)

| Requirement partition | P0 | P1 | P2 | total |
|---|---:|---:|---:|---:|
| FR | 15 | 2 | 1 | 18 |
| NFR | 7 | 0 | 0 | 7 |
| SEC | 4 | 0 | 0 | 4 |
| OPS | 4 | 0 | 0 | 4 |
| GOV | 4 | 0 | 0 | 4 |

## Reverse trace (요구→테스트→gate→risk)

| Req | Owner | Phase | Tests | Gate | Risk |
|---|---|---|---:|---|---|
| FR-001 | transport | P0 | 2 | G2 | RK08 |
| FR-002 | framer3e | P0 | 4 | G1 | RK06 |
| FR-003 | dispatcher | P0 | 4 | G1 | RK01 |
| FR-004 | codec3e | P0 | 4 | G1 | RK04 |
| FR-005 | profile | P0 | 3 | G0-E | RK01;RK13 |
| FR-006 | memory | P0 | 3 | G1 | RK05 |
| FR-007 | codec3e | P0 | 4 | G0-E | RK02 |
| FR-008 | transport | P0 | 2 | G2 | RK15 |
| FR-009 | test_control | P0 | 2 | G1 | RK05 |
| FR-010 | config | P0 | 3 | G2 | RK11 |
| FR-011 | integration | P0 | 3 | G0-C | RK03 |
| FR-012 | framer3e | P0 | 3 | G3 | RK06 |
| FR-013 | telemetry | P0 | 2 | G3 | RK12 |
| FR-014 | validator | P0 | 3 | G1 | RK05;RK02 |
| FR-015 | codec3e | P0 | 2 | G1 | RK02 |
| FR-016 | faults | P1 | 1 | G5 | RK07 |
| FR-017 | simulation | P1 | 1 | G5 | RK05 |
| FR-018 | protocol_extra | P2 | 1 | G5 | RK01 |
| NFR-001 | memory | P0 | 1 | G1 | RK11 |
| NFR-002 | transport | P0 | 3 | G3 | RK06 |
| NFR-003 | delivery | P0 | 1 | G3 | RK11 |
| NFR-004 | security | P0 | 1 | G3 | RK08 |
| NFR-005 | governance | P0 | 1 | DG0 | RK14 |
| NFR-006 | telemetry | P0 | 1 | G3 | RK06 |
| NFR-007 | config | P0 | 1 | G3 | RK11 |
| SEC-001 | security | P0 | 1 | G3 | RK08 |
| SEC-002 | security | P0 | 1 | G3 | RK08 |
| SEC-003 | telemetry | P0 | 1 | G3 | RK12 |
| SEC-004 | framer3e | P0 | 1 | G3 | RK06 |
| OPS-001 | transport | P0 | 1 | G2 | RK06 |
| OPS-002 | telemetry | P0 | 2 | G3 | RK14 |
| OPS-003 | delivery | P0 | 1 | G4 | RK11 |
| OPS-004 | memory | P0 | 1 | G2 | RK05 |
| GOV-001 | governance | P0 | 1 | G4 | RK10 |
| GOV-002 | governance | P0 | 1 | G4 | RK14 |
| GOV-003 | governance | P0 | 1 | DG0 | RK09 |
| GOV-004 | governance | P0 | 1 | G4 | RK14 |

## 해당 리포트가 의미하지 않는 것
모든 P0 요구에서 적어도 하나의 테스트 **명세**가 연결되었다는 뜻. 테스트 실행/green/client compatibility/real PLC validation을 의미하지 않음.


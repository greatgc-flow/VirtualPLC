# 요구사항과 제외 범위 — 역할·층위·생애주기별 MECE

정본: `../machine/requirements.csv`. 요구 ID를 임의로 텍스트 복제하지 않고 테스트/게이트에서 참조.

## 시스템 경계
```
Authorized test client (pymcprotocol / CIM / MES)
        | 3E Binary TCP 127.0.0.1:15000
 [TCP] -> [Incremental Framer] -> [3E Decode] -> [Command Validator]
           -> [Profile] -> [Memory Transaction] -> [Response Serializer]
                                             \-> [Structured Telemetry]
 [local Python fixture: reset/seed/snapshot] -> [Memory Transaction]
```
서비스는 PLC 실제 보증 대상이 아닌 **독립된 가상 대상**이다. 다중 Client는 동일 가상 상태를 공유한다.

## MVP P0 / Next P1 / Extension P2 엄격 구분
- **P0:** 서버 TCP/3E Binary, D word 0401/1401, M bit 0401/1401, 명확한 오류 응답, 결정론적 메모리, multi-client, 제어용 Python fixture, 관찰/설정/자원 제한, 테스트 문서.
- **P1:** deterministic scenario engine, fault injection (전/후 commit), 독립 보조 클라이언트, high-load 추세 비교, M word 접근이 실사용에 필요할 경우.
- **P2:** 4E Serial, ASCII, 3E UDP, X/Y/W/R/B 및 고급 명령, REST UI, PLC logic/ladder simulation. 실제 제어 명령은 명시적인 요청/안전 심사 없이는 계속 비범위.
- **비기능 P0:** 범위·자원 통제, 재현성, 운영 분리, 성능 baseline 기록, Windows/Linux 보증은 향후 실제 CI 게이트 통과 이후에만.

## 지원 매트릭스(설계 약속)
| frame | transport | command/subcommand | device | unit | status |
|---|---|---|---|---|---|
| 3E Binary | TCP | 0401 / 0000 | D | word | P0 |
| 3E Binary | TCP | 1401 / 0000 | D | word | P0 |
| 3E Binary | TCP | 0401 / 0001 | M | bit | P0 |
| 3E Binary | TCP | 1401 / 0001 | M | bit | P0 |
| 3E Binary | TCP | 0401/1401 / 0000 | M | 16-bit word | NOT_IN_P0 |
| 3E Binary | TCP | 0401/1401 | X/Y/R/W/B | — | NOT_IN_P0 |
| 3E Binary | TCP | 0403/1402/0101 | any | — | NOT_IN_P0 |
| 4E/ASCII/UDP | any | any | any | — | NOT_IN_P0 |

## 요구 실효성
각 ID는 측정 가능한 판정 조건과 소유 계층, 테스트 ID, Gate, 위험(없으면 `NONE`)를 갖는다. 단, P1/P2 요구사항은 변경 신청 승인 전까지 P0 커버리지를 낮추지 않는다. P0 테스트는 Red-Green-Refactor로 실행 증거를 남긴다. 운영/문서/GOV 요구는 정적 CI 계약 검증 및 수동 운영 수용으로 검증한다.

## 성능 수치 가이드
성능 SLO는 현실적인 CI/로컬 하드웨어 baseline에 따라 확정한다. '1,000 word/16 clients'는 **벤치마크 수집 항목**이고 사양 보증 목표가 아님. latency P50/P95/P99, socket close, 서버 RSS, 통과율을 환경식별자와 함께 기록한다.

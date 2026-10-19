# 재귀적 MECE — 상·하 / 종·횡 / 순환형 검증

## 1. 분류의 직교 축
| 축 | 파티션(서로 다른 목적) | 완결성 판정 |
|---|---|---|
| 종(생애주기) | 근거 → 요구 → ADR → 인터페이스/모델 → 계약 테스트 → 구현 → 운영·관측 → 변화관리 | 각 단계는 선행 입력과 후행 결과 참조를 가진다 |
| 횡(기술 책임) | transport / framing / codec / validation / profile / state / controller / telemetry / governance | 소유 모듈 하나, 경계/인터페이스만 교차 |
| 실패/정상 상태 | 정상 / 해독 후 거부 / framing fatal / socket loss / resource limit / ambiguous post-commit | 각 사건에 상태효과·응답·로그·테스트가 있다 |
| 출시 단계 | P0 / P1 / P2 / EXCLUDED | P0만 필수 Gate, P1+는 승인 통해 이동 |
| 근거 등급 | OFFICIAL / CLIENT_CAPTURE / DERIVED / PROFILE_ASSUMPTION / UNKNOWN | UNKNOWN은 G2 호환성 주장에 사용 불가 |
| 요구분류 | FR / NFR / SEC / OPS / GOV | 상호 다른 수용기준·담당 역할·시험 존재 |

※ 'MECE'는 현실 모든 PLC 기능 망라가 아니라 **선언한 MVP와 피드백 관리 경계 안에서 무중복·무누락**이라는 의미. 임의의 장치/명령이 외부에서 새로 발견되면 P1 또는 P2로 분류해 경계 변경 심사.

## 2. 참조 무결성·쌍방 추적
단일 기준: `requirements.csv`(ID, owner component, sourceIDs, riskIDs, gate) ← `test_matrix.csv`(req_ids, oracle) ← `gates.json` ← `risks.csv` ← `sources.json`.
정적 검증에서 **every P0 requirement ≥1 test**, every test req IDs exist, every source/risk/gate ref exists, no duplicate IDs, all wire fixtures valid, manifest exact. 반대 방향으로 각 test에서 `req_id→owner→source→risk→gate`를 탐색할 수 있다.

## 3. Closed loop — 트리거부터 재귀적 품질피드백까지
```
[SOURCE UPDATE / DEFECT / TEST FAIL / METRIC DRIFT / NEW CLIENT]
       ↓ (1. 발견: 이슈 ID 생성, severity, raw 증거 SHA)
[CLASSIFY: source/functional/nonfunctional/security/ops/profile + owner]
       ↓ (2. 영향 분석: affected req/test/ADR, scope P0/P1/P2)
[CHANGE PROPOSAL: ADR, acceptance oracle & risk revision]
       ↓ (3. Red first: failing regression or static design check)
[IMPLEMENTATION/REFACTOR: boundary-preserving code + test]
       ↓ (4. gate evidence actual PASS + review / reject HOLD)
[RELEASE TAG + support matrix + reversible change]
       ↓ (5. monitor: incident, metrics, client feedback]
[CHECK AGAINST ACCEPTANCE + compare baseline] ───────┐
       ├─ drift/regression → new issue (1)  <───────────┘
       └─ stable → archive evidence; next review trigger
```
- 담당 역할: Domain owner(프로토콜/메모리), QA owner(test oracle), Safety owner(security), Maintainer(gate approval). 실제 개인 미배정 상태이며 다음 차수에서 합의.
- 모든 이슈에는 `trigger, evidence SHA, scope, root cause, linked req, linked tests, decision, fix version, observed metrics, closure rationale`를 남긴다.
- SLA 숫자는 사용자 환경에 맞춰 별도 계약; **P0 compatibility/security regression = 즉시 gate HOLD**, 미검증 source drift는 다음 정기 설계 재검토 의무.
- 모니터 목표는 숫자 목표뿐 아니라 '위험이 되돌아오는 경로가 누락되지 않음'이다. 최신 타당성 소실 시 CLOSED 이슈를 다시 OPEN할 수 있다.

## 4. 변경 유형별 재귀 검증 규칙
- 새 device → device registry/addr radix → protocol request/response fixture → test matrix → risks → supported matrix → version.
- 새 frame 4E → header, serial echo, connection association, fault model, extra error payload, negative parser, cross-client capture를 3E와 독립 테스트.
- 새 fault mode → 부작용(commit 여부), 시드/리플레이, logging privacy, risk assessment, unit+integration test.
- 새 client → pinned version + raw sample → diff vector → requirement mapping → gate & support matrix.

## 5. 기계적/사람 검토가 각각 답하는 질문
정적 `validate_design.py`: 존재·고유·해시·스키마·링크 커버리지·기초 HEX 길이·비트 패킹의 내부 모순.
사람/G0: 본 매뉴얼과 장치 매뉴얼의 error-map 정합성, 실제 클라이언트 바이트/에러 핸들링, 외부 저작권, 네트워크 안전, 판단 근거 누락.
TDD/runtime: 실제 버그 여부, 런타임 레이스·자원 고갈·플랫폼 차이, 성능 추이. 세 수준을 서로 대체하지 않음.

# 반복 점검 이력 / 판정의 한계

## Round 1 — 구버전 의미·기술 정확도 검토
원본 ZIP 15 entries를 열고 본문/requirements/test mapping 전체 확인. 발견 `DEF-01..15`. 공식 SLMP manual(3E layout, D/M device code, bit nibble, failed response detail)을 교차 대조하고 '미검증'과 '확정'을 분리. 결과: 문서 구조 재설계 필요.

## Round 2 — 상하 계층 및 좌우 경계 재검토
근거 → ADR → 요구 → 경계 → 인터페이스 → frame → state → test → gate → 운영 루프를 연결. 모듈별 단일 책임, 변경 유형별 영향을 체크, M word/4E/ASCII/REMOTE/REST가 P0 범위를 오염시키지 않는지 확인. machine SSOT 및 source/risk/gate ID 외래키를 추가.

## Round 3 — 구조적 무결성·역방향 추적 및 독립적 모순 체크
`validate_design.py`로 구조·유일성·참조·P0 커버리지·HEX 길이·bit packing·패키지 SHA-256을 자동 검증. STATIC_PASS(검사 결과 `review/structural_validation.json` 참고), 원본 미검증 항목은 원칙적으로 `OPEN` 유지. 실제 TDD·상호운용성 테스트 수행하지 않음.

## Round 4 — 감독/피드백 경로 자체 검증
폐루프 이벤트 스키마와 CLOSED/REOPENED 분기 검증 계약을 추가했다. 정적 검사기에도 의도적으로 **고아 참조, 불일치 HEX 길이, P0 테스트 누락**을 주입한 임시 사본 3개를 실행하여 모두 FAIL_STATIC으로 검출됨을 확인했다(`review/negative_validator_tests.json`). 본 검사기 결함 주입은 실제 PLC 서버 소프트웨어/TDD 테스트가 아니다.

## 최종 다면 판단
- **PASS (범위 한정):** 문서 재귀 계층, 요구/테스트/리스크/게이트 추적, 기본 프레임·bit data 설계상 자기모순/CRC/해시 검사, 폐루프 변경 계약.
- **HOLD (객관적):** 특정 PLC 모델별 상세 end-code·제한값, 실제 pymcprotocol Client 생성 packet 비교, CIM/MES 실제 명령 커버리지. 위 검증 전 '완벽한 PLC 호환'으로 발표할 수 없음.
- **NOT RUN:** 개발 코드, TDD tests, 서버 기동, CIM/MES 접속, 현장/운영 적합성. 스크립트의 PASS는 이 항목을 대체하지 않는다.

`PERFECT`는 검증 가능 범위를 넘는 주장이라 사용하지 않는다. 이 패키지는 TDD **직전** 전달물로 설계 정합성을 엄격 관리하지만, 다음 단계의 실제 테스트에서 새로운 결함을 찾아 다시 유입시키도록 작성하였다.

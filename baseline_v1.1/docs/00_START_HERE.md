# MC/SLMP Virtual PLC — 재귀적 MECE 설계 통합본 v1.1
2026-10-19 | 목표 상태: **DESIGN-BASELINE VALIDATED / G0 PARTIAL / TDD NOT STARTED**

## 목적과 경계
기존 pymcprotocol 및 CIM/MES 드라이버의 접속 대상이 되는 **가상 PLC TCP Server**를 순수 Python으로 개발하기 위한 TDD 직전 설계다. Mitsubishi PLC 전체/래더/실 I/O 에뮬레이션이 아니며 현장용 장비 제어기가 아니다. 성공/실패 가능한 통신 행태, 가상 메모리, 결정론적 시나리오를 제공한다.

- **MVP 동결**: 3E Binary/TCP, D 16-bit 워드 읽기·쓰기, M 1-bit 읽기·쓰기, 0401/1401, Q-호환 3바이트 주소 형태, 동시 연결, 메모리 일관성, localhost 통신, in-process 테스트 제어.
- **의도적 제외**: 4E, ASCII, 3E UDP, M의 16-bit 워드 접근, X/Y/W/R/B, 0403/1402, 래더/스캔, REMOTE RUN/STOP, 외부 REST 관리자, 실제 PLC 접근. 이 항목은 명시된 확장 게이트 이전에 구현 금지.
- **Python 3.11+ / stdlib-first**: 설정은 TOML(`tomllib`), 네트워크 `asyncio`, 로그 `logging`, 개발 시 테스트 도구는 별도. 서버 런타임에 YAML/웹 프레임워크 필수 의존 없음.
- **기본 실행**: `127.0.0.1:15000`, 가상 디바이스 D0..9999/M0..9999, 초기값 0, 오류 주입 OFF, 자동 시나리오 OFF. 외부 IP 바인딩/현장망은 기본 정책에서 거절.

## 문서 내비게이션 — 단일 진입점
1. `01_BASELINE_AUDIT.md`: 이전 설계의 누락/중복/모순 → 수정 근거
2. `02_RESEARCH_ADR.md`: 공식 문서/코드 레퍼런스와 ADR·재사용 판단
3. `03_REQUIREMENTS_BOUNDARIES.md`: 범위와 독립적인 요구사항 축
4. `04_ARCHITECTURE_INTERFACES.md`: 모듈, 호출 계약, 동시성/결함 모델
5. `05_PROTOCOL_WIRE_CONTRACT.md`: 고정 3E byte, 에러 형식과 골든 상태
6. `06_MEMORY_SCENARIO_CONFIG.md`: 상태모델/주소/설정/시나리오
7. `07_TDD_TEST_ORACLES.md`: Red-Green-Refactor 이전 테스트 상세명세
8. `08_SECURITY_OPERATIONS.md`: 오남용 방지, 회복성, 운영 정책
9. `09_TRACEABILITY_FEEDBACK.md`: 종/횡 매트릭스와 양방향 변경 루프
10. `10_GATES_RISKS_OPEN_ITEMS.md`: 남은 G0 항목과 객관적 Go/No-go
11. `11_CHANGELOG_ITERATIVE_AUDIT.md`: 3회 재귀 검토/잔여 제약
12. `12_NEXT_CHAT_TDD_PROMPT.md`: 그대로 복사하여 다음 TDD 진행
13. `../machine/*.csv|json`: 정규화된 SSOT (문서와 불일치하면 SSOT를 고친 뒤 문서 재생성)
14. `../scripts/validate_design.py`: 구현 없이 기계적 참조·커버리지·골든·해시 검사

## 상태를 혼동하지 않기 위한 규칙
- **정적 설계 검증 PASS ≠ 서버 테스트 PASS.** 설계 검증 스크립트는 파일·외래키·필수필드·의존관계와 정적 패킷 불변식만 평가한다.
- 별도 TDD 작업 전 `tests/*.py`·`src/*.py` 서버 구현/테스트는 이 패키지에 존재하지 않는다.
- 공식 3E 프레임 구조·D/M 코드·니블 순서 등은 제조사 SLMP Reference Manual과 대조했다. 모델별 에러 코드/상한, `pymcprotocol` wire 실제 캡처는 **G0 OPEN**으로 격리했다.
- 아래 문서의 프로파일 `generic-q-3e`는 **합의된 테스트 프로파일**이지 Mitsubishi 전 모델에 대한 보증이 아니다.

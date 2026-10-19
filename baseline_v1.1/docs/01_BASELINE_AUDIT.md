# 기존 v1.0 설계 독립 검토 / 결함 보고

검사 대상: `MC_SLMP_Virtual_PLC_TDD_Ready_Design_20261019.zip` (15 entries, ZIP CRC 확인). 원본은 읽기만 수행; 개정판은 별도 ZIP. 검토 대상과 결과 요약은 `review/original_inventory.json` 및 `review/iterative_audit.json`.

| 검출 결함 ID | 문제 및 영향 | 조치 | 분류 |
|---|---|---|---|
| DEF-01 | NFR-001~006이 요구 SSOT/테스트 추적표에 없어 '100% 추적'은 미충족 | NFR/SEC/OPS/GOV 포함 단일 요구 원장 재구성 및 전체 테스트 커버리지 검사 | 누락 |
| DEF-02 | 선택적 fault/scenario가 P0로 표기되어 MVP와 충돌 | In-process reset/snapshot만 P0; 지연/시나리오는 P1 | 모순 |
| DEF-03 | stdlib-first 선언과 YAML 설정 파일 예시가 충돌 | TOML 설정 채택, Python 3.11+ `tomllib` 표준화 | 모순 |
| DEF-04 | G0 OPEN인데 설계 'READY'로 기술해 외부 클라이언트 호환 PASS로 오인 위험 | `DESIGN_BASELINE_VALIDATED, G0_PARTIAL, NO_TDD` 상태 분리 | 모호 |
| DEF-05 | 오류 응답 payload (원격 오류정보 + command/subcommand) 누락 | 공식 매뉴얼 response error 레이아웃 명시. 코드별 정책은 G0 분리 | 누락 |
| DEF-06 | timeout/Drop가 '쓰기 후 commit / 응답 실패'에서 부작용을 어떻게 다룰지 빠짐 | 장애발생 단계 PRE_DISPATCH/POST_COMMIT/POST_SEND 명시, ambiguous outcome 문서화 | 누락 |
| DEF-07 | 3E request/response 흐름과 address radix, unsupported M word-unit 경계가 흐림 | command×device×subcommand matrix 및 기종 고정 프로파일 | 불명확 |
| DEF-08 | 동시성 'bank lock'만으로 원자 reset/snapshot/시나리오 vs request 일관성 보장 안 됨 | 단일 상태 직렬화 추상 연산 + 버전 스냅샷 (미래 최적화는 계약 유지) | 충돌 |
| DEF-09 | 임의 예시 골든을 제조사 샘플/실 클라이언트 캡처와 혼동 가능 | fixture 출처 등급: OFFICIAL/DERIVED/CLIENT_CAPTURE/PENDING | 검증 |
| DEF-10 | 외부 구현 사례 인용만 있고 채택 기준/라이선스/위협모델 불완전 | 대체 후보 role별 비교 및 third-party intake checklist | 누락 |
| DEF-11 | CI/배포 이후 피드백이 차기 요구 및 회귀시험으로 다시 연결되지 않음 | 트리거→분류→추적→변경→검증→운영→재감시 Closed Loop 정의 | 구조 |
| DEF-12 | G0/G1 문턱, PASS 근거, 예외/승인권한 불명확 | 독립 Gate checklist, 승인/보류/위험 수용/롤백 계약 | 모호 |
| DEF-13 | 무기한 대기·slowloris·호출 과다·control 보안의 세부 방어가 약함 | 단계별 수신 timeout, 메모리 제한, backpressure, local-only control | 보안 |
| DEF-14 | 요구→소스→설계→test→risk→gate의 반대 방향 탐색 불가 | 기계 판독 가능한 외래키 원장 + validator | 추적 |
| DEF-15 | 불량 frame에 언제 닫고 언제 protocol error를 돌려줄지 미분리 | 프레이밍 vs decoded-validation 오류 등급과 응답 규칙 | 중복·모호 |

`DEF`는 설계결함 식별자이며 코드 버그/테스트 실패를 뜻하지 않는다. 세 차례 검토 후 **설계문서 구조적 DEF-01..15는 문서상 보완**. 외부 실제 상호운용/모델별 공식 오류값은 아직 미증빙. 완벽/양산 적합 선언 금지.

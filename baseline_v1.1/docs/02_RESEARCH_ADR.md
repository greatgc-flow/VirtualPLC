# 근거·오픈소스 분류·설계 의사결정

## 출처 신뢰도와 동일성
- `S01`: Mitsubishi SLMP Reference Manual SH-080956ENG-M, 공식 244p. 우선 소스. Chapter 4(프레임), Chapter 5(명령/디바이스), 위험 주의사항; 문서판은 개정될 수 있으므로 PDF 경로/매뉴얼 표기 및 접근일을 함께 기록.
- `S02`: `senrust/pymcprotocol` 공식 README / Type3E API 및 내부 생성 프레임. 라이브러리 **Client**, 4E 구현은 문서상 미시험. 고정 버전과 패킷을 TDD 시작 시 캡처.
- `S03`: 독립 공개 기사 Python 3E dummy server. **Server 참고 구현**. 개인 블로그 공개 코드는 저작권 자동 포기 아님. 코드 전문 ZIP에 미포함.
- `S04`: `gomc_rest_python` REST server는 MC 클라이언트→실제 PLC 게이트웨이. 가상 MC endpoint 아님.
- `S05`: `OkitaSystemDesign/MC-Protocol` UDP MC **Client**. 서버 재사용 불가.
- `S06`: `fa-yoshinobu/plc-comm-slmp-python` 3E/4E **Client**. 독립 상호운용 비교 후보로 유용(MIT 표기), 매트릭스 확인 후 테스트 추가.
- `S07`: `s-pms/melsec_mc_net` C 기반 MC **Client**. 비교 참고. 정식 라이선스/지원 범위 재검증 후만 코드 재사용.
- `S08`: `pymcprotocol` API 문서.

## 재사용 후보 비교 (동일 축)
| 후보 | MC 요청을 수신하는 PLC Server | 메모리 에뮬레이션 | 자동 채택 | 활용 |
|---|---|---|---|---|
| 독립 Python 표준라이브러리 코어 | 목표 | 설계 | Yes | 자체 구현 주 경로 |
| GenbaPy 3E dummy | Yes (기사 기준) | Yes | No | 경계 사례/계약 레퍼런스 |
| pymcprotocol | No | No | No | 독립 주 테스트 Client |
| plc-comm-slmp-python | No | No | No | 추가 독립 테스트 Client |
| gomc_rest_python | No (MC 기준) | No | No | 이름 착각 방지 반례 |
| 공식 PLC 시뮬레이터 | 구성·모델마다 다름 | 별도 평가 | No | 실제 논리 시뮬레이션 필요시 조사 |

## ADR (결정 단위, 고립·상호검증)
- **ADR-01 (채택):** 서버와 `pymcprotocol` 의존성 분리. 이유: Client 기능과 Server framing 관심사 분리, 추후 다른 클라이언트 호환성 입증.
- **ADR-02 (채택):** 3E Binary TCP만 P0; 4E/ASCII는 각 codec plugin으로 P2. 이유: 오류면적 최소화. Gate: 새 frame마다 독립 source/fixture/test/compat.
- **ADR-03 (채택):** `generic-q-3e`라는 테스트용 프로파일. 포맷/장치/주소/접근/상한은 프로파일 SSOT에 위치; 모델 사실로 일반화하지 않음.
- **ADR-04 (채택):** 메모리 단일 logical transaction layer. 빠른 구현보다 read/write/reset/snapshot 원자성 증명이 중요. 멀티 bank 락은 향후 ADR.
- **ADR-05 (채택):** 설정은 TOML, 메모리·시나리오 인쇄물은 JSON, 서버 async 표준 라이브러리. pytest 등은 dev-extra만.
- **ADR-06 (채택):** 네트워크 endpoint allowlist loopback 강제. 운영/생산망에 사용하는 기능은 설계 대상 밖.
- **ADR-07 (채택):** 장애 시뮬레이션 P1 opt-in; fault 단계/commit 부작용 정합성을 계약으로 규정.
- **ADR-08 (채택):** 계약에는 공식·추론·기종가정·실측을 각각 표시하고, 미검증 수치를 기본 성공으로 대체 금지.
- **ADR-09 (보류):** M word-unit 접근, X/Y, 4E, ASCII, REST Control, PLC CPU type `0101`. 증거/고객 요구와 별도 gate로 판단.

## 외부 코드 유입 체크리스트
출처 pinned commit/tag → 실제 LICENSE→ third-party notice → 의존성/보안 검토→동작 재현→ protocol matrix 비교→ 채택 ADR → 테스트·회귀에 반영. 미충족 시 **아이디어만 독자 구현**, 소스 복제 금지. 공식 매뉴얼은 다운로드 링크로만 제공.

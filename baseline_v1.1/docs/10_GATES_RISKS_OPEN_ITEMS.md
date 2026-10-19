# GO/NO-GO Gate, 미결 입력, 리스크 정본

## Gate 상태(정본: `../machine/gates.json`)
| Gate | 의미 | 현재 | 판정 조건 |
|---|---|---|---|
| DG0 | 설계 구조/상호 추적 무결성 | PASS_STATIC | 기계 검사/3차 재귀검토, 사용자 승인 전제 없음 |
| G0-F | 프레임 핵심 공식 교차검토 | PASS_DESK | 3E 기본 헤더 길이/bit-code/wire sample 공식 문서 대조(종이 위) |
| G0-E | 미지원/범위 오류 end-code + payload 확정 | OPEN | 대상 Q 모델/매뉴얼 정합 매핑 + client 오류 동작 + negative capture |
| G0-C | 실제 pinned pymcprotocol 송신 byte 대조 | OPEN | 로컬 클라이언트 요청 raw vs official/derived fixtures |
| G1 | 순수 메모리·codec Red/Green | NOT_RUN | P0 unit/contract tests green + 실제 logs |
| G2 | 서로 다른 프로세스 TCP/Client 호환 | NOT_RUN | client pinned actual integration pass |
| G3 | 보안/성능·Windows/Linux | NOT_RUN | bounded memory/time/EOF/slowloris tests, platform traces |
| G4 | 릴리즈 승인/회귀 폐루프 | NOT_RUN | 요구+테스트+관찰+변경 반영, unsupported 명시, signoff |

**착수 판단:** 구조 설계는 TDD Red 작성 가능. G0-E/G0-C 해결 전에는 실제 외부 클라이언트와 error-compatible 서버 완료/제품지원 PASS 선언 금지. P1/P2 확장은 G4 별도 승인.

## 중요한 OPEN ITEM과 해결방법
- **OPEN-01** 해당 기종(모델/firmware/module) 및 MC/SLMP 포맷의 대표 설정이 현재 없음. 기본 `generic-q-3e`로 sandbox 개발, 모델별 구현 호환 선언 금지.
- **OPEN-02** 상세 에러 end-code mapping은 SLMP general manual만으로 모델 차이가 남음. 공식 제품별 문서 + pinned client 에러 판독 기준으로 정함.
- **OPEN-03** 공식 단일 기종 command별 max points/size 및 memory bank 정책. 설정 상한의 교차 검증 필요.
- **OPEN-04** 로컬에서 실제 `pymcprotocol.Type3E`가 만드는 request raw 캡처 없음. fixture는 아직 일부 derived.
- **OPEN-05** 실제 CIM/MES 기존 드라이버 사용 명령/address 목록 부재. 범위 결정은 MVP 우선, 추가 기능은 별도 요구 변경.
- **OPEN-06** 테스트 담당 / 유지보수 담당 / release 승인자 미지정(역할만 정의). 진행시 역할 배정.

## 위험 우선순위
정본 `../machine/risks.csv` (owner/likelihood/impact/trigger/mitigation/retest/monitor). Critical: 실제 제어망 오접속, 중복 write 부작용, 오류 프레임 클라이언트 파싱 실패, 무제한 request queue.

## 리스크 수용 규칙
`OPEN-HIGH`인 프로토콜/산업안전 영향 문제는 릴리즈 G4 GO 불가. `P0` 범위의 미해결 불변식은 문서에 정확히 UNKNOWN으로 표시하고 프로파일 기능으로 노출 금지. 회피/보류는 사유/재검증 트리거/승인자를 기록, 무기한 '완벽' 주장 방지.

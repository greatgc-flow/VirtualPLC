# 테스트 범위와 오라클 — 정상·경계·예외·회복 구분

## 분할 규칙
**유효 입력**=정상 단일/연속/최소/최대/다중; **유효 경계**=D0,D9999,M0,M9999, 0x0000/0xFFFF, M 홀수·짝수 비트; **해독 후 거부**=명령/주소/개수/서브명령/페이로드/route 불지원, 실패 응답 + 메모리 무변경; **fatal frame**=헤더/길이/EOF 파괴, 무응답 close + 메모리 무변경; **전송 장애**=RST/FIN/slow sender/reader/resource overflow, bounded close 또는 정의된 회복; **상태 경합**=read/write/reset 다중 클라이언트 직렬화, torn state 불허; **운영/보안**=loopback 제한/비밀 redaction/프로파일 유효성/Restart volatile; **확장·보류**=P1/P2 명시 분리.

## 테스트 오라클 엄격 규칙
- read 성공은 응답 end_code=0000, 정확한 크기, 원래 write 값과 모든 바이트 일치.
- write 성공은 응답 end_code=0000, data 빈 문자열 + 후속 readback.
- decoded invalid의 에러는 **0이 아닌 end_code**, 길이 일치, 오류 주체 5바이트 + 실패 명령 2바이트 + subcommand 2바이트, 메모리 보존. **숫자 오류코드 일치 시험은 G0-E 미확정**.
- fatal framing은 디바이스 데이터 비변경과 해당 connection close; 정상 프레임 자동 resync 금지.
- M 비트 1쌍=1바이트: 첫 bit는 상위 nibble, 두 번째 bit는 하위 nibble. 홀수 tail 하위 nibble=0. strict-profile nonzero odd tail reject(제조사 호환성은 별도 검증).
- 실패 원자성은 후속 readback과 memory version으로 검사할 것. socket 종료만으로 'commit 안 됨' 추정 금지. **유효한 write 전체 송신 후 응답 유실**은 성공/실패가 모호하므로 자동 재실행하여 비교하지 않는다(확장 기능에서 별도 다룸).
- 테스트는 결괏값만 보지 않고 `행위/상태효과/길이/endcode/로그/자원`을 확인; 단순 `does not throw`는 수용 불가.

## 폭발적 테스트 조합을 줄이는 방법
직교 축의 완전 데카르트 곱은 불필요하고 불가능. 단일 계층 invariant는 동등 분할·경계값·결정표; 계층 간 결합은 pairwise/위험 기반 3-way; race/fuzz는 seed를 고정하고 회귀 시 최소 반례를 영속 저장한다. 모든 조합 생략은 risk/impact/owner/gate를 기록한다. 실험 시간을 늘려도 정상성 정의를 바꾸지 않는다.

## P0 예외 실패효과 결정표
| 예외 클래스 | 프레임 송신 | 응답 예상 | 메모리 효과 | 부가 검증 |
|---|---|---|---|---|
| Unsupported cmd/sub/device | 완전·구문 정상 | valid 3E error, nonzero | 없음 | 원 cmd/sub·length 일치 |
| Invalid count/range/value | 완전·해독 가능 | valid 3E error, nonzero | 없음 | all-or-nothing |
| Invalid D/M payload/nibble | 완전·해독 가능 | valid 3E error, nonzero | 없음 | no partial commit |
| Bad subheader/over-size | 프레이밍 치명오류 | close, no response | 없음 | 메모리/cap/로그 |
| EOF mid header/body | 미완성 | close, no response | 없음 | no hang/commit |
| TCP RST | 프레임 미완성·세션 손실 | transport loss | 완료 전 write는 없음 | 서버 생존 |
| Fully received valid write then response lost | 유효·완성 | client sees ambiguity | could be committed | 절대 중복 실행 가정 금지 |
| Too many clients/slow receiver | resource saturation | policy close/reject | 기존 커밋 보존 | RSS/timeout/others alive |
| Nonloopback/remote command | safety policy | deny startup / valid error | 없음 | 현장 PLC 미접속 |

## 테스트 품질 요건
negative oracle은 **예상 실패 경로를 긍정적으로** 검사한다. 무작위 입력은 생성 규칙·seed·축소 재현·성공/실패 판정을 갖는다. 실서버가 없으면 Red/NOT_RUN이며 'skip because implementation absent'를 Release PASS로 산입하지 않는다.

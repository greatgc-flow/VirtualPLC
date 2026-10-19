# 피드백 루프 오작동에 대한 메타 검토

## 폐루프 자체를 테스트해야 한다
실패가 감지되고도 설계가 변경되지 않거나, 설계 변경은 되었지만 테스트가 추가되지 않거나, 테스트가 통과해도 운영에서 같은 문제가 재발하면 '부분 루프'다. 본 설계는 다음 6가지 필수 링크를 갖는 이슈 기록을 요구한다.

| 단계 | 입력/트리거 | 측정 가능한 출력 | 닫히지 않았을 때 |
|---|---|---|---|
| Detect | source/client/test/metric/incident | 증거 SHA·이슈 ID | 진단 불가, HOLD |
| Classify | 이슈·영향 모듈 | category, scope, severity, owner | triage HOLD |
| Decide | risk + affected requirements | ADR/change decision | 임의변경 차단 |
| Prevent | root cause | 회귀 테스트 oracle + 고정 fixture | 해결 선언 불가 |
| Verify | Red→Green + gate | 실행 증거/버전/로그 + release decision | 배포 HOLD |
| Observe | production-equivalent **isolated** test telemetry | baseline 비교, 재발 감지 | CLOSED 금지 |

정본 계약: `machine/change_event.schema.json` (JSON Schema; 아직 실제 issue record 없음). 개발 중 schema validation 추가. `CLOSED` 허용 조건은 (a) root cause, (b) linked test, (c) gate pass evidence, (d) outcome metric 확인, (e) rollback path 또는 risk acceptance 모두 충족. 그 전 상태 `OPEN` 또는 `HOLD`. 새로운 client·device·model 발견은 '새 defect' 아닌 change proposal로도 들어오고 동 루프로 처리한다.

## 선순환 루프의 실패 주입 예
- 폴더에 `unknown device code` 신규 건이 들어오면 요구/프로파일/테스트/지원표에 연결되지 않는 한 자동 CLOSED 불가.
- `pymcprotocol` 버전 업데이트 후 byte mismatch면 G0-C 재오픈, 새 fixture를 실패 oracle로 먼저 추가.
- server 메모리 사용량 증가 알림인데 test reproduction이 없다면 위험 수용(명시적 승인) 외에는 CLOSED 불가.
- G4 PASS 이후에도 새 source revision/보안 변경이 발생하면 이전 통과 근거와 새 조건의 동일성 재평가.

## 외부 데이터가 없는 현재의 적정 상태
아직 서버 코드/telemetry 미존재→ 탐지/운영 루프는 **설계상 연결**되어 있으나 **운용 중인 폐루프가 아니다**. G4 NOT_RUN 유지. 증거 없이는 완성 주장 금지.

# 선순환 피드백 루프: 진단→보완→회귀→검증→관찰→진단

1. **발견**: 설계 변이·실제 실패·client 버전 변동·소스 개정·성능 drift를 `ISSUE-ID`, 시각, 최소 재현 입력/seed/환경 fingerprint와 함께 기록.
2. **분류**: primary_domain 1개 + 계층 실패효과 + P0/P1/P2 + 안전 심각도 + 영향 requirement/risk/gate 연결. 신규 사례는 기존 사례와 input/oracle 중복 검사.
3. **Red**: 현재 실패를 재현하는 CASE를 작성/수정(고정 입력을 만들고 테스트가 원하는 이유로 실패함을 검증). 불확정 공식 사양은 quarantine gate로 남김.
4. **Green / Refactor**: 서버 구현만 최소 변경. trace 및 goldens 수정 시 공식 근거·테스트 독립성 재검토. `old CASE` 모두 재실행.
5. **Gate**: `DG0→G0-F/E/C→G1→G2→G3→G4`. P0 MUST 전체 증거 확보 전 출시 HOLD. CI 행렬은 Win/Linux·Python 지원버전별 실제 테스트로 채운다.
6. **관찰**: 정상/오류/연결차단/서버 RSS/latency p50/p95/p99/재현 seed/클라이언트 릴리스 변경 기록. 구체적인 절대 SLO는 현장 profile과 baseline 후 결정.
7. **재진입**: 같은 버그 재발, unsupported command 새 발견, client wire diff, 공식 표준 변경은 닫힌 ISSUE도 reopen하고 linked CASE·ADR·support table까지 동시 업데이트.

## 폐루프 최소 이슈 레코드
`id, trigger, found_at, source_grade, risk_ids, requirement_ids, case_ids, observed, expected, seed, minimal_bytes_sha256, root_cause, change_id, diff_review, gate_before, retest_result, gate_after, regression_monitor, closure_reason, reopen_trigger`.

## 단절 차단 정책
- orphan requirement/case/risk 원천 차단: `validate_suite.py`.
- static PASS를 real G2 PASS로 표시하면 release guard 거부: `gate_report.py` 기본 HOLD.
- 빌드 없이 `test_cases.jsonl`의 evidence를 PASS로 손수 고치면 static guard 실패.
- 실제 CI PASS를 기록할 때에는 원본 JUnit+SHA, 서버 commit, 패키지+client version, OS/time, profile 및 원본 요청 bytes 해시를 같이 남긴다.
- P1/P2 변경은 G5 승인 후 범위 확장, 그때에만 test runner 명령·상한·프로필·메모리 정책·문서·리스크 갱신.

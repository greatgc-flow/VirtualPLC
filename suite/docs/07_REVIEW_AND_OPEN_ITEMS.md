# 다층 반복 감사 — 결과 및 남은 설계/실행 간극

## Round 1 (Baseline → 새 카탈로그)
`v1.1` 전체 30파일/요구 37개/기존 TC 69건/리스크 15건을 인계했다. P0 34개 요구에 테스트 2개 이상 배정, P1/P2 조기 편입 차단.

## Round 2 (입력/출력과 예외 분할)
3E binary word/bit 요청, 홀수·짝수 비트, 마지막 주소, 짧음/큼/미지원/정상 해독 오류와 TCP framing fatal, no partial write, FIFO, 동시 클라이언트, 자원·운영·안전·버전 drift로 분류했다.

## Round 3 (실제 실행구조)
테스트 독립 3E raw helper, loopback 전용 서버 프로세스 fixture, 유효 read/write와 40개 이상 wire/integration CASE 실행구조, 도메인 메모리 어댑터 Red 테스트, 선택적 pinned pymcprotocol 스모크를 구성했다. 기존 클라이언트 raw 캡처와 숫자 error mapping은 G0 미해결임을 유지한다.

## Round 4 (종횡 추적 및 실패를 이용한 검사기 테스트)
고유 ID, 요구 ID, 원본 TC, 리스크, 범위 단계, 게이트, 결과 오라클, runner 연결성을 자동 검증한다. 검증기에 참조 끊기/ID 충돌/P2 범위누수/거짓 PASS/실행 action drift를 주입하여 오류를 찾아내는지 검사한다. 정적 검사 결과/파일 해시를 최종 패키지 무결성 기록에 포함.

## 남은 일 (TDD 진행 시 반드시 처리)
1. **G0-E** 기종별 정확한 숫자 end code, 개별 route/단말 정보 검증.
2. **G0-C** pinned pymcprotocol 버전/3E raw client-capture 검증.
3. **G1** 130개 `runtime_adapter` 카탈로그 사례를 도메인/codec/config/security 어댑터와 실제 시험 노드로 단계적으로 연결; 미연결은 NOT_RUN으로 유지. shipped `suite/tests/domain`은 메모리 불변식의 1차 선행 테스트다.
4. **G2** live 45건을 실제 구현 서버에서 테스트 및 failed-error code/payload 확인.
5. **G3** Windows/Linux actual CI, fuzz expansion, log redaction, time/resource bounds, performance baseline 측정.
6. **G4** P0 199건 실제 결과 evidence + release signoff; G0~G3 OPEN 하나라도 있으면 HOLD.

**중요**: `MECE static PASS`는 분류·추적 기준을 만족한다는 뜻이지 테스트 수트의 모든 사례가 자동 실행·통과했다는 뜻이 아니다. '완벽' 단언 대신 열려 있는 실제 검증 게이트를 공개한다.

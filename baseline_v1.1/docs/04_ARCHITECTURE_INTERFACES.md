# 모듈 설계 / 타입 계약 / 실패 매핑

## 책임의 단일성 (각 층은 바로 옆 층만 참조)
- `transport`: asyncio listener/session, connection cap/idle/read deadlines, backpressure. packet opcode 불인지.
- `framer3e`: 3E binary head+length를 증가분 수집, bounded frame, resync 하지 않음.
- `codec3e`: 정확한 header/body parsed typed message 및 serializes response. 메모리를 모름.
- `validator`: command×subcommand×device×count×length×route 정책 분리.
- `profile`: 코드·주소 진법/범위/권한, 포인트 cap. 자체 바이트 buffer를 조작하지 않음.
- `memory`: D/M 저장; `atomic(fn)`로 read/write/snapshot/reset/seed 상호 직렬화; 번호별 초기값 정의.
- `dispatcher`: 유효 명령→memory 호출→ `Success|ProtocolError`. 예외가 TCP payload로 누출되지 않음.
- `faults` (P1): PRE_DISPATCH/POST_COMMIT/PRE_SEND 단계별 정책. P0은 실행 경로에서 비활성.
- `telemetry`: typed event + rate-limit. 값/비밀번호/사용자 원본 생략.
- `test_control`: TCP PLC 포트와 독립된 in-process fixture; local-only.

## typed interfaces (pseudo type, 구현 아님)
```
FrameFeed.feed(chunk: bytes) -> list[Frame] | FrameFatal
Decode3E.parse(frame: Frame) -> Request | DecodedFault
Validate.check(req, profile) -> ValidatedCommand | ProtocolFault
Memory.atomic(fn: Callable[MutableView, Result]) -> Result
Dispatch(req) -> Completed(data) | Rejected(end_code, error_details)
Encode3E.response(route, end_code, body) -> bytes
Control.seed(values) / reset(seed) / snapshot() -> {version, D, M}
```
`FrameFatal`(신뢰할 헤더 없거나 max_frame 초과) → 연결 종료, 무응답. `DecodedFault`(의미 해석 가능한 프레임이나 미지원 cmd/device) → 프로파일 기반 **실제 호환 end-code + error details**. 임의 코드가 정해져 있지 않은 경우 G0 완료 전 '지원' 선언 금지.

## transport/session 계약
1. TCP는 byte stream. read(1)/coalesced/fragmented 허용; 길이 조건을 먼저 검증한 후 payload 할당.
2. 같은 socket 요청은 **인입 순서대로 처리/응답**; 다중 연결간 총순서나 공정성은 보장하지 않지만 모든 memory op는 원자적으로 직렬화.
3. half-close(EOF): 완전 프레임 처리 후 정상 마감; 미완성은 프레이밍 경고와 종료. RST/쓰기실패로 memory undo하지 않음.
4. 동시 요청, shutdown/reset/snapshot 경합 시 단일 atomic 결과. snapshot은 version+전체 banks가 **같은 논리 시점**.
5. socket close 후 pending request cancellation은 memory commit 직전만 취소 가능. commit 이후 응답 취소는 확정 write가 될 수 있으므로 독립 클라이언트 재조회 필요.
6. 비정상·의도적 fault 주입 시 오류 주입 단계·요청 번호·실제 부작용을 기록, `REPLAY` 입력으로 보관(기본은 비활성).

## sequence 예시
정상 write: RECEIVE→VALIDATE→ATOMIC_COMMIT(version+1)→ENCODE_SUCCESS→SEND→LOG.
범위 오류: RECEIVE→VALIDATE_REJECT→ENCODE_COMPAT_ERROR→SEND→LOG; 메모리 변경=0.
장애 POST_COMMIT_DROP (P1): RECEIVE→VALIDATE→COMMIT→DROP→LOG(`unknown_to_client`); 클라이언트는 write 미실행으로 단정 금지.

## 프로젝트 경로(권고만, 패키지에 구현 코드 없음)
`src/virtual_plc/{transport,framer3e,codec3e,profile,validate,memory,dispatch,test_control,telemetry}.py`
`tests/{unit,wire,integration,property,security,performance,docs}/`
`config/default.toml`, `fixtures/wire_vectors.json`, `docs/*`.

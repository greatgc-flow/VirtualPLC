# 메모리·초기값·시나리오·설정 모델

## 메모리 SSOT
D: 10,000개의 unsigned 16-bit `0..65535`, 디바이스 번호 0..9999.
M: 10,000개의 boolean `false/true`, 디바이스 번호 0..9999.
각 주소는 고유 bank 공간. 읽기 단위 `D[i..i+n-1]` 또는 `M[i..i+n-1]`; 경계 조건 `n>=1, i>=0, i+n<=size`와 프로파일별 points limit (최종 수치 G0). 공백 device/bank 없는 자동 생성 금지. `D[-1]` 접근 없음.

### 주소 표현
디바이스 문자열 `D100`은 D index=decimal 100, M도 decimal 100. 별도 hex 디바이스(X/Y 등)는 P0에 넣지 않음. wire의 시작 주소는 24-bit LE, 문자 입력은 profile radix 변환. `D100`와 raw `0x64` 같은 대상을 뜻함. 최대 wire head=0xFFFFFF라 하더라도 유효 메모리 상한과 혼동 금지.

### Atomic 계약
`read`: 단일 버전 스냅샷.
`write`: 전체 values type·count·length·range 검증 완료 후 한 번에 commit, version++.
`seed`: 전체 작업의 validates-before-commit; 버전 증가 1회.
`reset`: 지정 초기 상태로 전체 banks 교체, version++; pending I/O와 직렬화.
`snapshot`: `{schema_version, profile_id, logical_version, memory}` immutable 복제; 동일 버전 데이터만.
`restore`: MVP 비범위 (P1 옵션). 파일 export는 canonical sorted keys/UTF-8/defined schema.
**반응성:** 서버 실행 중 상태는 volatile. crash/restart 시 default reset; 설정/seed 외 persistence 없음.

### 16/32-bit 실무 해석
CPU 문서의 16-bit signed 값은 0..65535 원시 값을 client view에서 2's complement로 변환. 32-bit/float/string은 `D[n],D[n+1]`의 word order/endian과 데이터 의미가 필요. MVP에서 데이터를 자동 재배치하거나 타입 의미를 추론하지 않는다.

## P1 시나리오 모델(테스트를 위한 계약, 미구현)
`initial -> trigger(virtual_tick | on_write | control) -> condition -> atomic action -> assertion -> event`.
- virtual clock 은 외부 벽시계와 분리, 타이머 수동 advance로 결정론 보장.
- trigger 순서는 time, registration ordinal 기준. 같은 tick에 실패하면 아무것도 commit하지 않는다.
- fault: phase={PRE_DISPATCH,POST_COMMIT,PRE_SEND}, selector=(command,device,request_ordinal), outcome=(delay/drop/close/error), and deterministic seed.
- 장애 후 `POST_COMMIT` 응답 drop 시 client retry가 동일 write/증분 연산을 반복할 수 있음. 명시적으로 `AT_LEAST_ONCE_AMBIGUOUS`를 로그에 남기고 사용자에게 재조회 권고.

## TOML(설계 스키마, 구현 전 gate에서 validation 계약 고정)
```
[server]
host = "127.0.0.1"
port = 15000
max_clients = 16
max_frame_bytes = 8192
read_header_deadline_seconds = 5
read_body_deadline_seconds = 10
idle_timeout_seconds = 30
write_timeout_seconds = 5

[profile]
id = "generic-q-3e"

[memory]
d_words = 10000
m_bits = 10000

[simulation]
enabled = false

[faults]
enabled = false
```
server `host` 는 MVP `127.0.0.1`만, 포트는 1..65535의 테스트용 포트. `max_frame` <= bytes resource budget. 설정의 mutable/nonmutable 구분: 서버 시작 후 network/profile/size 변경은 별도 재시작; seed/reset만 동작 중 제어.

# TDD 선행 테스트 명세 — 구현 없음

정본 `machine/test_matrix.csv`의 `test_id`, `req_ids`, `oracle`, `gate`, `phase`, `evidence`를 사용한다. 이 문서는 순서·추가 경계·구체적 예시를 제공한다. `NOT_RUN`은 정상적인 사전 설계 상태다.

## 개발 흐름 / Red-Green-Refactor 순서
1. **M0 spec gate G0:** 매뉴얼-프로파일, 원본 클라이언트 wire raw, error end-code, device point cap. 미결 항목은 compatible 구현이라고 표기 금지.
2. **M1 pure-domain:** schema/profile validation, D/M memory, atomic/reset/snapshot. 단위테스트 먼저 실패시키기.
3. **M2 wire:** 3E codec, bit packing, official/derived fixture, malformed/stale/eof error. byte-for-byte contract tests.
4. **M3 session:** asyncio TCP listener, fragmented/coalesced packets, idle/backpressure/FIN/RST/shutdown, multi-client shared memory.
5. **M4 external:** pinned pymcprotocol Type3E sync client, separate process contract; needs actual request capture.
6. **M5 negative and NFR:** fuzz/property, 100/1k-word bounded cases, 16 clients, resource ceilings, Windows/Linux cross-OS smoke.
7. **M6 optional P1:** Fault injection deterministic states/scenario engine only if gate formally approved.

## 최소 상세 판정 사례(다른 케이스는 matrix 참조)
- **RW D:** seed D100=0 → 1401 D100=[100,200,300] → 0401 D100..102 = same, expected LE response and version+1. Bounds `0`,`65535`; input `-1` client side conversion contract is separate.
- **RW M:** write [1,0,1,0,1] at M10 → raw write nibble `10 10 10`→ read 5 points raw identical→ server internal bools; even-6 & odd-1 variants.
- **TCP split/merge:** request byte-by-byte; 2 and 3 frames in one send; bytes order preserved, every response size accurate.
- **negative byte stream:** `00 00` header, huge length, truncated 9-byte header, EOF mid-payload; bounded close, no auto-resync, memory unchanged.
- **decoded negative:** unsupported command 9999, wrong subcmd/D-bit/word-M in P0, count=0, over-limit, write-length mismatches; stable declared end-code + mandatory error payload, memory unchanged.
- **concurrency:** 2 writers overlapping D bank and observer get valid atomic snapshot (no torn vector), compare versions. reset racing with write produces one of two serialized orders only.
- **fault semantics(P1):** failure before/after commit has correct state/version and recorded phase; dropped response is *ambiguous* to client.
- **operations:** startup invalid port/profile disallowed; unexpected external bind rejected; graceful stop sockets cleaned; logs never contain complete memory payload.

## 시험 산출물 / 증거 레코드
요구: `run_id`, Git SHA, python/client version, platform, profile hash, fixture SHA, `test_id`, `expected`, `observed`, `status`, duration, seed, requested gate, build artifact URL. 실패시 최소 재현 bytes (개인정보 마스킹)와 impact targets 기록.

## 측정과 Go/No-go
- 요구 P0의 `test_id` 전부 녹색으로 실행, `test_id` 고아/미연결=0, 실패/skip/xfail 원인 분리.
- wire fixture source-grade/verified status, actual client capture 분리 (derived fixtures만으로 G2 PASS 금지).
- line coverage 코어 최소 90%는 *보조 지표*; branch/의미 요구 커버리지 필요. mutation score 목표치는 초기 실측 후 확정; 임의 숫자 PASS 선언 금지.
- property test는 프레임 파서 panic/oom/hang/negative mutation 없음을 우선; 퍼징 실행 시간과 seed를 추적.
- 성능은 해당 머신의 baseline/p95/p99/RSS 기록, 무근거 절대 SLA 미선언. 실패시 gate HOLD.

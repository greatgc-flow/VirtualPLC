# Binary 3E 프레임·명령 명세 (MVP 전용)

**사실/가정 구분:** 제조사 SLMP Reference Manual SH-080956ENG-M pp.17–28/35–52를 기준으로 정한 일반 포맷. 수치별 제품 지원 차이와 client raw-byte 일치의 마지막 교차검증은 G0 OPEN. `../fixtures/wire_vectors.json` 각 케이스에 출처등급 부여.

## 3E Binary request — byte offset
```
00..01 subheader=50 00
02      network=00
03      station(pc)=FF
04..05 module_io=FF 03 (0x03FF LE)
06      multidrop=00
07..08 body_size(LE) = bytes from monitoring_timer through end of request
09..10 monitoring_timer(LE)
11..12 command(LE): 01 04=0401; 01 14=1401
13..14 subcommand(LE): 00 00=word; 01 00=bit
15..17 device_head(24-bit LE; radix from profile)
18      device_code: D=A8, M=90 for declared generic Q layout
19..20 points(LE)
21..   write payload (read has none)
```
For D word: each value 2 bytes LE, `0000..FFFF`; signed presentation outside wire (e.g. -1 ↔ FFFF). For M bit: two points per byte; **1st bit high nibble**, **2nd bit low nibble**; 5 bits [1,0,1,0,1] → `10 10 10`; odd tail low nibble zero. 비트 불량 nibble >1은 validation fault; ignored tail nibble zero를 요구하며 nonzero tail 처리 정책은 G0 결정전에는 'strict reject'로 테스트용 안전 정책 표시.

## 3E Binary response
```
00..01 subheader = D0 00
02..06 routing: request-derived network,station,IO,multidrop
07..08 response_size = 2 + len(response_data) (LE)
09..10 end_code = 00 00 (success) or vendor-mapped protocol error
11..   response_data (read values; write success empty)
```
**중요 보완:** 3E/4E 오류 응답은 end-code 뒤에 `error responding station (network 1, station 1, module_io 2, multidrop 1) + failed command 2 + subcommand 2` 등의 오류 데이터를 담는다(공식 매뉴얼 p.28). 길이는 *그 바이트를 포함*해야 한다. `pymcprotocol`가 end_code만 검사하는지와 무관하게 프로토콜 구조를 따를 것. 오류 발생 위치에 따라 error responding station이 요청 route와 다를 수 있으므로 generic profile 응답 주체를 정의해야 한다.

## 처리 분류
| 입력 구분 | 결과 | memory |
|---|---|---|
| header·길이·상태 정상 / supported | 0000 success | read or atomic write |
| 헤더/길이 오버런, 제한 위반, 비동기 buffer 손상 | close(무응답) | unchanged |
| frame 완성 / command 또는 subcmd 미지원 | 유효한 error response (endcode G0 map 필요) | unchanged |
| frame 완성 / device·range·point 오류 | 유효한 error response (endcode G0 map 필요) | unchanged |
| frame 완성 / write data length mismatch | 유효한 error response (endcode G0 map 필요) | unchanged |
| partial frame 후 EOF | close, parse event | unchanged |

실제 제품의 특정 end_code는 이 general manual만으로 확정하기 어려우므로 임의 코드와 성공을 표시하지 않는다. **TDD 첫 번째 설계 게이트(G0-E)**에서 공식 제품 매뉴얼 + 고객 사용 프로파일 + client error처리로 매핑 확정.

## 골든 증거
1. `VEC001`: D100 3개 read / 예상 100,200,300 값 응답. **DERIVED** (공식과 구조 비교했으나 client raw capture 아님).
2. `VEC002`: D100~102 write / 0x1995,0x1202,0x1130. **OFFICIAL_PAYLOAD + DERIVED_FRAME** (공식 매뉴얼 p.52 write request payload 근거).
3. `VEC003`: M10 5개 bits / [1,0,1,0,1] → `10 10 10`. **OFFICIAL_PAYLOAD + DERIVED_FRAME** (공식 p.40 nibble).
4. `VEC004`: D0=0xFFFF word write / 응답 빈 write 성공. **DERIVED** (경계 값; distinct fixture).
5. `VEC005`: M bit read odd reply. **DERIVED**.
6. 오류 예시는 mapping 미확정이라 PASS 골든 집합에 **포함하지 않는다**.

## 독립 호환성 재검증
TDD 직전/초기 `pymcprotocol` **pinned 버전**을 local simulator에 연결해 실제 송신 request를 캡처(안전한 loopback only)→fixture와 byte-for-byte compare→차이가 나오면 ADR/스펙/테스트를 동시에 수정한다. 본 ZIP에서는 아직 수행하지 않음. 공식 매뉴얼과 대조하는 것과 클라이언트 실제 시험을 분리할 것.

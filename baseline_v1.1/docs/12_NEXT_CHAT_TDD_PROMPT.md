# 새 채팅 / 개발 인계 프롬프트 (복사)

첨부된 `MC_SLMP_Virtual_PLC_Design_MECE_Revalidated_20261019.zip`을 열고 `docs/00_START_HERE.md`부터 읽어 줘. 우선 `python scripts/validate_design.py`의 결과가 PASS인지 확인하고 요구/테스트/출처/리스크/게이트의 정본을 바꾸지 마. 변경이 꼭 필요하면 ADR→요구/테스트/게이트/지원표 순서로 동시에 업데이트하고 구조 검사에 반영해.

목적은 기존 `pymcprotocol` 및 CIM/MES 클라이언트가 접속하는 독립 **PLC Server**를 TDD(Red-Green-Refactor)로 완성하는 것. Python 3.11+, 표준라이브러리 우선, `asyncio` 3E Binary TCP, D word/M bit 0401/1401, localhost:15000, 단일 atomic state, bounded session, in-process reset/seed/snapshot만 P0. 4E/ASCII/UDP/REST/래더·실 PLC 명령은 추가 승인 전 구현하지 않는다.

TDD 전에 OPEN 상태인 G0-E(에러 코드 및 failed payload), G0-C(pinned pymcprotocol 실제 wire bytes), per-device points cap을 우선 공식 문서와 실제 client 캡처로 검증한다. 인증 없는 MC 포트가 외부 주소로 열리지 않도록 기본 차단하고, 실제 PLC·운영망 접근은 절대 진행하지 않는다. `machine/test_matrix.csv`의 테스트 oracle에 맞춰 Red→Green→Refactor하고 각 gate에 실제 evidence artifact·Git SHA·버전·해시를 남겨.

최종 응답에는 completed tests, coverage, failed/blocked tests, 실제 외부 client interop, 제한 사항, 원인/재발방지(폐루프), release go/no-go를 구분해 보고해. '구조검증 PASS'를 '실제 PLC 호환성 PASS'로 주장하지 마.

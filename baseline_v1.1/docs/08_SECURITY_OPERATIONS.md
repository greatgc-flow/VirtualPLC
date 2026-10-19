# 산업 테스트 서버 안전성·보안·운영·복구 계약

## 위협/오남용 경계
- 외부 실제 PLC/운영망으로 직접 연결/탐색/프록시하는 코드 **비범위**. 테스트 Client endpoint는 `127.0.0.1` allowlist 기본; 잘못된 실PLC 주소 연결 금지.
- MC Protocol 인증이 없으므로 listener loopback 이외 바인딩 거부. 네트워크 격리가 필요한 CI는 독립 network namespace/VM 사용. 관리자 REST 제공 안 함(P0).
- fault injection은 P1도 기본 OFF, 허용된 test-control session과 명시적 opt-in 환경에서만. 로그에 VIRTUAL_PLC_TEST_ONLY 명시.
- input hardening: subheader/route/length/command/device/count, count*size overflow, allocation cap, deadline, max_client, queue cap, fair scheduling.
- 패킷/메모리 덤프는 기본 로그에 금지; 단위테스트 fixture는 합성 값만. 운영정보/PII 우연 포함 시 마스킹 및 접근 권한 제한.

## 운영 수명주기
- START: TOML validate → socket bind(loopback only) → health-ready (실제 bind 이후) → telemetry clear.
- RUN: `connections_current`, `rejected_total`, `requests_total{command}`, `end_code_total`, `parse_faults`, `pending_bytes`, `response_duration` 분포, `memory_version` 관찰; 높은 cardinality 개인정보 key 금지.
- SHUTDOWN: accept stop→in-flight deadline 적용→buffer/connection close→ graceful summary. 실패 시 강제 close; crash recovery는 빈 메모리로 초기화.
- DEBUG: replay input+profile+seed+client version+vector SHA로 reproduce; 연구 로그는 실제 현장 프로토콜 dump와 섞지 않음.
- DOCS: Git release tag와 지원 matrix/checksum 동결. 서드파티 버전/라이선스/supply-chain inventory 유지.

## 회귀와 운영 → 설계 피드백
모니터링 경보/실패/현장 client compatibility 신규 발견→ 이슈 등록(`category=SEC|WIRE|MEMORY|OPS`)→ source/protocol risk audit→ 요구 ID 또는 ADR 수정→ 실패하는 regression 테스트 선작성→ green gate→ release/compat version 태깅→ baseline monitor. 프로토콜 불변식 실패는 롤백 또는 배포 HOLD.

## 주요 실패 모드
- 무응답은 파서/네트워크 차원 실패인지 실제 end-code인지 구별.
- 실패 로그에 원본 사용자·설비 태그 값 남기지 않음.
- 3E에 serial 필드 없음. session 내 순차 응답만 보장; client pipelining 동작시 매칭 근거가 약하므로 결과 검증 필요.
- 협업시 출처 미확정 장치코드/에러코드·성능 수치를 호환성 PASS로 승격 금지.

# TDD용 어댑터 인터페이스 (서버 구현 파일 아님)

## 1. 서버 실행 포트
`--server-cmd "python -m virtual_plc --host {host} --port {port}"`

- 명령은 `shell=False` 실행, `{host}` 는 항상 `127.0.0.1`, `{port}`는 free ephemeral port.
- 새로운 프로세스를 테스트 하나마다 시작하므로 데이터 초기상태가 독립적이어야 한다. 무상태 설정 P0: D/M 0..9999, 초기 0, 3E Binary/TCP, fault injection off.
- readiness=TCP accept on loopback, 요청/응답 timeout. 각 테스트 종료 후 process terminate.
- 가상 PLC의 로직, protocol decoder/encoder, 정확한 endcode는 개발자가 구현해야 한다. 검증 스위트는 테스트 측 독립 encoder로 패킷을 구성하며 서버 내부 코드 재사용 금지.

## 2. 순수 도메인 포트
`MC_SIM_ADAPTER_MODULE=myproject.test_adapter` 로 모듈을 제공. **필수 함수**: `create_memory(*, d_size=10000,m_size=10000)`.

반환 객체는 `read_words(head,count) -> list[int]`, `write_words(head, values)`, `read_bits`, `write_bits`, `reset`, `snapshot()->{'D': sequence,'M': sequence, 'version':int}` 지원. 입력 오류는 `ValueError|IndexError`이며 어떤 부분쓰기/버전 변화도 없어야 한다. snapshot은 불변 스냅샷, 모든 operation은 개별 원자성 보장. 인접 domain(profile/config/telemetry)은 차기 어댑터 포트 확장 시 ADR로 함수 계약 확정. `suite/support/domain_adapter_contract.py`는 typing 명세이며 구현체가 아님.

## 3. 의도적인 미결 인터페이스
- end-code 정수 맵, error response payload의 모델별 추가 bytes: **G0-E OPEN**.
- pinned `pymcprotocol` 버전, 실제 wire capture, client timeout 설정: **G0-C OPEN**.
- 세부 지원 max points, 모니터링 타이머 매핑, route 허용 목록: 제품/고객 프로필 확인 필요.
- 느린 클라이언트/리소스 초과 처리 세부 시간은 profile config에 정의한 값에 따라 시험해야 하며 무조건 1초 같은 절대치를 합격 기준으로 삼지 않는다.

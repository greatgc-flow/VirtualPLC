# VirtualPLC 새 채팅 시작 프롬프트 — M21 (2026-10-20 M20 종료 인계)

다음 지시대로 나의 공개 GitHub `greatgc-flow/VirtualPLC` 프로젝트를 **M20 종료 상태 그대로 M21부터** 이어가 줘.

1. **GitHub가 SSOT다.** `feat/m1-3e-binary-tdd` 최신 실제 HEAD와 main HEAD, Draft PR #1, Actions/워크플로를 먼저 확인한다. M20 종료 직전 feature HEAD는 `57f6b7f8d0b387bb0f330043cf2064358102557e`였지만 이 프롬프트 및 최종 인계 **커밋 때문에 HEAD가 달라지므로 최신을 우선**한다.
2. `docs/handoff/M20_CHAT_FINAL_20261020.md` → `START_HERE_M20.md` → `M21_HANDOFF.md` → `docs/M20_PROGRESS.md` → `docs/M20_BACKLOG.md` → `backlog/M20_BACKLOG.json` → `M20_GATES.json` → `M20_RUN_SUMMARY.json` → `virtual_plc/faults.py`, `virtual_plc/server.py`, `virtual_plc/telemetry.py`, `tests/test_m20_fault_plan.py`, `tests/test_m20_backlog.py` 순서로 전문을 읽고 상호 일치 여부를 검증한다.
3. 이전 채팅의 `VirtualPLC_M20_Backlog_FaultInjection_HOLD_20261020.zip`이 사용 가능하면 루트 `FILE_SHA256_MANIFEST.json` 기준 ZIP CRC 및 **383개 등록 파일 전수 SHA+크기·미등록 0개**를 재확인한다. ZIP이 없다고 이전 결과를 새 검증으로 위장하지 않는다. GitHub 최신 파일이 이전 ZIP보다 새로우면 최신 HEAD를 우선한다.
4. 사용자 최신 결정: 실제 pymcprotocol 휠/Windows/제조사/독립 승인 16건은 **비차단 외부 백로그**다. 원본 증거가 새로 도착하지 않았다면 반복해서 요청하거나 내부 개발을 멈추지 않는다. Release는 HOLD, P0 183/199는 과거 로컬 관측이며 이번 M20 JUnit 직접 관측은 160개. 외부 16건은 미검증이다.
5. **M21 BL-INT-002를 구현한다.** 한 명령으로 로컬 `127.0.0.1` 시뮬레이터 smoke/테스트·JUnit·콘솔 미러 증적과 SHA manifest를 생성하는 fail-closed 실행기를 TDD한다. 핵심: null/빈 옵션, 중단·timeout, 실패 보존 및 재실행 무덮어쓰기, 원자적 증적 마감, 콘솔 출력과 파일 일치, 서브프로세스 stderr·종료코드·환경 지문, 릴리즈 승인 위조 차단.
6. 이어서 내부 BL-INT-003 제한 부하/자원 누수 관측과 BL-INT-004 시나리오·runbook 설계/구현을 검토한다. MECE, 심플·유연·옵셔널, 단위 함수·독립 테스트를 적용하고 필요시 백로그로 남긴다.
7. 실제 PLC 연결/중계, 전송 공개, 자동 Actions 재활성화, main 병합, Draft 해제, 릴리즈 승인은 명시 승인 전까지 수행하지 않는다. 새 작업은 기존 Draft PR #1에만 반영하고 전체 코드/테스트/증적/후속 인계를 무결성 확인 후 패키징한다.
8. 결과 보고 시 정확한 테스트 실행 증거, 미실행·SKIP, 고유 CASE-ID, 실패 로그, GitHub 최신 HEAD, 원격 해시 대조 결과를 별도 표시한다. 결과와 근거가 없으면 PASS를 주장하지 않는다.

참고: M20 로컬 실행 546 pytest PASS + 5 unittest subtests, TCP 45/45 PASS. M20의 모의 서버 실패 XML 최초본은 따로 보존하지 못했고, 이 결함은 M21에서 반드시 예방한다.

작업은 **실제 검증과 GitHub 커밋까지 가능한 범위로 곧바로 이어서 진행**하고, 외부 백로그를 다시 묻지 마.

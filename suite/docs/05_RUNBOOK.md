# 테스트 명령 및 운영 안전 Runbook

## A. 구현 없이 가능한 정적 검사 (P0 design)
```bash
cd MC_SLMP_Virtual_PLC_TDD_TestSuite_v1.2
python scripts/validate_suite.py --json --mutation
python -m unittest discover -s suite/tests/static -p "test_*.py" -v
python scripts/gate_report.py --out evidence/status_HOLD.json
```

## B. 실제 구현을 만든 다음 TDD Red→Green
```bash
python -m pip install -r suite/requirements-test.txt
python -m pytest suite/tests/live/test_wire_cases.py -q --server-cmd "python -m YOUR_SERVER --host {host} --port {port}" --junitxml=evidence/wire.xml
```
**서버 모듈이 없으면 실패하는 것이 정상 Red 상태**. 절대 실제 PLC 주소/현장망 IP로 `--server-cmd` 를 작성하지 않는다.

```bash
# 수용한 domain 포트에서 진행
MC_SIM_ADAPTER_MODULE=YOUR_PACKAGE.test_adapter python -m pytest suite/tests/domain -q --junitxml=evidence/domain.xml
# Windows PowerShell: $env:MC_SIM_ADAPTER_MODULE='YOUR_PACKAGE.test_adapter'
```

## C. pinned client 인터롭(독립 G0-C/G2)
```bash
# 사전 확인한 pymcprotocol 버전과 원본 request 캡처가 있어야 한다.
# 실제 호환판정을 위해 수집한 raw requests와 pinned fixture를 바이트 단위 비교
MC_PINNED_PYMC_VERSION=<VERIFIED_VERSION> python -m pytest suite/tests/live/test_pymc_compat.py -q --server-cmd "python -m YOUR_SERVER --host {host} --port {port}" --run-pymc
```
이 예제의 `<VERIFIED_VERSION>`은 직접 확인하여 채운다. 예약어 그대로 실행 불가.

## D. 수집/재현
테스트의 고유 ID는 `CASE-NNNN`. 실패 시 `JUnit XML, run command (secret 제외), Git commit, OS/Python, simulator version, profile hash, client pin, case ID, seed, timing, memory diff, received code, request hash` 남김. `python scripts/gate_report.py --junit evidence/wire.xml --out evidence/report.json`으로 P0 미실행을 구분해 표시한다.

## E. NO-GO
현장 IP를 테스트에 넣기, `0.0.0.0` 바인딩, 실 I/O, 리얼 PLC 강제명령, unknown end code를 guessed PASS로 기록, only-static PASS를 production-ready 라고 선언: 모두 금지.

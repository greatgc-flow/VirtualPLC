# 오픈소스/공식 문서 참고 색인 — 재배포 코드 포함 안 함

정본 URL, 검증 상태, 역할, 라이선스 상태는 `../machine/sources.json` 참조.

## 기능별로 신뢰할 근거
1. **공식 프로토콜** — Mitsubishi Electric SLMP Reference Manual SH-080956ENG-M: https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engm.pdf (프레임 pp.17–28, D/M pp.35–52)
2. **대표 클라이언트** — https://github.com/senrust/pymcprotocol 및 https://pymcprotocol.netlify.app/ (pinned version raw packets는 G0-C 때 캡처)
3. **가상 MC Server 공개 사례** — https://genbapy.dev/articles/slmp-dummy-server-python (실제 서버 참고, 블로그 코드 라이선스/배포권은 미확정)
4. **독립 클라이언트 후보** — https://github.com/fa-yoshinobu/plc-comm-slmp-python (독립 wire contract 비교용, 서버 아님)
5. **오인하면 안 되는 이름** — https://github.com/Moge800/gomc_rest_python ('REST Server'는 PLC로 향하는 *클라이언트 게이트웨이*, MC PLC endpoint 아님)
6. **다른 Client 참고** — https://github.com/OkitaSystemDesign/MC-Protocol, https://github.com/s-pms/melsec_mc_net (UDP/C 구현 참고, 둘 다 가상 서버 아님)

## 기존 구현을 참고할 때의 결정 절차
- 기존 프로그램이 실제로 **MC 요청을 listen/accept 하는지** 확인하고 client/gateway/server를 따로 표기.
- commit/tag, LICENSE, 저작권 고지, 포함 의존성, 보안/운영 가정, wire coverage 확인.
- 소스를 그대로 재배포하려면 해당 조건 충족 필요. 현재 패키지는 오픈소스·공식 문서 전문을 **복제하지 않고 출처 링크**로만 첨부.
- 실제 라이선스 조건 검증 전에는 설계 원리만 참고하고 개별 구현은 새 TDD로 구축.

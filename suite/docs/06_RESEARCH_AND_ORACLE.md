# 연구 근거/타 구현 사례와 공식·추론 경계

## 1. 1차 규범 자료
- Mitsubishi Electric, SLMP Reference Manual (SH-080956ENG), `https://dl.mitsubishielectric.com/dl/fa/document/manual/plc/sh080956eng/sh080956engl.pdf`: 3E 요청/응답, CMD 0401/1401, D/M, 데이터 packing, 에러 시 응답정보 구조. 장비 모델·모듈별 실제 지원과 독립 확인 필요.
- 제조사 문서 다운로드 목록 `https://www.mitsubishielectric.co.jp/fa/download/search.page?category1=%E5%85%B1%E9%80%9A&category2=&category3=&filter_bundled=&filter_discontinued=1&filter_readme=&kisyu=%2Fplcnet&kisyuid=&lang=2&listView=1&mode=manual&q=&sort=0` : SLMP Reference Manual 버전 확인 (검색 시 2025-10 영어 Ver.N 표기).

## 2. 클라이언트 근거
- `https://github.com/senrust/pymcprotocol` (MIT / client library) 및 `https://pymcprotocol.netlify.app/pymcprotocol`: Type3E, batchread_wordunits, batchwrite_wordunits, batchread_bitunits, batchwrite_bitunits 등의 public client API.
- 핀 고정 전 설치 버전·의존성 확인, local loopback raw capture 필수. test-side `suite/support/wire.py`는 클라이언트 소스에 의존하지 않는 독립 oracle helper.

## 3. 참고 구현 분류
- `baseline_v1.1/refs/REFERENCE_INDEX.md`에 기존 후보와 URL·라이선스 검토 경계 보존. 서버 역할/게이트웨이 역할을 혼동하지 않음.
- 본 패키지에는 외부 구현 전체 복제 없음. 벤더 공식 매뉴얼도 링크로만 제공. 가져오기 전 license+revision+source→risk map 검토 필요.

## 4. 오라클 근거 등급
`OFFICIAL`=벤더 문서 확인, `DERIVED`=일반 사양에서 생성한 기대 바이트, `BASELINE_V1.1`=이전 설계에서 계승, `CLIENT_CAPTURE`=pin 된 실클라이언트 raw capture, `PROFILE_ASSUMPTION`=대상 제품 미확정 계약. 샘플 fixture 5건은 동일 사양에서 파생되며 정적 설계검사는 실제 에뮬레이터의 호환성을 보증하지 않는다.

## 5. 공개된 미확정 항목
제품/모듈/firmware, 허용 route, 기종별 end code 숫자, 명령별 max points, wire 실제 client capture, 사용 CIM/MES tag map. 이들을 미확정 상태로 남긴 것은 빠뜨린 것이 아니라 잘못된 PLC 동작을 만들지 않기 위한 Gate 조건이다.

"""규제·정책 조사 system 의 [8] 신뢰할 수 있는 출처 리스트 — 판 셋(코랩 셀 17 현행·셀 71 금융권·셀 73 비금융권).

날 글은 읽기판 줄을 6칸 들여쓰기 그대로 옮겼다(끝 줄바꿈 하나). prompts.regulation_system 이 머리·꼬리 날 글 사이에
끼우고 dedent 한다(셀 69 「[8] 에 붙여넣어 변경」의 흉내). 판의 바이트 차이(발주서 머리의 diff 확인):
- 셀 17 현행 = 셀 71 + 한국 공공 다섯(12~16) − 셀 71 EU 의 빈 「9.」 줄. 코랩 예시 실행(비금융 공기업)용 손질판이라
  대조 전용이다 — whitelist_for 가 고르지 않는다(발주서 처분 ⑥ 가).
- 셀 73 은 한국 법제처·규제정보포털이 두 번(4·12, 5·13), 미국 Federal Register 가 두 번(2·10)이고 미국 번호 9·국제
  번호 8 이 빠졌다 — 그대로 둔다. 셀 73 머리의 지시 주석과 빈 줄(R/3762-3763)은 프롬프트 글이 아니라 뺐다.
읽기판 줄과 블록 sha256 은 prompts/README.md.
"""

from typing import Final, Literal

WHITELIST_COLAB17: Final = """\
      =====================================================================
      [8] 신뢰할 수 있는 출처 리스트
      =====================================================================

      다음 출처를 우선하여 검색한다.

      1. 지역별 구분 - 한국, 미국, EU, 기타 국가
          1. 한국
              1. 한국회계기준원 https://www.kasb.or.kr/
              2. 기후에너지환경부 https://www.mcee.go.kr/home/web/main.do
              3. 산업통상자원부 https://www.motir.go.kr/
              4. 금융감독원 https://www.fss.or.kr/fss/main/main.do?menuNo=200000
              5. 금융위원회 https://www.fsc.go.kr/index
              6. 법제처 https://www.law.go.kr/main.html
              7. 규제정보포털 https://www.better.go.kr/zz.main.PortalMain
              8. 한국은행 https://www.bok.or.kr/portal/main/main.do
              9. 국민연금 https://www.nps.or.kr/gate.do
              10. 기후정보포털 https://www.climate.go.kr/home/
              11. 한국거래소(KRX) https://www.krx.co.kr/main/main.jsp
              12. ALIO https://www.alio.go.kr/
              13. 공공데이터 포털 https://www.data.go.kr/
              14. 국가통계 포털 https://kosis.kr/index/index.do
              15. 클린아이 https://www.cleaneye.go.kr/index.jsp
              16. 재정경제부 https://mofe.go.kr/
          2. 미국
              1. SEC https://www.sec.gov/
              2. Federal Register https://www.federalregister.gov/
              3. 미국 중앙은행 https://www.federalreserve.gov/
              4. 백악관 https://www.whitehouse.gov/
              5. EPA https://www.epa.gov/
              6. FDIC https://www.fdic.gov/ (연방예금보험공사)
              7. OCC https://www.occ.treas.gov/ (통화감독청)
              8. US TREASURY https://home.treasury.gov/
              9. CFTC https://www.cftc.gov/ (상품선물거래위원회)
              10. FASB https://www.fasb.org/ (미국회계기준위원회)
          3. EU
              1. EFRAG https://www.efrag.org/en
              2. European Commission https://finance.ec.europa.eu/index_en
              3. EU 법령 https://eur-lex.europa.eu/homepage.html
              4. ESMA https://www.esma.europa.eu/ (유럽 증권시장감독청)
              5. EBA https://www.eba.europa.eu/homepage (유럽은행감독청)
              6. EIOPA https://www.eiopa.europa.eu/index_en (유럽보험연금감독청)
              7. ECB https://www.ecb.europa.eu/ (유럽중앙은행)
              8. EEA https://www.eea.europa.eu/ (유럽환경청)
          4. 기타 국가
              1. 일본 법령 https://laws.e-gov.go.jp/
              2. 일본 재무부 https://www.fsa.go.jp/
              3. 캐나다 정부 https://www.canada.ca/en.html
              4. 캐나다 환경 및 기후 https://www.canada.ca/en/environment-climate-change.html
              5. 캐나다 금융감독청 https://www.osfi-bsif.gc.ca/en
              6. 캐나다 증권인증 https://www.securities-administrators.ca/
              7. 영국 재무부 https://www.gov.uk/government/organisations/hm-treasury
              8. 영국 은행 https://www.bankofengland.co.uk/
              9. 영국 금융행위감독청 https://www.fca.org.uk/
              10. 싱가폴 통화청 https://www.mas.gov.sg/
              11. 홍콩 통화청 https://www.hkma.gov.hk/
              12. 홍콩 증권선물위원회 https://www.sfc.hk/en/
              13. 호주 건전성감독청 https://www.apra.gov.au/
              14. 호주 증권투자위원회 https://www.asic.gov.au/
        2. 국제 표준 가이드라인 기관 및 국제기구
            1. GRI https://www.globalreporting.org/standards/
            2. IFRS https://www.ifrs.org/
            3. SASB https://sasb.ifrs.org/
            4. NGFS https://www.ngfs.net/en (녹색금융협의체)
            5. IOSCO https://www.iosco.org/ (국제증권관리위원회)
            6. ICMA https://www.icmagroup.org/ (국제자본시장협회)
            7. IEA https://www.iea.org/ (국제에너지기구)
            8. IPCC https://www.ipcc.ch/
            9. PRI https://www.unpri.org/ (유엔책임투자원칙)
            10. WRI https://www.wri.org/ (세계자원연구소)
        3. 정책 규제 가이드라인 업데이트 모니터링 언론
            1. 법률신문 https://www.lawtimes.co.kr/
            2. ESG경제 https://www.esgeconomy.com/
            3. 임팩트온 https://www.impacton.net/
            4. ESG Today https://www.esgtoday.com/
        4. 아카이빙 사이트 (세계 각국 법령 정보 모음)
            1. 세계법제정보센터 https://world.moleg.go.kr/web/main/index.do
            2. ICLG https://iclg.com/

      =====================================================================
"""
"""셀 17 현행 [8](R/573-652, 출처 64). 대조 전용."""

WHITELIST_CELL71: Final = """\
      =====================================================================
      [8] 신뢰할 수 있는 출처 리스트
      =====================================================================

      다음 출처를 우선하여 검색한다.

      1. 지역별 구분 - 한국, 미국, EU, 기타 국가
          1. 한국
              1. 한국회계기준원 https://www.kasb.or.kr/
              2. 기후에너지환경부 https://www.mcee.go.kr/home/web/main.do
              3. 산업통상자원부 https://www.motir.go.kr/
              4. 금융감독원 https://www.fss.or.kr/fss/main/main.do?menuNo=200000
              5. 금융위원회 https://www.fsc.go.kr/index
              6. 법제처 https://www.law.go.kr/main.html
              7. 규제정보포털 https://www.better.go.kr/zz.main.PortalMain
              8. 한국은행 https://www.bok.or.kr/portal/main/main.do
              9. 국민연금 https://www.nps.or.kr/gate.do
              10. 기후정보포털 https://www.climate.go.kr/home/
              11. 한국거래소(KRX) https://www.krx.co.kr/main/main.jsp
          2. 미국
              1. SEC https://www.sec.gov/
              2. Federal Register https://www.federalregister.gov/
              3. 미국 중앙은행 https://www.federalreserve.gov/
              4. 백악관 https://www.whitehouse.gov/
              5. EPA https://www.epa.gov/
              6. FDIC https://www.fdic.gov/ (연방예금보험공사)
              7. OCC https://www.occ.treas.gov/ (통화감독청)
              8. US TREASURY https://home.treasury.gov/
              9. CFTC https://www.cftc.gov/ (상품선물거래위원회)
              10. FASB https://www.fasb.org/ (미국회계기준위원회)
          3. EU
              1. EFRAG https://www.efrag.org/en
              2. European Commission https://finance.ec.europa.eu/index_en
              3. EU 법령 https://eur-lex.europa.eu/homepage.html
              4. ESMA https://www.esma.europa.eu/ (유럽 증권시장감독청)
              5. EBA https://www.eba.europa.eu/homepage (유럽은행감독청)
              6. EIOPA https://www.eiopa.europa.eu/index_en (유럽보험연금감독청)
              7. ECB https://www.ecb.europa.eu/ (유럽중앙은행)
              8. EEA https://www.eea.europa.eu/ (유럽환경청)
              9.
          4. 기타 국가
              1. 일본 법령 https://laws.e-gov.go.jp/
              2. 일본 재무부 https://www.fsa.go.jp/
              3. 캐나다 정부 https://www.canada.ca/en.html
              4. 캐나다 환경 및 기후 https://www.canada.ca/en/environment-climate-change.html
              5. 캐나다 금융감독청 https://www.osfi-bsif.gc.ca/en
              6. 캐나다 증권인증 https://www.securities-administrators.ca/
              7. 영국 재무부 https://www.gov.uk/government/organisations/hm-treasury
              8. 영국 은행 https://www.bankofengland.co.uk/
              9. 영국 금융행위감독청 https://www.fca.org.uk/
              10. 싱가폴 통화청 https://www.mas.gov.sg/
              11. 홍콩 통화청 https://www.hkma.gov.hk/
              12. 홍콩 증권선물위원회 https://www.sfc.hk/en/
              13. 호주 건전성감독청 https://www.apra.gov.au/
              14. 호주 증권투자위원회 https://www.asic.gov.au/
        2. 국제 표준 가이드라인 기관 및 국제기구
            1. GRI https://www.globalreporting.org/standards/
            2. IFRS https://www.ifrs.org/
            3. SASB https://sasb.ifrs.org/
            4. NGFS https://www.ngfs.net/en (녹색금융협의체)
            5. IOSCO https://www.iosco.org/ (국제증권관리위원회)
            6. ICMA https://www.icmagroup.org/ (국제자본시장협회)
            7. IEA https://www.iea.org/ (국제에너지기구)
            8. IPCC https://www.ipcc.ch/
            9. PRI https://www.unpri.org/ (유엔책임투자원칙)
            10. WRI https://www.wri.org/ (세계자원연구소)
        3. 정책 규제 가이드라인 업데이트 모니터링 언론
            1. 법률신문 https://www.lawtimes.co.kr/
            2. ESG경제 https://www.esgeconomy.com/
            3. 임팩트온 https://www.impacton.net/
            4. ESG Today https://www.esgtoday.com/
        4. 아카이빙 사이트 (세계 각국 법령 정보 모음)
            1. 세계법제정보센터 https://world.moleg.go.kr/web/main/index.do
            2. ICLG https://iclg.com/

      =====================================================================
"""
"""셀 71 금융권(R/3677-3752, 출처 59)."""

WHITELIST_CELL73: Final = """\
      =====================================================================
      [8] 신뢰할 수 있는 출처 리스트
      =====================================================================

      다음 출처를 우선하여 검색한다.

      1. 지역별 구분 - 한국, 미국, EU, 기타 국가
          1. 한국
              1. 기후에너지환경부 https://www.mcee.go.kr/home/web/main.do
              2. 산업통상자원부 https://www.motir.go.kr/
              3. 고용노동부 https://www.moel.go.kr/index.do
              4. 법제처 https://www.law.go.kr/main.html
              5. 규제정보포털 https://www.better.go.kr/zz.main.PortalMain
              6. 기후정보포털 https://www.climate.go.kr/home/
              7. 산업통상자원부(MOTIE) https://www.motie.go.kr/
              8. 공정거래위원회 https://www.ftc.go.kr/
              9. 국토교통부 https://www.molit.go.kr/
              10. 과학기술정보통신부 https://www.msit.go.kr/
              11. 원자력안전위원회 https://www.nssc.go.kr/
              12. 법제처 https://www.law.go.kr/main.html
              13. 규제정보포털 https://www.better.go.kr/zz.main.PortalMain
              14. 한국표준협회(KSA) / KS 표준 https://www.ksa.or.kr/

          2. 미국
              1. SEC https://www.sec.gov/
              2. Federal Register https://www.federalregister.gov/
              3. US TREASURY https://home.treasury.gov/
              4. 백악관 https://www.whitehouse.gov/
              5. EPA https://www.epa.gov/ (환경보호청)
              6. DOE https://www.energy.gov/ (미국 에너지부)
              7. Department of Commerce (DOC) https://www.commerce.gov/
              8. OSHA https://www.osha.gov/ (산업안전보건청)
              10. Federal Register https://www.federalregister.gov/ (미국 연방 관보)
              11. NIST (표준기술연구소) https://www.nist.gov/
              12. Department of Transportation (DOT) https://www.transportation.gov/
          3. EU
              1. EFRAG https://www.efrag.org/en
              2. European Commission https://finance.ec.europa.eu/index_en
              3. EU 법령 https://eur-lex.europa.eu/homepage.html
              4. EEA https://www.eea.europa.eu/ (유럽환경청)
              5. EU OSHA https://osha.europa.eu/en (산업안전청)
              6. JRC https://joint-research-centre.ec.europa.eu/ (EU 공동연구센터)
              7. DG ENER https://energy.ec.europa.eu/ (에너지총국)
              8. DG ENV https://environment.ec.europa.eu/ (환경총국)
          4. 기타 국가
              1. 일본 법령 https://laws.e-gov.go.jp/
              2. 일본 환경성 https://www.env.go.jp/
              3. 일본 경제산업성(METI) https://www.meti.go.jp/
              4. 일본 노동성(MHLW) https://www.mhlw.go.jp/
              5. 캐나다 정부 https://www.canada.ca/en.html
              6. 캐나다 환경 및 기후 https://www.canada.ca/en/environment-climate-change.html
              7. 캐나다 표준위원회(SCC) https://www.scc.ca/en
              8. 영국 환경식품농림부(DEFRA) https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs
              9. 영국 HSE(산업안전보건청) https://www.hse.gov.uk/
              10. 싱가포르 환경부(NEA) https://www.nea.gov.sg/
              11. 호주 환경/기후청(DECC) https://www.dcceew.gov.au/
              12. 호주 산업/과학부(DISR) https://www.industry.gov.au/
        2. 국제 표준 가이드라인 기관 및 국제기구
            1. GRI https://www.globalreporting.org/standards/
            2. IFRS https://www.ifrs.org/
            3. SASB https://sasb.ifrs.org/
            4. ISO https://www.iso.org/ (국제표준화기구)
            5. IEA https://www.iea.org/ (국제에너지기구)
            6. IPCC https://www.ipcc.ch/
            7. UNEP https://www.unep.org/
            9. ILO https://www.ilo.org/ (국제노동기구)
            10. WRI https://www.wri.org/ (세계자원연구소)
        3. 정책 규제 가이드라인 업데이트 모니터링 언론
            1. 법률신문 https://www.lawtimes.co.kr/
            2. ESG경제 https://www.esgeconomy.com/
            3. 임팩트온 https://www.impacton.net/
            4. ESG Today https://www.esgtoday.com/
            5. Energy Monitor https://www.energymonitor.ai/
        4. 아카이빙 사이트 (세계 각국 법령 정보 모음)
            1. 세계법제정보센터 https://world.moleg.go.kr/web/main/index.do
            2. ICLG https://iclg.com/
            3. ECOLEX (환경 법령 DB) https://www.ecolex.org/
            4. FAOLEX (농업·식품 관련 법령) https://www.fao.org/faolex/

      =====================================================================
"""
"""셀 73 비금융권(R/3764-3843, 출처 63)."""

WhitelistName = Literal["cell71", "cell73"]


def whitelist_for(sector: str) -> tuple[WhitelistName, str]:
    """입력의 sector 로 판을 고른다: financial → 셀 71, non_financial → 셀 73(발주서 처분 ⑥ 가). 그 밖은 ValueError."""
    if sector == "financial":
        return "cell71", WHITELIST_CELL71
    if sector == "non_financial":
        return "cell73", WHITELIST_CELL73
    raise ValueError(f"모르는 sector: {sector!r}")

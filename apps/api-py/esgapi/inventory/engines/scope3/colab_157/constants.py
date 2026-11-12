"""코랩 C1·C2 길이 닿는 규칙표·상수(읽기판 줄을 글자 그대로 옮김 — 줄 번호는 상수마다 단다).

원천: `received-derived/2026-10-15/Scope 3 코랩/Scope3_생물기원적용_.md`(`MARC-ENT-157`, 원본 sha1 `9801d39d…`).
고유명(회사·사람) 0 — 옮긴 상수에 기업 이름은 없다(2026-10-19 다시 봄). 수치 상수는 환율 표 하나이고 그 출처는
코랩 셀 자체다(아래). C1·C2 밖의 수치 상수(`WASTE_AVG_EF`·`DEFAULT_TRANSPORT_EF_MAP_PATCH` 등)는 옮기지 않았다(S3C-b·c).
같은 이름을 코랩이 여러 번 정의한 것은 **마지막 정의**를 옮겼다(`GENERIC_NOISE_WORDS`·`NOISE_PATTERNS`·
`ERP_TO_NAICS_HINTS` 는 `:2489`·`:2494`·`:2503` 판 — 앞 `:2386`·`:2391`·`:2465` 판을 덮는다).
코랩의 밑줄 이름(`_CURRENCY_ALIAS`·`_MANUAL_PURCHASE_TITLE_RULES`)은 다른 파일이 읽도록 밑줄을 뗐다(값은 그대로).
"""

from typing import Final, TypedDict


class GroupRule(TypedDict):
    group_key: str
    group_ko: str
    category: str
    family: str
    keywords: list[str]


class NaicsHint(TypedDict):
    family: str
    patterns: list[str]
    titles: list[str]
    generic_ko: str
    generic_en: str


# 코랩 :2358-2382. 걸러 쓰는 것(그 계수 책에 있는 제목만 — :2384·:7954)은 purchase.py.
CURATED_SPEND_CANDIDATES: Final[list[str]] = [
    "Office Supplies (except Paper) Manufacturing",
    "Stationery Product Manufacturing",
    "Printing and Writing Paper Merchant Wholesalers",
    "Stationery and Office Supplies Merchant Wholesalers",
    "Office Supplies and Stationery Stores",
    "Office Furniture (except Wood) Manufacturing",
    "Wood Office Furniture Manufacturing",
    "Showcase, Partition, Shelving, and Locker Manufacturing",
    "Furniture Merchant Wholesalers",
    "Electronic Computer Manufacturing",
    "Computer Terminal and Other Computer Peripheral Equipment Manufacturing",
    "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
    "Office Equipment Merchant Wholesalers",
    "Coffee and Tea Manufacturing",
    "Soft Drink Manufacturing",
    "Bottled Water Manufacturing",
    "General Line Grocery Merchant Wholesalers",
    "Other Grocery and Related Products Merchant Wholesalers",
    "Sanitary Paper Product Manufacturing",
    "Commercial Printing (except Screen and Books)",
    "Sign Manufacturing",
    "Hazardous Waste Treatment and Disposal",
    "Other Nonhazardous Waste Treatment and Disposal",
]


# 코랩 :2665-2671(build_allowed_titles 안의 broad_defaults)
BROAD_DEFAULT_TITLES: Final[list[str]] = [
    "Office Supplies (except Paper) Manufacturing",
    "Stationery and Office Supplies Merchant Wholesalers",
    "Other Grocery and Related Products Merchant Wholesalers",
    "Furniture Merchant Wholesalers",
    "Office Equipment Merchant Wholesalers",
]


# 코랩 :2489-2492(마지막 정의)
GENERIC_NOISE_WORDS: Final[list[str]] = [
    "구입",
    "구매",
    "구입대",
    "구입건",
    "구입비",
    "추가",
    "의 건",
    "관련",
    "정산",
    "품의",
    "사용",
    "용",
    "등",
    "외",
]


# 코랩 :2494-2501(마지막 정의)
NOISE_PATTERNS: Final[list[str]] = [
    r"\([^)]*\)",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}\b",
    r"\b\d+\.\d+\b",
    r"[=:,/.\-*]+",
    r"\b\d+\b",
]


# 코랩 :2503-2628(마지막 정의 — :2484 의 「계수 책에 있는 제목만」 거르기는 이 판에 걸리지 않는다. 코랩 그대로)
ERP_TO_NAICS_HINTS: Final[list[NaicsHint]] = [
    {
        "family": "office_supplies",
        "patterns": [
            r"사무용품",
            r"문구",
            r"소모품",
            r"스테플러",
            r"계산기",
            r"바인더",
            r"서류봉투",
            r"도장",
            r"고무인",
            r"라벨지",
            r"화이트보드",
            r"자석테이프",
            r"펜심",
            r"책꽂이",
            r"결재판",
        ],
        "titles": [
            "Office Supplies (except Paper) Manufacturing",
            "Stationery and Office Supplies Merchant Wholesalers",
            "Office Supplies and Stationery Stores",
        ],
        "generic_ko": "사무용품",
        "generic_en": "office supplies",
    },
    {
        "family": "paper",
        "patterns": [r"a4용지", r"복사지", r"copy\s*paper", r"용지", r"복사\s*지"],
        "titles": [
            "Printing and Writing Paper Merchant Wholesalers",
            "Stationery Product Manufacturing",
        ],
        "generic_ko": "복사용지",
        "generic_en": "copy paper",
    },
    {
        "family": "printer_supplies",
        "patterns": [r"토너", r"잉크", r"카트리지", r"프린터\s*토너", r"복사기\s*토너", r"드럼\s*유닛"],
        "titles": [
            "Office Supplies (except Paper) Manufacturing",
            "Office Equipment Merchant Wholesalers",
        ],
        "generic_ko": "프린터 소모품",
        "generic_en": "printer supplies",
    },
    {
        "family": "office_furniture",
        "patterns": [r"의자", r"책상", r"보조책상", r"파티션", r"옷장", r"캐비닛", r"비품", r"수납장"],
        "titles": [
            "Office Furniture (except Wood) Manufacturing",
            "Wood Office Furniture Manufacturing",
            "Showcase, Partition, Shelving, and Locker Manufacturing",
            "Furniture Merchant Wholesalers",
        ],
        "generic_ko": "사무용 비품/가구",
        "generic_en": "office furniture",
    },
    {
        "family": "computer",
        "patterns": [r"노트북", r"데스크탑", r"컴퓨터", r"pc\b", r"서버"],
        "titles": [
            "Electronic Computer Manufacturing",
            "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        ],
        "generic_ko": "컴퓨터 장비",
        "generic_en": "computer equipment",
    },
    {
        "family": "monitor",
        "patterns": [r"모니터", r"디스플레이", r"태블릿모니터"],
        "titles": [
            "Computer Terminal and Other Computer Peripheral Equipment Manufacturing",
            "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        ],
        "generic_ko": "모니터/주변기기",
        "generic_en": "computer monitor",
    },
    {
        "family": "coffee",
        "patterns": [r"커피원두", r"원두", r"캡슐\s*커피", r"커피"],
        "titles": [
            "Coffee and Tea Manufacturing",
            "Other Grocery and Related Products Merchant Wholesalers",
        ],
        "generic_ko": "커피/원두",
        "generic_en": "coffee",
    },
    {
        "family": "water",
        "patterns": [r"생수", r"식수대", r"정수기\s*물", r"정수기", r"물통"],
        "titles": [
            "Bottled Water Manufacturing",
            "Other Grocery and Related Products Merchant Wholesalers",
        ],
        "generic_ko": "생수/식수",
        "generic_en": "drinking water",
    },
    {
        "family": "beverages_snacks",
        "patterns": [r"주방음료", r"탕비", r"간식", r"음료", r"자판기\s*재료", r"다과"],
        "titles": [
            "Other Grocery and Related Products Merchant Wholesalers",
            "General Line Grocery Merchant Wholesalers",
            "Soft Drink Manufacturing",
        ],
        "generic_ko": "주방음료/간식",
        "generic_en": "beverages and snacks",
    },
    {
        "family": "paper_cups_tissue",
        "patterns": [r"종이컵", r"휴지", r"티슈", r"키친타월"],
        "titles": [
            "Sanitary Paper Product Manufacturing",
            "Stationery Product Manufacturing",
        ],
        "generic_ko": "위생 종이류",
        "generic_en": "paper hygiene products",
    },
    {
        "family": "printing_sign",
        "patterns": [r"상장케이스", r"상장", r"명함", r"인쇄", r"출력물", r"현수막", r"사인", r"표지판", r"기념품"],
        "titles": [
            "Commercial Printing (except Screen and Books)",
            "Sign Manufacturing",
        ],
        "generic_ko": "인쇄물/표지/기념품",
        "generic_en": "printed materials",
    },
    {
        "family": "waste",
        "patterns": [r"폐기물", r"오니", r"폐수", r"처리비", r"처리\s*용역"],
        "titles": [
            "Hazardous Waste Treatment and Disposal",
            "Other Nonhazardous Waste Treatment and Disposal",
        ],
        "generic_ko": "폐기물 처리",
        "generic_en": "waste treatment",
    },
]


# 코랩 :2955-3033
SPEND_FAMILY_TITLES: Final[dict[str, list[str]]] = {
    "office_supplies": [
        "Office Supplies (except Paper) Manufacturing",
        "Stationery and Office Supplies Merchant Wholesalers",
        "Office Supplies and Stationery Stores",
        "Stationery Product Manufacturing",
        "Printing and Writing Paper Merchant Wholesalers",
    ],
    "paper": [
        "Printing and Writing Paper Merchant Wholesalers",
        "Stationery Product Manufacturing",
        "Stationery and Office Supplies Merchant Wholesalers",
        "Office Supplies and Stationery Stores",
        "All Other Converted Paper Product Manufacturing",
    ],
    "printer_supplies": [
        "Office Supplies (except Paper) Manufacturing",
        "Stationery and Office Supplies Merchant Wholesalers",
        "Office Equipment Merchant Wholesalers",
        "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        "Other Electronic Parts and Equipment Merchant Wholesalers",
    ],
    "office_furniture": [
        "Office Furniture (except Wood) Manufacturing",
        "Wood Office Furniture Manufacturing",
        "Furniture Merchant Wholesalers",
        "Showcase, Partition, Shelving, and Locker Manufacturing",
        "Institutional Furniture Manufacturing",
    ],
    "computer": [
        "Electronic Computer Manufacturing",
        "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        "Office Equipment Merchant Wholesalers",
        "Electronics Stores",
        "Electronic Shopping and Mail-Order Houses",
    ],
    "monitor": [
        "Computer Terminal and Other Computer Peripheral Equipment Manufacturing",
        "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        "Office Equipment Merchant Wholesalers",
        "Electronics Stores",
        "Electronic Shopping and Mail-Order Houses",
    ],
    "coffee": [
        "Coffee and Tea Manufacturing",
        "Other Grocery and Related Products Merchant Wholesalers",
        "General Line Grocery Merchant Wholesalers",
        "Electronic Shopping and Mail-Order Houses",
        "Warehouse Clubs and Supercenters",
    ],
    "water": [
        "Bottled Water Manufacturing",
        "Other Grocery and Related Products Merchant Wholesalers",
        "General Line Grocery Merchant Wholesalers",
        "Electronic Shopping and Mail-Order Houses",
        "Warehouse Clubs and Supercenters",
    ],
    "beverage": [
        "Other Grocery and Related Products Merchant Wholesalers",
        "General Line Grocery Merchant Wholesalers",
        "Soft Drink Manufacturing",
        "Coffee and Tea Manufacturing",
        "Warehouse Clubs and Supercenters",
    ],
    "sanitary_paper": [
        "Sanitary Paper Product Manufacturing",
        "All Other Converted Paper Product Manufacturing",
        "Office Supplies (except Paper) Manufacturing",
        "Stationery and Office Supplies Merchant Wholesalers",
        "Office Supplies and Stationery Stores",
    ],
    "waste": [
        "Hazardous Waste Treatment and Disposal",
        "Other Nonhazardous Waste Treatment and Disposal",
        "Hazardous Waste Collection",
        "Other Waste Collection",
        "Materials Recovery Facilities",
    ],
}


# 코랩 :3462-3475. 2025년 월평균 원/달러 환율(원/USD). 출처는 코랩 셀의 주석 「2025년 공식 월평균 원/달러 환율」뿐이다
# (한국은행 원표와 대조하지 않음 — 추정). C1·C2 에서는 USD 금액의 연평균 환산(normalize_purchase_unit)에만 쓰인다.
BOK_USD_KRW_MONTHLY_AVG_2025: Final[dict[int, float]] = {
    1: 1455.79,
    2: 1445.56,
    3: 1456.95,
    4: 1444.31,
    5: 1394.49,
    6: 1366.95,
    7: 1375.22,
    8: 1389.66,
    9: 1391.83,
    10: 1423.36,
    11: 1457.77,
    12: 1467.40,
}


# 코랩 :3665-3681
CURRENCY_ALIAS: Final[dict[str, str]] = {
    # 원화 계열
    "원": "KRW",
    "krw": "KRW",
    "₩": "KRW",
    "한화": "KRW",
    "won": "KRW",
    "korean won": "KRW",
    # 달러 계열
    "usd": "USD",
    "달러": "USD",
    "미달러": "USD",
    "$": "USD",
    "us dollar": "USD",
    "us$": "USD",
    # 기타 외화 — USD로 간주 (환율 보정 필요)
    "eur": "EUR",
    "유로": "EUR",
    "€": "EUR",
    "jpy": "JPY",
    "엔": "JPY",
    "¥": "JPY",
    "cny": "CNY",
    "위안": "CNY",
    "인민폐": "CNY",
    "vnd": "VND",
    "동": "VND",
    "sgd": "SGD",
    "싱가포르달러": "SGD",
    "gbp": "GBP",
    "파운드": "GBP",
    "£": "GBP",
    "": "KRW",  # 미입력 → KRW 기본
}


# 코랩 :5718-5846
PURCHASE_GROUP_RULES: Final[list[GroupRule]] = [
    # ── Category1: 구매품 및 서비스 (원재료/부자재/포장재/소모품/사무용품/외주/서비스) ──
    {
        "group_key": "raw_material",
        "group_ko": "원재료/부자재",
        "category": "Category1",
        "family": "raw_material",
        "keywords": ["원재료", "부자재", "원자재", "철강", "철판", "알루미늄", "플라스틱", "수지", "원료"],
    },
    {
        "group_key": "packaging",
        "group_ko": "포장재",
        "category": "Category1",
        "family": "packaging",
        "keywords": ["포장재", "포장지", "골판지", "박스", "비닐", "테이프", "완충재", "에어캡"],
    },
    {
        "group_key": "paper_a4",
        "group_ko": "A4/복사지",
        "category": "Category1",
        "family": "office_sup_paper",
        "keywords": ["a4용지", "a3용지", "복사지", "복사용지", "용지", "코팅지", "라벨지"],
    },
    {
        "group_key": "toner_ink",
        "group_ko": "토너/잉크",
        "category": "Category1",
        "family": "office_sup_printer",
        "keywords": ["토너", "잉크", "카트리지", "드럼", "복사기토너", "프린트 토너", "프린터토너"],
    },
    {
        "group_key": "office_stationery",
        "group_ko": "문구/일반사무용품",
        "category": "Category1",
        "family": "office_sup_stationery",
        "keywords": [
            "사무용품",
            "문구",
            "소모품",
            "스테플러",
            "가위",
            "서류봉투",
            "고무인",
            "도장",
            "결재판",
            "자석테이프",
            "책꽂이",
            "화이트보드",
            "명찰",
        ],
    },
    {
        "group_key": "pantry",
        "group_ko": "주방/탕비용품",
        "category": "Category1",
        "family": "pantry_supplies",
        "keywords": ["커피", "차", "생수", "물", "종이컵", "음료", "다과", "원두"],
    },
    {
        "group_key": "outsourcing_service",
        "group_ko": "외주가공/서비스용역",
        "category": "Category1",
        "family": "service_outsourcing",
        "keywords": [
            "외주",
            "외주가공",
            "가공비",
            "용역",
            "서비스",
            "컨설팅",
            "청소",
            "경비",
            "시설관리",
            "유지보수",
            "수리비",
        ],
    },
    # ── Category2: 자본재 (설비/장비/차량/건물 등 자산으로 회계처리된 항목) ──
    {
        "group_key": "manufacturing_equipment",
        "group_ko": "생산설비/기계장치",
        "category": "Category2",
        "family": "manufacturing_equipment",
        "keywords": ["생산설비", "기계장치", "프레스", "CNC", "선반", "용접기", "컨베이어"],
    },
    {
        "group_key": "vehicle",
        "group_ko": "차량",
        "category": "Category2",
        "family": "vehicle",
        "keywords": ["차량", "트럭", "승용차", "화물차", "지게차", "포크리프트"],
    },
    {
        "group_key": "building_construction",
        "group_ko": "건물/구축물",
        "category": "Category2",
        "family": "building",
        "keywords": ["건물", "구축물", "창고", "건설", "공장"],
    },
    {
        "group_key": "desk_table",
        "group_ko": "책상/보조책상",
        "category": "Category2",
        "family": "office_furniture_desk",
        "keywords": ["책상", "보조책상", "테이블"],
    },
    {
        "group_key": "chair",
        "group_ko": "의자",
        "category": "Category2",
        "family": "office_furniture_chair",
        "keywords": ["의자"],
    },
    {
        "group_key": "partition",
        "group_ko": "파티션",
        "category": "Category2",
        "family": "office_furniture_partition",
        "keywords": ["파티션"],
    },
    {
        "group_key": "cabinet_storage",
        "group_ko": "옷장/캐비닛/수납장",
        "category": "Category2",
        "family": "office_furniture_storage",
        "keywords": ["옷장", "캐비닛", "수납장"],
    },
    {
        "group_key": "computer_equipment",
        "group_ko": "컴퓨터/IT장비",
        "category": "Category2",
        "family": "computer_equipment",
        "keywords": ["노트북", "데스크탑", "컴퓨터", "pc", "모니터", "서버", "태블릿", "스마트폰"],
    },
    {
        "group_key": "printer_device",
        "group_ko": "프린터/복합기",
        "category": "Category2",
        "family": "printer_device",
        "keywords": ["프린터", "복합기", "스캐너"],
    },
    {
        "group_key": "software_license",
        "group_ko": "소프트웨어",
        "category": "Category2",
        "family": "software_it",
        "keywords": ["소프트웨어", "라이선스", "license", "software"],
    },
]


# 코랩 :8295-8305
MANUAL_PURCHASE_TITLE_RULES: Final[list[tuple[list[str], list[str]]]] = [
    (
        ["플라스틱수지", "수지", "레진", "resin", "polymer", "pe", "pp", "pet", "abs", "pvc"],
        ["Plastics Material and Resin Manufacturing", "Plastics Packaging Film and Sheet Manufacturing"],
    ),
    (
        ["골판지", "포장박스", "박스", "carton", "corrugated"],
        ["Corrugated and Solid Fiber Box Manufacturing", "Folding Paperboard Box Manufacturing"],
    ),
    (
        ["erp", "시스템유지보수", "소프트웨어유지보수", "it서비스", "개발용역", "si", "시스템통합", "소프트웨어개발"],
        [
            "Custom Computer Programming Services",
            "Data Processing, Hosting, and Related Services",
            "Software Publishers",
        ],
    ),
    (
        ["전문서비스", "컨설팅", "자문", "경영자문", "consulting"],
        ["Management Consulting Services", "Professional and Management Development Training"],
    ),
    (
        ["창고랙", "랙설비", "랙", "선반", "shelving", "locker", "storage rack"],
        ["Showcase, Partition, Shelving, and Locker Manufacturing", "Lessors of Miniwarehouses and Self-Storage Units"],
    ),
    (
        ["지게차", "포크리프트", "forklift", "스태커"],
        [
            "Industrial Truck, Tractor, Trailer, and Stacker Machinery Manufacturing",
            "Light Truck and Utility Vehicle Manufacturing",
        ],
    ),
    (
        [
            "자동포장",
            "포장라인",
            "생산설비",
            "기계장치",
            "제조설비",
            "기계",
            "설비",
            "machine",
            "machinery",
            "equipment",
        ],
        [
            "Other Industrial Machinery Manufacturing",
            "Conveyor and Conveying Equipment Manufacturing",
            "Special Industry Machinery Manufacturing",
        ],
    ),
    (
        ["차량운반구", "승용차", "자동차", "차량", "suv", "vehicle", "car"],
        [
            "Automobile Manufacturing",
            "Light Truck and Utility Vehicle Manufacturing",
            "Automotive Parts and Accessories Stores",
        ],
    ),
    (
        ["노트북", "데스크탑", "컴퓨터", "pc", "서버", "laptop"],
        [
            "Electronic Computer Manufacturing",
            "Computer and Computer Peripheral Equipment and Software Merchant Wholesalers",
        ],
    ),
]


# ── S3C-b1: 지출(C4-2·C9-2·C6-2)·폐기물(C5) 길의 규칙표·상수 ──
# 수치(`WASTE_AVG_EF`·`BIOGENIC_WASTE_FCF`·`WEIGHT_TO_KG`)는 코랩 셀의 값이고, 출처는 코랩 주석(환경부 지침·IPCC 2006
# Vol.5 Table 2.4·US EPA)뿐이다 — 우리가 그 원천에서 확인하지 않았다(운영 규칙 4). 확인 전에는 「코랩 값」으로만 쓴다.

# 코랩 :353 — 처리방법별 환경부 전체 평균 EF(kgCO2eq/kg). 「기타」 키는 없다(:659 의 fallback 이 None 이 된다).
WASTE_AVG_EF: Final[dict[str, float]] = {"매립": 0.175965929, "소각": 1.176142131, "재활용": 0.029390317}

# 코랩 :362 — 생물기원 대상 그룹의 화석탄소비율(FCF). 코랩 주석: IPCC 2006 Vol.5 Table 2.4 기본값.
BIOGENIC_WASTE_FCF: Final[dict[str, float]] = {"음식물류": 0.0, "폐지류": 0.01, "폐목재류": 0.0}

# 코랩 :365-369 — C12 폐기물 코드(중분류·소분류 앞부분) → 생물기원 대상 그룹(S3C-c1b-1). 차례대로 「코드가 접두로
# 시작」 이 먼저 걸린다. 코랩 주석: 91-08 폐가구류는 목재 EF 와 같다.
BIOGENIC_C12_CODE_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("51-21", "음식물류"), ("91-01", "음식물류"),
    ("51-03", "폐지류"), ("91-02", "폐지류"),
    ("51-04", "폐목재류"), ("91-08", "폐목재류"), ("91-09", "폐목재류"),
)  # fmt: skip

# 코랩 :626-635 — 처리방법 정규화(dict 차례대로 「별칭 ⊂ 입력」 이 먼저 걸린다).
TREATMENT_ALIAS: Final[dict[str, str]] = {
    "매립": "매립", "land": "매립", "landfill": "매립",
    "소각": "소각", "incineration": "소각", "incinerator": "소각", "inc": "소각",
    "재활용": "재활용", "recycling": "재활용", "recycle": "재활용", "rec": "재활용",
    "기타": "기타", "other": "기타", "etc": "기타",
}  # fmt: skip

# 코랩 :3683-3689 — 중량 단위 → kg. 「metric ton」 은 `normalize_unit` 이 공백을 지워 걸리지 않는다(코랩 그대로).
WEIGHT_TO_KG: Final[dict[str, float]] = {
    "kg": 1.0, "킬로그램": 1.0, "kilogram": 1.0,
    "g": 0.001, "gram": 0.001, "그램": 0.001,
    "ton": 1000.0, "t": 1000.0, "톤": 1000.0, "mt": 1000.0, "metric ton": 1000.0,
    "lb": 0.453592, "lbs": 0.453592, "pound": 0.453592,
    "oz": 0.028350, "ounce": 0.028350,
}  # fmt: skip

# 코랩 :7644-7666 `_template_transport_code` 의 낱말(차례 그대로 — 더 구체적인 것이 먼저).
TRANSPORT_CODE_KEYWORDS: Final[list[tuple[str, list[str]]]] = [
    ("parcel", ["택배", "소화물", "특송", "courier", "parcel", "express"]),
    ("sea_bulk", ["벌크", "bulk", "drybulk", "bulkcarrier"]),
    ("inland_water", ["내륙수로", "inlandwater", "riverfreight", "barge"]),
    ("sea", [
        "외항선", "컨테이너선", "해상", "선박", "해운", "배", "항만",
        "ocean", "sea", "vessel", "ship", "marine", "container",
    ]),
    ("air", ["항공화물", "항공", "공항", "aircargo", "airfreight", "air", "flight", "awb"]),
    ("rail", ["철도", "철송", "기차", "열차", "rail", "railway", "train", "ktx", "srt"]),
    ("road", ["도로", "육상", "육로", "트럭", "화물차", "윙바디", "탑차", "차량", "truck", "lorry", "road", "van"]),
]  # fmt: skip

# 코랩 :7742-7750 — 운송 Spend 조회 때 표시명에 덧붙이는 힌트.
TRANSPORT_CODE_TO_SPEND_HINT: Final[dict[str, str]] = {
    "road": "도로 트럭 화물 truck freight",
    "parcel": "택배 소화물 courier parcel express",
    "rail": "철도 기차 rail train",
    "sea": "해상 선박 ocean freight sea freight vessel",
    "sea_bulk": "벌크선 bulk ocean freight sea freight",
    "inland_water": "내륙수로 river freight inland water",
    "air": "항공화물 항공 air freight air cargo flight",
}

# 코랩 :8595-8602 — 출장 Spend 수동 표(낱말 → NAICS Title).
TRAVEL_SPEND_MANUAL: Final[list[tuple[list[str], str]]] = [
    (["항공", "비행", "airfare", "flight", "항공권"], "Scheduled Passenger Air Transportation"),
    (["철도", "기차", "ktx", "srt", "rail", "train"], "Line-Haul Railroads"),
    (["숙박", "호텔", "모텔", "hotel", "lodging", "accommodation"], "Hotels (except Casino Hotels) and Motels"),
    (["렌터카", "렌트카", "rentalcar", "carrental"], "Passenger Cars, Rental"),
    (["택시", "taxi", "cab"], "Taxi Service"),
    (["버스", "bus", "coach"], "Interurban and Rural Bus Transportation"),
]

# 코랩 :8535-8551 `normalize_travel_mode` 의 앞 표(정규화 글에 낱말이 들면 그 이동수단 — 차례 그대로).
TRAVEL_MODE_FIX_KEYWORDS: Final[list[tuple[list[str], str]]] = [
    (["숙박", "호텔", "모텔", "lodging", "hotel", "accommodation"], "lodging"),
    (["렌터카", "렌트카", "rentalcar", "carrental"], "rental_car"),
    (["철도", "기차", "ktx", "srt", "rail", "train"], "train"),
    (["항공", "비행", "flight", "air"], "flight"),
    (["택시", "taxi", "cab"], "taxi"),
    (["버스", "bus", "coach"], "bus"),
    (["지하철", "전철", "subway", "metro"], "subway"),
    (["승용차", "자가용", "차량", "car"], "car"),
]


# ── S3C-b2a: 거리(C4-1·C9-1 — C6-1·C7 도 같은 거리 길)의 규칙표·상수 ──
# 보정계수(`DISTANCE_MODE_FACTOR`)·운송 기본 계수(`DEFAULT_TRANSPORT_EF_MAP_PATCH`)·국내 상한(distance.py)은 코랩 셀의
# 값이고, 출처는 코랩 주석(ICAO Carbon Calculator·DEFRA 방법론·Climatiq 벤치마킹)뿐이다 — 우리가 그 원천에서 확인하지
# 않았다(운영 규칙 4). 확인 전에는 「코랩 값」으로만 쓴다.

# 코랩 :1611 — 직선거리 × 이동수단별 보정계수(air 1.09 는 코랩 주석의 ICAO/DEFRA 우회보정).
DISTANCE_MODE_FACTOR: Final[dict[str, float]] = {"road": 1.3, "parcel": 1.35, "air": 1.09, "sea": 1.30, "rail": 1.20}

# 코랩 :1616 — 출발지/도착지 글이 이미 공항인지 보는 낱말.
AIRPORT_TEXT_HINTS: Final[list[str]] = ["공항", "airport", "국제공항", "terminal"]

# 코랩 :1582 — AI 실거리 프롬프트의 운송수단 이름(없으면 mode 그대로).
DISTANCE_MODE_LABEL: Final[dict[str, str]] = {
    "road": "도로(트럭)", "parcel": "택배", "sea": "해상", "air": "항공", "rail": "철도",
}  # fmt: skip

# 코랩 :1120-1145 의 키워드 사전 + :6573-6579 의 보강(`list(set(…))` — 옛 `infer_transport_mode` 가 `any()` 로만 보니
# 차례는 값에 닿지 않는다). 옛 판(:1153)의 1·2순위가 parcel → air → sea → rail → road 차례로 본다(transport.py).
ROAD_KEYWORDS: Final[list[str]] = [
    "road", "truck", "lorry", "van", "delivery", "freight", "cargo truck",
    "트럭", "화물차", "카고", "배송", "납품", "상차", "하차", "육상",
    "윙바디", "탑차", "냉동탑차", "5t", "11t", "25t",
    "도로", "육로", "화물", "차량", "운송차량", "트레일러",
]  # fmt: skip
SEA_KEYWORDS: Final[list[str]] = [
    "sea", "ocean", "vessel", "voyage", "fcl", "lcl", "bl", "mbl", "hbl",
    "port", "terminal", "cy", "cfs", "선박", "해상", "항만", "부산항", "인천항", "평택항",
    "해운", "포워더", "수출", "수입",
]  # fmt: skip
AIR_KEYWORDS: Final[list[str]] = [
    "air", "air cargo", "flight", "awb", "mawb", "hawb", "airport", "cargo",
    "항공", "항공화물", "공항", "대한항공 cargo", "asiana cargo", "icn", "gmp", "pvg", "nrt",
    "항공특송",
]  # fmt: skip
RAIL_KEYWORDS: Final[list[str]] = [
    "rail", "railway", "train", "intermodal rail",
    "철도", "철송", "기차",
    "KTX", "SRT",
]  # fmt: skip
PARCEL_KEYWORDS: Final[list[str]] = [
    "parcel", "courier", "express", "small parcel",
    "택배", "특송", "퀵", "cj대한통운", "한진택배", "롯데택배", "fedex", "dhl", "ups",
    "소포", "퀵배송",
]  # fmt: skip
# 코랩 :1146-1147
PORT_HINTS: Final[list[str]] = ["항", "port", "terminal", "cy", "부산항", "인천항", "평택항"]
AIRPORT_HINTS: Final[list[str]] = ["공항", "airport", "icn", "gmp", "pvg", "nrt", "lax", "jfk"]
# 코랩 :1204 — 옛 판 3순위의 국내 사업장 낱말(대소문자 그대로 `in`).
DOMESTIC_SITE_HINTS: Final[list[str]] = ["공장", "창고", "물류센터", "고객사", "warehouse", "factory", "dc"]

# 코랩 :6563-6570 — 운송 계수 맵의 기본값(kgCO2e/ton-km). `_build_transport_ef_map_from_db` 의 :421·:425 도 같은 값.
DEFAULT_TRANSPORT_EF_MAP_PATCH: Final[dict[str, float]] = {
    "road": 0.120, "parcel": 0.180, "rail": 0.030, "sea": 0.015, "air": 0.600,
}  # fmt: skip

# 코랩 :6479-6484 — 거리기반 운송량의 중량 단위 → kg(b1 `WEIGHT_TO_KG` :3683 과 다른 표: lb 배수·oz 없음·kilograms 등).
WEIGHT_TO_KG_PATCH: Final[dict[str, float]] = {
    "kg": 1.0, "킬로그램": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001, "그램": 0.001,
    "ton": 1000.0, "tons": 1000.0, "t": 1000.0, "톤": 1000.0, "mt": 1000.0, "metric ton": 1000.0,
    "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237,
}  # fmt: skip


# ── S3C-b2b: 출장·통근 거리(C6-1·C7)의 규칙표·상수 ──
# DEFRA 기본 계수(`TRAVEL_EF_DEFAULTS`)·버스+지하철 기본값은 코랩 셀의 값이고, 출처는 코랩 주석(「DEFRA 2025 기준
# 기본값」)뿐이다 — 우리가 DEFRA 원천에서 확인하지 않았다(운영 규칙 4). 확인 전에는 「코랩 값」으로만 쓴다.

# 코랩 :440-455 — 출장·통근 계수 맵의 기본값(kgCO2e/km, 계수 책 `출장_통근` 의 코드가 덮는다).
TRAVEL_EF_DEFAULTS: Final[dict[str, float]] = {
    "flight": 0.14253, "flight_dom": 0.22928, "flight_short": 0.12786,
    "flight_short_eco": 0.12576, "flight_short_biz": 0.18863,
    "flight_long": 0.15282, "flight_long_eco": 0.11704,
    "flight_long_prem": 0.18726, "flight_long_biz": 0.33940,
    "flight_long_first": 0.46814, "flight_eco": 0.10916,
    "flight_biz": 0.31656, "flight_first": 0.43663,
    "ferry": 0.11270, "ferry_foot": 0.01871, "ferry_car": 0.12933,
    "bus": 0.10385, "coach": 0.02776,
    "train": 0.03546, "train_intl": 0.00446, "tram": 0.02860, "subway": 0.02780,
    "taxi": 0.14861,
    "car": 0.17304, "car_small": 0.14340, "car_medium": 0.17174, "car_large": 0.21007,
    "car_hybrid": 0.09167, "car_ev": 0.0,
    "motorcycle": 0.11367, "motorcycle_small": 0.08319, "motorcycle_large": 0.13252,
    "walk": 0.0, "bicycle": 0.0,
}  # fmt: skip

# 코랩 :3343 — `BUS_SUBWAY_AVG_EF = (map.get("bus", 0.10385) + map.get("subway", 0.0278)) / 2` 의 대안 값.
BUS_SUBWAY_FALLBACK: Final[tuple[float, float]] = (0.10385, 0.0278)

# 코랩 :8671 — 출장 계수가 없거나 0 이면(`or`) 쓰는 코드.
TRAVEL_EF_FALLBACK_CODE: Final = "car"

# 코랩 :8682 — 통근 근무일수가 없을 때.
COMMUTE_DEFAULT_WORKDAYS: Final = 245

# 코랩 :8692 — 통근 거리가 이 값(km)을 넘으면 AI 직선거리로 교차검증한다.
COMMUTE_AI_CHECK_KM: Final = 100

# 코랩 :8191-8194 `_fix_contains_roundtrip` — 이 칸들의 글에 왕복 낱말이 들면 거리왕복계수 1(아니면 2).
ROUNDTRIP_COLUMNS: Final[list[str]] = ["비고", "설명/적요", "단위환산비고"]
ROUNDTRIP_WORDS: Final[list[str]] = ["왕복", "round trip", "roundtrip", "return trip", "왕복기준"]


# ── S3C-c1a: 에너지 계열(C3·C8·C13 — C11·C14 도 같은 사슬)의 규칙표·상수 ──
# 발열량(`ENERGY_BASE_UNIT`)의 출처는 코랩 주석(「에너지법 시행규칙 8차 순발열량 기준」)뿐이고, 폴백 계수
# (`ENERGY_FALLBACK_EF_PATCH`)는 코랩 주석이 「데모/안전 fallback」 이라 적은 코랩 상수다(출처 없음).
# 환산 배수는 코랩 셀의 식 그대로다. 우리가 그 원천에서 확인하지 않았다(운영 규칙 4) — 확인 전에는 「코랩 값」 으로만
# 쓴다.

# 코랩 :3723-3741 — 에너지원별 (기준단위, 순발열량 MJ/기준단위).
# 출처: 코랩 주석 「에너지법 시행규칙 8차 순발열량 기준」.
ENERGY_BASE_UNIT: Final[dict[str, tuple[str, float | None]]] = {
    "도시가스(LNG)": ("Nm³", 38.5),
    "천연가스(LNG)": ("kg", 49.4),
    "CNG(차량)": ("kg", 49.4),
    "LNG(차량)": ("kg", 49.4),
    "도시가스(LPG)": ("Nm³", 58.3),
    "액화석유가스(LPG)": ("kg", 46.2),
    "LPG(차량)": ("kg", 46.2),
    "경유": ("L", 35.3),
    "보일러 등유": ("L", 34.1),
    "실내 등유": ("L", 34.1),
    "등유": ("L", 34.1),
    "항공유": ("L", 34.0),
    "휘발유": ("L", 30.1),
    "전력": ("kWh", None),
    "전기": ("kWh", None),
    "열(스팀)": ("GJ", None),
    "스팀": ("GJ", None),
}

# 코랩 :3744-3756 — 에너지원 이름 감지(`_detect_energy_name` `:3766` 이 dict 차례로 본다).
ENERGY_NAME_ALIAS: Final[dict[str, list[str]]] = {
    "경유": ["경유", "디젤", "diesel", "gas oil"],
    "휘발유": ["휘발유", "가솔린", "gasoline", "petrol"],
    "보일러 등유": ["보일러등유", "보일러 등유", "b등유", "kerosene"],
    "실내 등유": ["실내등유", "실내 등유", "등유"],
    "항공유": ["항공유", "제트유", "jet fuel", "aviation fuel"],
    "도시가스(LNG)": ["도시가스", "도시가스(lng)", "city gas", "lng(도시)"],
    "천연가스(LNG)": ["천연가스", "lng", "natural gas"],
    "도시가스(LPG)": ["도시가스(lpg)", "lpg도시"],
    "액화석유가스(LPG)": ["lpg", "액화석유가스", "프로판", "부탄", "propane", "butane"],
    "전력": ["전력", "전기", "electricity", "electric", "kwh", "power"],
    "열(스팀)": ["열", "스팀", "steam", "district heat", "지역난방"],
}

# 코랩 :3759-3764 — MJ 기반 공통 환산 상수.
MJ_PER_KWH: Final = 3.6
MJ_PER_MWH: Final = 3600.0
MJ_PER_GJ: Final = 1000.0
MJ_PER_TJ: Final = 1_000_000.0
MJ_PER_TOE: Final = 41_868.0
MJ_PER_GCAL: Final = 4_186.8

# 코랩 :3884-3890 — `convert_energy_unit` 의 kWh 기준 배수(식 그대로).
ENERGY_KWH_FACTORS: Final[dict[str, float]] = {
    "kwh": 1.0, "wh": 0.001, "mwh": 1000.0, "gwh": 1e6,
    "kj": 1/3.6, "mj": 1/MJ_PER_KWH, "gj": MJ_PER_GJ/MJ_PER_KWH,
    "tj": MJ_PER_TJ/MJ_PER_KWH,
    "kcal": 1/860, "mcal": 1000/860, "gcal": MJ_PER_GCAL/MJ_PER_KWH,
    "toe": MJ_PER_TOE/MJ_PER_KWH,
}  # fmt: skip

# 코랩 :3904-3909 — GJ 기준 배수(식 그대로).
ENERGY_GJ_FACTORS: Final[dict[str, float]] = {
    "gj": 1.0, "mj": 0.001, "tj": 1000.0, "kj": 1e-6,
    "kwh": MJ_PER_KWH/1000, "mwh": MJ_PER_MWH/1000,
    "kcal": 4.1868e-6*1000, "mcal": 4.1868/1000, "gcal": 4.1868,
    "toe": MJ_PER_TOE/1000,
}  # fmt: skip

# 코랩 :3925-3939 — 입력단위 → MJ(발열량 경유 환산).
ENERGY_MJ_PER_INPUT: Final[dict[str, float]] = {
    "mj": 1.0, "kj": 0.001, "gj": MJ_PER_GJ, "tj": MJ_PER_TJ, "kwh": MJ_PER_KWH, "mwh": MJ_PER_MWH,
    "kcal": 4.1868e-3, "mcal": 4.1868, "gcal": MJ_PER_GCAL, "toe": MJ_PER_TOE, "toe/y": MJ_PER_TOE,
}  # fmt: skip

# 코랩 :3943 · :3952-3956 · :3965 — 같은 계열 질량·부피·가스 부피 배수.
ENERGY_KG_FACTORS: Final[dict[str, float]] = {
    "kg": 1.0,
    "g": 0.001,
    "ton": 1000.0,
    "t": 1000.0,
    "lb": 0.453592,
    "mt": 1000.0,
}
ENERGY_VOLUME_FACTORS: Final[dict[str, float]] = {
    "l": 1.0, "ml": 0.001, "kl": 1000.0, "m3": 1000.0, "m³": 1000.0, "gal": 3.78541, "gallon": 3.78541,
}  # fmt: skip
ENERGY_GAS_FACTORS: Final[dict[str, float]] = {"nm3": 1.0, "nm³": 1.0, "m3": 1.0, "m³": 1.0, "l": 0.001, "ml": 1e-6}

# 코랩 :514-522 — 첫 `lookup_energy_ef`(`:479`)의 낱말 별칭(입력 전체가 키와 같을 때만).
ENERGY_ALIAS_479: Final[dict[str, str]] = {
    "전기": "전력", "electricity": "전력", "electric": "전력",
    "lng": "도시가스(lng)", "천연가스": "천연가스(lng)",
    "cng": "cng(차량)", "도시가스": "도시가스(lng)",
    "lpg": "액화석유가스(lpg)", "프로판": "액화석유가스(lpg)",
    "diesel": "경유", "gasoline": "휘발유", "kerosene": "보일러 등유",
    "스팀": "열(스팀)", "steam": "열(스팀)", "열": "열(스팀)",
    "항공": "항공유", "jet": "항공유",
}  # fmt: skip

# 코랩 :6805-6820 — 통합DB 매칭 실패 때의 폴백 계수(이름, kgCO2e/단위, 단위).
# 코랩 주석: 「데모/안전 fallback으로만 사용」 — 코랩 상수, 출처 없음.
# dict 차례로 「키 ⊂ 입력 또는 입력 ⊂ 키」 첫 것이 걸린다.
ENERGY_FALLBACK_EF_PATCH: Final[dict[str, tuple[str, float, str]]] = {
    "전력": ("전력", 0.45941, "kWh"),
    "전기": ("전력", 0.45941, "kWh"),
    "electricity": ("전력", 0.45941, "kWh"),
    "도시가스": ("도시가스(LNG)", 2.23, "Nm³"),
    "도시가스(lng)": ("도시가스(LNG)", 2.23, "Nm³"),
    "천연가스": ("도시가스(LNG)", 2.23, "Nm³"),
    "lng": ("도시가스(LNG)", 2.23, "Nm³"),
    "경유": ("경유", 2.65, "L"),
    "휘발유": ("휘발유", 2.30, "L"),
    "스팀": ("열(스팀)", 56.10, "GJ"),
    "열(스팀)": ("열(스팀)", 56.10, "GJ"),
    "상수도": ("상수도", 0.332, "m³"),
    "수도": ("상수도", 0.332, "m³"),
}

# 코랩 :7294-7318 — `_ef_norm_unit` 의 단위 맵.
EF_UNIT_MAP: Final[dict[str, str]] = {
    "kwh": "kwh", "kwhr": "kwh", "kw": "kw", "wh": "wh", "gj": "gj", "mj": "mj", "tj": "tj",
    "l": "l", "liter": "l", "litre": "l", "리터": "l",
    "kg": "kg", "킬로그램": "kg", "ton": "ton", "t": "ton", "톤": "ton",
    "m3": "m3", "nm3": "nm3", "n㎥": "nm3", "n루베": "nm3", "루베": "m3", "㎥": "m3",
}  # fmt: skip

# 코랩 :7337-7345 · :7502-7503 — `_ef_similarity` 의 포함 점수와 fuzzy 문턱·상한.
ENERGY_CONTAINS_SIMILARITY: Final = 0.92
ENERGY_FUZZY_THRESHOLD: Final = 0.72
ENERGY_FUZZY_CAP: Final = 0.93
# 코랩 :7473 · :7483-7485 · :7490-7492 — 갈래마다 (기본 점수, 상한).
# raw exact 는 1.0, alias exact 는 0.97(상한 둘 다 1.0)
ENERGY_ALIAS_EXACT_SCORE: Final = 0.97
ENERGY_ALIAS_CONTAINS_SCORE: Final[tuple[float, float]] = (0.90, 0.98)
ENERGY_QUERY_CONTAINS_SCORE: Final[tuple[float, float]] = (0.86, 0.95)
# 코랩 :7423-7433 `_unit_match_score` — 같은 단위 · Nm³/m³ 혼용 · 다른 단위
ENERGY_UNIT_BONUS: Final[tuple[float, float, float]] = (0.08, 0.04, -0.05)

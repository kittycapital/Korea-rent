"""
전국 아파트 전월세 대시보드 (CSV 버전)
─────────────────────────────────────
CSV 파일에서 데이터를 읽어 전세/월세 구별 TOP 10 생성:
  1) 전세 → data/district_top10_jeonse.json
  2) 월세 → data/district_top10_wolse.json  (환산보증금 기준)

- 데이터 소스: 국토교통부 실거래가 공개시스템 CSV 다운로드
- 필터: 전용면적 59㎡ 이상
- 기간: TOP 산정 최근 6개월 / 추이 차트 최근 1년
- 월세 환산: 보증금 + (월세 × 12 / 전월세전환율)
"""

import csv
import glob
from datetime import datetime, timedelta
from collections import defaultdict
import os, json

# ── 설정 ──

DATA_DIR = 'data'
CSV_DIR = os.path.join(DATA_DIR, 'csv_jeonse')
MIN_AREA = 59
WOLSE_RATE = 0.05  # 전월세전환율 (5%)

# ── 시도 이름 매핑 (CSV 풀네임 → 약칭) ──
SIDO_MAP = {
    '서울특별시': '서울시',
    '부산광역시': '부산시',
    '대구광역시': '대구시',
    '인천광역시': '인천시',
    '광주광역시': '광주시',
    '대전광역시': '대전시',
    '울산광역시': '울산시',
    '세종특별자치시': '세종시',
    '경기도': '경기도',
    '강원특별자치도': '강원도',
    '충청북도': '충북',
    '충청남도': '충남',
    '전북특별자치도': '전북',
    '전라남도': '전남',
    '경상북도': '경북',
    '경상남도': '경남',
    '제주특별자치도': '제주도',
    # 이전 명칭 호환
    '강원도': '강원도',
    '전라북도': '전북',
}

# ── 전국 지역코드 ──
REGIONS = {
    # 서울시 (25)
    '11110':('서울시','종로구'),'11140':('서울시','중구'),'11170':('서울시','용산구'),
    '11200':('서울시','성동구'),'11215':('서울시','광진구'),'11230':('서울시','동대문구'),
    '11260':('서울시','중랑구'),'11290':('서울시','성북구'),'11305':('서울시','강북구'),
    '11320':('서울시','도봉구'),'11350':('서울시','노원구'),'11380':('서울시','은평구'),
    '11410':('서울시','서대문구'),'11440':('서울시','마포구'),'11470':('서울시','양천구'),
    '11500':('서울시','강서구'),'11530':('서울시','구로구'),'11545':('서울시','금천구'),
    '11560':('서울시','영등포구'),'11590':('서울시','동작구'),'11620':('서울시','관악구'),
    '11650':('서울시','서초구'),'11680':('서울시','강남구'),'11710':('서울시','송파구'),
    '11740':('서울시','강동구'),
    # 부산시
    '26110':('부산시','중구'),'26140':('부산시','서구'),'26170':('부산시','동구'),
    '26200':('부산시','영도구'),'26230':('부산시','부산진구'),'26260':('부산시','동래구'),
    '26290':('부산시','남구'),'26320':('부산시','북구'),'26350':('부산시','해운대구'),
    '26380':('부산시','사하구'),'26410':('부산시','금정구'),'26440':('부산시','강서구'),
    '26470':('부산시','연제구'),'26500':('부산시','수영구'),'26530':('부산시','사상구'),
    '26710':('부산시','기장군'),
    # 대구시
    '27110':('대구시','중구'),'27140':('대구시','동구'),'27170':('대구시','서구'),
    '27200':('대구시','남구'),'27230':('대구시','북구'),'27260':('대구시','수성구'),
    '27290':('대구시','달서구'),'27710':('대구시','달성군'),'27720':('대구시','군위군'),
    # 인천시
    '28110':('인천시','중구'),'28140':('인천시','동구'),'28177':('인천시','미추홀구'),
    '28185':('인천시','연수구'),'28200':('인천시','남동구'),'28237':('인천시','부평구'),
    '28245':('인천시','계양구'),'28260':('인천시','서구'),'28710':('인천시','강화군'),
    '28720':('인천시','옹진군'),
    # 광주시
    '29110':('광주시','동구'),'29140':('광주시','서구'),'29155':('광주시','남구'),
    '29170':('광주시','북구'),'29200':('광주시','광산구'),
    # 대전시
    '30110':('대전시','동구'),'30140':('대전시','중구'),'30170':('대전시','서구'),
    '30200':('대전시','유성구'),'30230':('대전시','대덕구'),
    # 울산시
    '31110':('울산시','중구'),'31140':('울산시','남구'),'31170':('울산시','동구'),
    '31200':('울산시','북구'),'31710':('울산시','울주군'),
    # 세종시
    '36110':('세종시','세종시'),
    # 경기도
    '41111':('경기도','수원시 장안구'),'41113':('경기도','수원시 권선구'),
    '41115':('경기도','수원시 팔달구'),'41117':('경기도','수원시 영통구'),
    '41131':('경기도','성남시 수정구'),'41133':('경기도','성남시 중원구'),
    '41135':('경기도','성남시 분당구'),'41150':('경기도','의정부시'),
    '41171':('경기도','안양시 만안구'),'41173':('경기도','안양시 동안구'),
    '41190':('경기도','부천시'),'41210':('경기도','광명시'),
    '41220':('경기도','평택시'),'41250':('경기도','동두천시'),
    '41271':('경기도','안산시 상록구'),'41273':('경기도','안산시 단원구'),
    '41281':('경기도','고양시 덕양구'),'41285':('경기도','고양시 일산동구'),
    '41287':('경기도','고양시 일산서구'),'41290':('경기도','과천시'),
    '41310':('경기도','구리시'),'41360':('경기도','남양주시'),
    '41370':('경기도','오산시'),'41390':('경기도','시흥시'),
    '41410':('경기도','군포시'),'41430':('경기도','의왕시'),
    '41450':('경기도','하남시'),'41461':('경기도','용인시 처인구'),
    '41463':('경기도','용인시 기흥구'),'41465':('경기도','용인시 수지구'),
    '41480':('경기도','파주시'),'41500':('경기도','이천시'),
    '41550':('경기도','안성시'),'41570':('경기도','김포시'),
    '41590':('경기도','화성시'),'41610':('경기도','광주시'),
    '41630':('경기도','양주시'),'41650':('경기도','포천시'),
    '41670':('경기도','여주시'),'41800':('경기도','연천군'),
    '41820':('경기도','가평군'),'41830':('경기도','양평군'),
    # 강원도
    '51110':('강원도','춘천시'),'51130':('강원도','원주시'),
    '51150':('강원도','강릉시'),'51170':('강원도','동해시'),
    '51190':('강원도','태백시'),'51210':('강원도','속초시'),
    '51230':('강원도','삼척시'),'51710':('강원도','홍천군'),
    '51720':('강원도','횡성군'),'51730':('강원도','영월군'),
    '51740':('강원도','평창군'),'51750':('강원도','정선군'),
    '51760':('강원도','철원군'),'51770':('강원도','화천군'),
    '51780':('강원도','양구군'),'51790':('강원도','인제군'),
    '51800':('강원도','고성군'),'51810':('강원도','양양군'),
    # 충북
    '43111':('충북','청주시 상당구'),'43112':('충북','청주시 서원구'),
    '43113':('충북','청주시 흥덕구'),'43114':('충북','청주시 청원구'),
    '43130':('충북','충주시'),'43150':('충북','제천시'),
    '43720':('충북','보은군'),'43730':('충북','옥천군'),
    '43740':('충북','영동군'),'43745':('충북','증평군'),
    '43750':('충북','진천군'),'43760':('충북','괴산군'),
    '43770':('충북','음성군'),'43800':('충북','단양군'),
    # 충남
    '44131':('충남','천안시 동남구'),'44133':('충남','천안시 서북구'),
    '44150':('충남','공주시'),'44180':('충남','보령시'),
    '44200':('충남','아산시'),'44210':('충남','서산시'),
    '44230':('충남','논산시'),'44250':('충남','계룡시'),
    '44270':('충남','당진시'),'44710':('충남','금산군'),
    '44760':('충남','부여군'),'44770':('충남','서천군'),
    '44790':('충남','청양군'),'44800':('충남','홍성군'),
    '44810':('충남','예산군'),'44825':('충남','태안군'),
    # 전북
    '52111':('전북','전주시 완산구'),'52113':('전북','전주시 덕진구'),
    '52130':('전북','군산시'),'52140':('전북','익산시'),
    '52180':('전북','정읍시'),'52190':('전북','남원시'),
    '52210':('전북','김제시'),'52710':('전북','완주군'),
    '52720':('전북','진안군'),'52730':('전북','무주군'),
    '52740':('전북','장수군'),'52750':('전북','임실군'),
    '52770':('전북','순창군'),'52790':('전북','고창군'),
    '52800':('전북','부안군'),
    # 전남
    '46110':('전남','목포시'),'46130':('전남','여수시'),
    '46150':('전남','순천시'),'46170':('전남','나주시'),
    '46230':('전남','광양시'),'46710':('전남','담양군'),
    '46720':('전남','곡성군'),'46730':('전남','구례군'),
    '46770':('전남','고흥군'),'46780':('전남','보성군'),
    '46790':('전남','화순군'),'46800':('전남','장흥군'),
    '46810':('전남','강진군'),'46820':('전남','해남군'),
    '46830':('전남','영암군'),'46840':('전남','무안군'),
    '46860':('전남','함평군'),'46870':('전남','영광군'),
    '46880':('전남','장성군'),'46890':('전남','완도군'),
    '46900':('전남','진도군'),'46910':('전남','신안군'),
    # 경북
    '47111':('경북','포항시 남구'),'47113':('경북','포항시 북구'),
    '47130':('경북','경주시'),'47150':('경북','김천시'),
    '47170':('경북','안동시'),'47190':('경북','구미시'),
    '47210':('경북','영주시'),'47230':('경북','영천시'),
    '47250':('경북','상주시'),'47280':('경북','문경시'),
    '47290':('경북','경산시'),'47720':('경북','의성군'),
    '47730':('경북','청송군'),'47750':('경북','영양군'),
    '47760':('경북','영덕군'),'47770':('경북','청도군'),
    '47820':('경북','고령군'),'47830':('경북','성주군'),
    '47840':('경북','칠곡군'),'47850':('경북','예천군'),
    '47900':('경북','봉화군'),'47920':('경북','울진군'),
    '47930':('경북','울릉군'),
    # 경남
    '48121':('경남','창원시 의창구'),'48123':('경남','창원시 성산구'),
    '48125':('경남','창원시 마산합포구'),'48127':('경남','창원시 마산회원구'),
    '48129':('경남','창원시 진해구'),'48170':('경남','진주시'),
    '48220':('경남','통영시'),'48240':('경남','사천시'),
    '48250':('경남','김해시'),'48270':('경남','밀양시'),
    '48310':('경남','거제시'),'48330':('경남','양산시'),
    '48720':('경남','의령군'),'48730':('경남','함안군'),
    '48740':('경남','창녕군'),'48820':('경남','고성군'),
    '48840':('경남','남해군'),'48850':('경남','하동군'),
    '48860':('경남','산청군'),'48870':('경남','함양군'),
    '48880':('경남','거창군'),'48890':('경남','합천군'),
    # 제주도
    '50110':('제주도','제주시'),'50130':('제주도','서귀포시'),
}


# ════════════════════════════════════════
# 주소 파싱
# ════════════════════════════════════════

def build_reverse_map():
    """(sido_short, sigungu) → region_code 역방향 매핑"""
    rmap = {}
    for code, (sido, sigungu) in REGIONS.items():
        rmap[(sido, sigungu)] = code
    return rmap

REVERSE_REGION = build_reverse_map()


def parse_address(addr_str):
    parts = addr_str.strip().split()
    if len(parts) < 2:
        return None, None, None, None

    sido_full = parts[0]
    sido_short = SIDO_MAP.get(sido_full, sido_full)
    rest = parts[1:]

    for n in range(min(len(rest), 3), 0, -1):
        candidate = ' '.join(rest[:n])
        key = (sido_short, candidate)
        if key in REVERSE_REGION:
            dong = ' '.join(rest[n:]) if n < len(rest) else ''
            return sido_short, candidate, dong, REVERSE_REGION[key]

    # 세종시 특수 처리
    if sido_short == '세종시':
        dong = ' '.join(rest)
        return '세종시', '세종시', dong, REVERSE_REGION.get(('세종시', '세종시'))

    return sido_short, ' '.join(rest[:1]), ' '.join(rest[1:]), None


# ════════════════════════════════════════
# CSV 데이터 로딩
# ════════════════════════════════════════

def load_csv_file(filepath):
    """전월세 CSV 파일 로드 → (전세 리스트, 월세 리스트) 반환"""
    jeonse_items = []
    wolse_items = []
    encodings = ['euc-kr', 'cp949', 'utf-8-sig', 'utf-8']

    for enc in encodings:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                header_found = False
                for row in reader:
                    if not header_found:
                        if len(row) > 0 and row[0].strip('"') == 'NO':
                            header_found = True
                        continue

                    if len(row) < 14:
                        continue

                    rent_type = row[6].strip()  # 전월세구분

                    # 전용면적
                    try:
                        area = float(row[7].strip())
                    except:
                        continue
                    if area < MIN_AREA:
                        continue

                    # 보증금
                    deposit_str = row[10].replace(',', '').strip()
                    try:
                        deposit = int(deposit_str)
                    except:
                        continue

                    # 월세금
                    monthly_str = row[11].replace(',', '').strip()
                    try:
                        monthly = int(monthly_str)
                    except:
                        monthly = 0

                    # 주소 파싱
                    sido, sigungu, dong, region_code = parse_address(row[1])
                    if not region_code:
                        continue

                    # 계약년월
                    ym = row[8].strip()
                    deal_year = ym[:4] if len(ym) >= 6 else ''
                    deal_month = ym[4:6] if len(ym) >= 6 else ''
                    deal_day = row[9].strip()

                    # 층
                    floor_val = row[12].strip()
                    if floor_val == '-':
                        floor_val = ''

                    # 건축년도
                    build_year = row[13].strip() if len(row) > 13 else ''

                    area_pyeong = round(area / 3.3, 1)

                    if rent_type == '전세':
                        ppyeong = round((deposit / area) * 3.3)
                        jeonse_items.append({
                            'apt_name': row[5].strip(),
                            'sido': sido, 'sigungu': sigungu, 'dong': dong,
                            'area_m2': area, 'area_pyeong': area_pyeong,
                            'deposit': deposit, 'monthly': 0,
                            'price': deposit,
                            'price_per_pyeong': ppyeong,
                            'deal_year': deal_year, 'deal_month': deal_month,
                            'deal_day': deal_day, 'floor': floor_val,
                            'build_year': build_year, 'region_code': region_code
                        })
                    elif rent_type == '월세':
                        # 환산보증금 = 보증금 + (월세 × 12 / 전월세전환율)
                        converted = deposit + round(monthly * 12 / WOLSE_RATE)
                        ppyeong = round((converted / area) * 3.3)
                        wolse_items.append({
                            'apt_name': row[5].strip(),
                            'sido': sido, 'sigungu': sigungu, 'dong': dong,
                            'area_m2': area, 'area_pyeong': area_pyeong,
                            'deposit': deposit, 'monthly': monthly,
                            'price': converted,
                            'price_per_pyeong': ppyeong,
                            'deal_year': deal_year, 'deal_month': deal_month,
                            'deal_day': deal_day, 'floor': floor_val,
                            'build_year': build_year, 'region_code': region_code
                        })
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  ❌ 파일 읽기 실패 [{filepath}]: {e}")
            return [], []

    return jeonse_items, wolse_items


def load_all_csv():
    """data/csv_jeonse/ 의 모든 CSV → (전세 통합, 월세 통합) 반환"""
    csv_files = sorted(glob.glob(os.path.join(CSV_DIR, '*.csv')))
    if not csv_files:
        print(f"❌ {CSV_DIR}/ 디렉토리에 CSV 파일이 없습니다!")
        print(f"   rt.molit.go.kr에서 전월세 CSV를 다운받아 {CSV_DIR}/ 에 넣어주세요.")
        exit(1)

    print(f"📂 전월세 CSV 파일 {len(csv_files)}개 발견\n")

    all_jeonse = []
    all_wolse = []
    seen_j = set()
    seen_w = set()

    for filepath in csv_files:
        fname = os.path.basename(filepath)
        j_items, w_items = load_csv_file(filepath)

        # 중복 제거 - 전세
        new_j = 0
        for it in j_items:
            key = (it['apt_name'], it['region_code'], it['area_m2'],
                   it['deal_year'], it['deal_month'], it['deal_day'],
                   it['deposit'], it['floor'])
            if key not in seen_j:
                seen_j.add(key)
                all_jeonse.append(it)
                new_j += 1

        # 중복 제거 - 월세
        new_w = 0
        for it in w_items:
            key = (it['apt_name'], it['region_code'], it['area_m2'],
                   it['deal_year'], it['deal_month'], it['deal_day'],
                   it['deposit'], it['monthly'], it['floor'])
            if key not in seen_w:
                seen_w.add(key)
                all_wolse.append(it)
                new_w += 1

        print(f"  ✅ {fname}: 전세 {new_j}건 / 월세 {new_w}건 추가")

    print(f"\n  → 전세 총 {len(all_jeonse)}건, 월세 총 {len(all_wolse)}건 (중복 제거 후)\n")
    return all_jeonse, all_wolse


# ════════════════════════════════════════
# 공통 유틸
# ════════════════════════════════════════

def get_months(n):
    months = set()
    today = datetime.today()
    for i in range(n):
        d = today.replace(day=1) - timedelta(days=30*i)
        months.add(d.strftime('%Y%m'))
    return sorted(months)


def fp(p):
    b = p // 10000
    r = p % 10000
    return f"{b}억 {r:,}만" if b > 0 else f"{p:,}만"


# ════════════════════════════════════════
# 구별 TOP 10 JSON 생성
# ════════════════════════════════════════

def build_district_data(recent, alldata, months_6_set, outfile, label):
    """구별 TOP 10 JSON 생성"""
    print(f"── 전국 구별 TOP 10 생성 ({label}) ──")

    # 구별 그룹핑 (최근 6개월)
    by_district = defaultdict(list)
    for it in recent:
        key = f"{it['sido']}|{it['sigungu']}"
        by_district[key].append(it)

    # 구별 TOP 10
    top10_map = {}
    for key, items in by_district.items():
        best = {}
        for it in items:
            aname = it['apt_name']
            if aname not in best or it['price_per_pyeong'] > best[aname]['price_per_pyeong']:
                best[aname] = it
        t10 = sorted(best.values(), key=lambda x: x['price_per_pyeong'], reverse=True)[:10]
        if t10:
            top10_map[key] = t10

    # 전체 월별 라벨
    all_months_set = set()
    for it in alldata:
        ym = f"{it['deal_year']}.{it['deal_month'].zfill(2)}"
        all_months_set.add(ym)
    all_months = sorted(all_months_set)

    # 구별 전체 데이터
    district_all = defaultdict(list)
    for it in alldata:
        key = f"{it['sido']}|{it['sigungu']}"
        district_all[key].append(it)

    result = {
        "updated": datetime.now().strftime('%Y.%m.%d %H:%M'),
        "labels": all_months,
        "data": {}
    }

    for key, t10 in top10_map.items():
        all_items = district_all[key]

        # 아파트별 월평균 평당가
        apt_monthly = defaultdict(lambda: defaultdict(list))
        for it in all_items:
            ym = f"{it['deal_year']}.{it['deal_month'].zfill(2)}"
            apt_monthly[it['apt_name']][ym].append(it['price_per_pyeong'])

        series = []
        for apt in t10:
            vals = []
            for m in all_months:
                if m in apt_monthly[apt['apt_name']]:
                    v = apt_monthly[apt['apt_name']][m]
                    vals.append(round(sum(v) / len(v)))
                else:
                    vals.append(None)
            series.append(vals)

        # 6개월 거래 건수
        deal_count = sum(
            1 for it in all_items
            if f"{it['deal_year']}{it['deal_month'].zfill(2)}" in months_6_set
        )

        avg_pp = round(sum(it['price_per_pyeong'] for it in t10) / len(t10))

        result["data"][key] = {
            "top10": [{
                "name": it['apt_name'],
                "dong": it['dong'],
                "area_m2": it['area_m2'],
                "area_pyeong": it['area_pyeong'],
                "price": it['price'],
                "deposit": it['deposit'],
                "monthly": it['monthly'],
                "ppyeong": it['price_per_pyeong'],
                "date": f"{it['deal_year']}.{it['deal_month'].zfill(2)}.{it['deal_day'].zfill(2)}",
                "floor": it['floor'],
                "build_year": it['build_year']
            } for it in t10],
            "series": series,
            "avg": avg_pp,
            "deals": deal_count
        }

    outpath = os.path.join(DATA_DIR, outfile)
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)

    fsize = os.path.getsize(outpath) / 1024
    print(f"  → {len(top10_map)}개 지역 → {outpath} ({fsize:.0f}KB)")


# ════════════════════════════════════════
# 메인 실행
# ════════════════════════════════════════

def main():
    print("=" * 60)
    print("  전국 아파트 전월세 대시보드 (CSV 버전)")
    print("=" * 60 + "\n")

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)

    # ── Step 1: CSV 데이터 로드 ──
    print("Step 1: 전월세 CSV 데이터 로드\n")
    all_jeonse, all_wolse = load_all_csv()

    # ── 최근 6개월 데이터 분리 ──
    months_6 = get_months(6)
    months_6_set = set(months_6)

    recent_jeonse = [
        it for it in all_jeonse
        if f"{it['deal_year']}{it['deal_month'].zfill(2)}" in months_6_set
    ]
    recent_wolse = [
        it for it in all_wolse
        if f"{it['deal_year']}{it['deal_month'].zfill(2)}" in months_6_set
    ]

    print(f"  전세 전체: {len(all_jeonse)}건 / 최근 6개월: {len(recent_jeonse)}건")
    print(f"  월세 전체: {len(all_wolse)}건 / 최근 6개월: {len(recent_wolse)}건\n")

    # ── Step 2: 대시보드 JSON 생성 ──
    print("Step 2: 대시보드 생성\n")

    if recent_jeonse:
        build_district_data(recent_jeonse, all_jeonse, months_6_set,
                            outfile='district_top10_jeonse.json', label='전세')
    else:
        print("  ⚠️ 전세 데이터 없음")

    if recent_wolse:
        build_district_data(recent_wolse, all_wolse, months_6_set,
                            outfile='district_top10_wolse.json', label='월세')
    else:
        print("  ⚠️ 월세 데이터 없음")

    print("\n" + "=" * 60)
    print("  ✅ 전월세 대시보드 생성 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()

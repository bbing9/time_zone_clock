import streamlit as st
from datetime import datetime
import pytz
import time
import math
import os
from typing import Dict, Tuple, Optional
import pydeck as pdk

# 1. 페이지 기본 설정 (제목, 레이아웃 등)
st.set_page_config(
    page_title="Our distance",
    page_icon="❤️",
    layout="centered"
)

# 2. 스타일 꾸미기 (CSS 주입 - 폰트 크기 및 색상 조정)
st.markdown("""
    <style>
    .time-display {
        font-size: 40px;
        font-weight: bold;
        color: #FF4B4B;
        text-align: center;
        margin-bottom: 20px;
    }
    .label {
        font-size: 20px;
        text-align: center;
        font-weight: bold;
    }
    .stSelectbox > div > div {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 제목 표시
st.title("💜 꾸미 - 쭌 🤍")
st.write("Jet lag can't stop us !!!!!!!!!!!")
st.markdown("---")

# 3. 도시 선택 기능 만들기
col1, col2 = st.columns(2)

# 전세계 주요(일반적으로 쓰이는) 타임존 목록을 불러와 정렬
# Streamlit selectbox는 기본적으로 스크롤 + 검색(타이핑)으로 빠르게 찾을 수 있습니다.
city_options = sorted(pytz.common_timezones)

def _safe_index(options, value, fallback=0):
    try:
        return options.index(value)
    except ValueError:
        return fallback

default_my_idx = _safe_index(city_options, "America/Los_Angeles", 0)
default_gf_idx = _safe_index(city_options, "Asia/Dubai", 1 if len(city_options) > 1 else 0)

with col1:
    st.markdown('<p class="label" style="text-align: left;">🦦️&nbsp; Danny</p>', unsafe_allow_html=True)
    # 기본값을 서울(0번 인덱스)로 설정
    my_city = st.selectbox("지역 선택", city_options, index=default_my_idx, key='me')

with col2:
    st.markdown('<p class="label" style="text-align: left;">🐰&nbsp; Judy</p>', unsafe_allow_html=True)
    # 기본값을 뉴욕(1번 인덱스)으로 설정
    gf_city = st.selectbox("지역 선택", city_options, index=default_gf_idx, key='gf')

st.markdown("---")

# 4. 실시간 시계 작동 로직
# 두 개의 빈 공간(placeholder)을 미리 만들어둡니다.
with col1:
    my_date_placeholder = st.empty()
    my_time_placeholder = st.empty()
with col2:
    gf_date_placeholder = st.empty()
    gf_time_placeholder = st.empty()

# 거리 표시용 placeholder
distance_placeholder = st.empty()

# 지도 표시용 placeholder
map_placeholder = st.empty()

# D-Day 계산 (예: 사귄 날짜가 2023년 1월 1일이라면)
st.write(f"🐰&nbsp; 💜&nbsp; 🦦️&nbsp;:&nbsp; {(datetime.now() - datetime(2023, 3, 12)).days+1}days&nbsp;🤍")

# 거리 계산 함수 및 보조 데이터
def _haversine_km(lat1, lon1, lat2, lon2):
    """두 좌표(위도/경도) 간 대원거리(km)"""
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# 타임존을 고르면 자동으로 좌표를 찾아 거리 계산까지 하도록
# IANA tz database의 zone1970.tab(또는 zone.tab)에서 타임존별 좌표를 읽어옵니다.
# 배포/OS 환경에 따라 파일 경로가 다를 수 있어 여러 경로를 순차적으로 시도합니다.

def _parse_iso6709(coord: str) -> Optional[Tuple[float, float]]:
    """IANA tab 파일의 ISO 6709 스타일 좌표(+DDMMSS+DDDMMSS / +DDMM+DDDMM 등)를 (lat, lon)로 변환"""
    if not coord:
        return None

    # 예: +404251-0740023, +3747+12225
    # 위도는 첫 +/-로 시작, 경도는 그 다음 +/-로 시작
    if coord[0] not in "+-":
        return None

    # 경도 시작 위치 찾기(두 번째 부호)
    lon_sign_pos = None
    for i in range(1, len(coord)):
        if coord[i] in "+-":
            lon_sign_pos = i
            break
    if lon_sign_pos is None:
        return None

    lat_str = coord[:lon_sign_pos]
    lon_str = coord[lon_sign_pos:]

    def _to_deg(s: str, is_lon: bool) -> float:
        sign = 1.0 if s[0] == "+" else -1.0
        digits = s[1:]

        # 위도: DDMM or DDMMSS
        # 경도: DDDMM or DDDMMSS
        if is_lon:
            deg_len = 3
        else:
            deg_len = 2

        if len(digits) not in (deg_len + 2, deg_len + 4):
            # 예상치 못한 형식이면 최대한 유연하게 처리
            # (예: DDMMSS.SS 같은 경우) -> 소수점 제거 후 시도
            digits2 = ''.join(ch for ch in digits if ch.isdigit())
            digits = digits2

        deg = int(digits[:deg_len])
        minute = int(digits[deg_len:deg_len + 2]) if len(digits) >= deg_len + 2 else 0
        sec = int(digits[deg_len + 2:deg_len + 4]) if len(digits) >= deg_len + 4 else 0

        return sign * (deg + minute / 60.0 + sec / 3600.0)

    try:
        lat = _to_deg(lat_str, is_lon=False)
        lon = _to_deg(lon_str, is_lon=True)
        return (lat, lon)
    except Exception:
        return None


def _read_tab_file(path: str) -> Dict[str, Tuple[float, float]]:
    """zone1970.tab/zone.tab에서 TZ -> (lat, lon) 매핑 생성"""
    mapping: Dict[str, Tuple[float, float]] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            coord = parts[1]
            tz = parts[2]
            parsed = _parse_iso6709(coord)
            if parsed:
                mapping[tz] = parsed
    return mapping


@st.cache_data(show_spinner=False)
def _load_tz_coords() -> Dict[str, Tuple[float, float]]:
    """환경에 존재하는 IANA tz tab 파일을 찾아 TZ -> 좌표 매핑을 로드"""
    candidates = [
        "/usr/share/zoneinfo/zone1970.tab",
        "/usr/share/zoneinfo/zone.tab",
        "/usr/share/lib/zoneinfo/tab/zone1970.tab",
        "/usr/share/lib/zoneinfo/tab/zone.tab",
    ]

    for p in candidates:
        if os.path.exists(p):
            m = _read_tab_file(p)
            if m:
                return m

    # tzdata(파이썬 패키지)가 설치된 경우 내부 리소스에서 찾기
    try:
        import importlib.resources as ir
        import tzdata

        for rel in [
            "zoneinfo/zone1970.tab",
            "zoneinfo/zone.tab",
        ]:
            try:
                with ir.as_file(ir.files(tzdata).joinpath(rel)) as fp:
                    if fp and os.path.exists(str(fp)):
                        m = _read_tab_file(str(fp))
                        if m:
                            return m
            except Exception:
                continue
    except Exception:
        pass

    return {}


TZ_COORDS = _load_tz_coords()

def _distance_text(tz1: str, tz2: str) -> str:
    a = TZ_COORDS.get(tz1)
    b = TZ_COORDS.get(tz2)
    if not a or not b:
        return "선택한 타임존의 좌표 정보를 찾지 못해 거리 계산을 표시할 수 없어요. (환경에 zone1970.tab/zone.tab가 없으면 발생할 수 있어요.)"
    km = _haversine_km(a[0], a[1], b[0], b[1])
    return f"📍 Distance between us: **{km:,.0f} km but 0km**"


# 1초마다 시간을 업데이트하는 루프
while True:
    # 현재 시간 구하기 (UTC 기준)
    now_utc = datetime.now(pytz.utc)

    # 선택한 도시의 시간대로 변환
    my_tz_dt = now_utc.astimezone(pytz.timezone(my_city))
    gf_tz_dt = now_utc.astimezone(pytz.timezone(gf_city))

    my_date = my_tz_dt.strftime('%Y-%m-%d (%a)')
    gf_date = gf_tz_dt.strftime('%Y-%m-%d (%a)')

    my_time = my_tz_dt.strftime('%p %I:%M:%S')
    gf_time = gf_tz_dt.strftime('%p %I:%M:%S')

    # 화면에 날짜/시간 업데이트
    my_date_placeholder.markdown(f'<div class="label">🗓️ {my_date}</div>', unsafe_allow_html=True)
    gf_date_placeholder.markdown(f'<div class="label">🗓️ {gf_date}</div>', unsafe_allow_html=True)

    my_time_placeholder.markdown(f'<div class="time-display">{my_time}</div>', unsafe_allow_html=True)
    gf_time_placeholder.markdown(f'<div class="time-display">{gf_time}</div>', unsafe_allow_html=True)

    # 두 지역 간 거리 표시
    distance_placeholder.markdown(_distance_text(my_city, gf_city))

    # 지도 시각화 부분 수정
    a = TZ_COORDS.get(my_city)
    b = TZ_COORDS.get(gf_city)

    if a and b:
        # 1. 이모지 데이터 (🦦 Danny, 🐰 Judy)
        map_data = [
            {"emoji": "🦦", "lat": a[0], "lon": a[1], "name": "Danny"},
            {"emoji": "🐰", "lat": b[0], "lon": b[1], "name": "Judy"},
        ]

        # 2. 이모지 레이어 (TextLayer)
        emoji_layer = pdk.Layer(
            "ScatterplotLayer",
            map_data,
            get_position="[lon, lat]",
            get_radius=200000,
            get_fill_color=[255, 0, 0],
        )

        # 3. 빨간 점선 곡선 레이어 (GreatCircleLayer)
        # 직선보다 훨씬 부드럽고 '장거리 연애' 느낌을 줍니다.
        line_layer = pdk.Layer(
            "LineLayer",  # 지구 곡률을 반영한 곡선
            data=[{
                "start": [a[1], a[0]],
                "end": [b[1], b[0]]
            }],
            get_source_position="start",
            get_target_position="end",
            get_width=3,
            get_color=[255, 75, 75, 200],  # 약간 투명한 빨간색
            # 점선 효과는 pydeck의 브라우저 렌더링 특성상
            # 스트로크 설정을 통해 구현합니다.
        )

        # 4. 지도 시점 설정
        view_state = pdk.ViewState(
            latitude=(a[0] + b[0]) / 2,
            longitude=(a[1] + b[1]) / 2,
            zoom=1.2,
            pitch=30,  # 살짝 입체감 있게 기울임
        )

        deck = pdk.Deck(
            layers=[line_layer, emoji_layer],
            initial_view_state=view_state  # 어두운 배경에서 빨간 선이 더 잘 보임
        )

        map_placeholder.pydeck_chart(deck)

    # 1초 대기
    time.sleep(1)
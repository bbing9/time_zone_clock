import streamlit as st
from datetime import datetime
import pytz
import time
import math
import os
from typing import Dict, Tuple, Optional
import pydeck as pdk

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="Our distance",
    page_icon="❤️",
    layout="centered"
)

# 2. 스타일 꾸미기 (CSS)
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
    /* 셀렉트박스 중앙 정렬 */
    .stSelectbox > div > div {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("💜 꾸미 - 쭌 🤍")
st.write("Jet lag can't stop us !!!!!!!!!!!")
st.markdown("---")

# 3. 도시 선택 기능
col1, col2 = st.columns(2)
city_options = sorted(pytz.common_timezones)

def _safe_index(options, value, fallback=0):
    try:
        return options.index(value)
    except ValueError:
        return fallback

# 기본값 설정
default_my_idx = _safe_index(city_options, "Asia/Seoul", 0)
default_gf_idx = _safe_index(city_options, "America/New_York", 1 if len(city_options) > 1 else 0)

with col1:
    st.markdown('<p class="label">🦦️&nbsp; Danny</p>', unsafe_allow_html=True)
    my_city = st.selectbox("지역 선택", city_options, index=default_my_idx, key='me')

with col2:
    st.markdown('<p class="label">🐰&nbsp; Judy</p>', unsafe_allow_html=True)
    gf_city = st.selectbox("지역 선택", city_options, index=default_gf_idx, key='gf')

st.markdown("---")

# 4. 화면 구성 요소(Placeholder) 준비
with col1:
    my_date_placeholder = st.empty()
    my_time_placeholder = st.empty()
with col2:
    gf_date_placeholder = st.empty()
    gf_time_placeholder = st.empty()

distance_placeholder = st.empty()
map_placeholder = st.empty()

# D-Day 계산
st.write(f"🐰&nbsp; 💜&nbsp; 🦦️&nbsp;:&nbsp; {(datetime.now() - datetime(2023, 3, 12)).days+1}days&nbsp;🤍")

# --- 내부 로직 함수들 (좌표 로딩 및 거리 계산) ---

def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _parse_iso6709(coord: str) -> Optional[Tuple[float, float]]:
    if not coord: return None
    if coord[0] not in "+-": return None
    lon_sign_pos = None
    for i in range(1, len(coord)):
        if coord[i] in "+-":
            lon_sign_pos = i
            break
    if lon_sign_pos is None: return None
    lat_str = coord[:lon_sign_pos]
    lon_str = coord[lon_sign_pos:]

    def _to_deg(s: str, is_lon: bool) -> float:
        sign = 1.0 if s[0] == "+" else -1.0
        digits = ''.join(ch for ch in s[1:] if ch.isdigit())
        deg_len = 3 if is_lon else 2
        if len(digits) < deg_len: return 0.0
        deg = int(digits[:deg_len])
        minute = int(digits[deg_len:deg_len + 2]) if len(digits) >= deg_len + 2 else 0
        sec = int(digits[deg_len + 2:deg_len + 4]) if len(digits) >= deg_len + 4 else 0
        return sign * (deg + minute / 60.0 + sec / 3600.0)

    try:
        return (_to_deg(lat_str, False), _to_deg(lon_str, True))
    except:
        return None

def _read_tab_file(path: str) -> Dict[str, Tuple[float, float]]:
    mapping = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip() or line.startswith("#"): continue
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                parsed = _parse_iso6709(parts[1])
                if parsed: mapping[parts[2]] = parsed
    return mapping

@st.cache_data(show_spinner=False)
def _load_tz_coords() -> Dict[str, Tuple[float, float]]:
    candidates = [
        "/usr/share/zoneinfo/zone1970.tab", "/usr/share/zoneinfo/zone.tab",
        "/usr/share/lib/zoneinfo/tab/zone1970.tab", "/usr/share/lib/zoneinfo/tab/zone.tab",
    ]
    for p in candidates:
        if os.path.exists(p):
            m = _read_tab_file(p)
            if m: return m
    try:
        import importlib.resources as ir
        import tzdata
        for rel in ["zoneinfo/zone1970.tab", "zoneinfo/zone.tab"]:
            try:
                with ir.as_file(ir.files(tzdata).joinpath(rel)) as fp:
                    if fp and os.path.exists(str(fp)):
                        m = _read_tab_file(str(fp))
                        if m: return m
            except: continue
    except: pass
    return {}

TZ_COORDS = _load_tz_coords()

def _distance_text(tz1, tz2):
    a = TZ_COORDS.get(tz1)
    b = TZ_COORDS.get(tz2)
    if not a or not b: return "좌표 정보를 찾을 수 없습니다."
    km = _haversine_km(a[0], a[1], b[0], b[1])
    return f"📍 Distance between two: **{km:,.0f} km**"

# 5. 루프 실행 (시계 및 지도 업데이트)
while True:
    now_utc = datetime.now(pytz.utc)
    my_tz_dt = now_utc.astimezone(pytz.timezone(my_city))
    gf_tz_dt = now_utc.astimezone(pytz.timezone(gf_city))

    # 날짜/시간 업데이트
    my_date_placeholder.markdown(f'<div class="label">🗓️ {my_tz_dt.strftime("%Y-%m-%d (%a)")}</div>', unsafe_allow_html=True)
    gf_date_placeholder.markdown(f'<div class="label">🗓️ {gf_tz_dt.strftime("%Y-%m-%d (%a)")}</div>', unsafe_allow_html=True)
    my_time_placeholder.markdown(f'<div class="time-display">{my_tz_dt.strftime("%p %I:%M:%S")}</div>', unsafe_allow_html=True)
    gf_time_placeholder.markdown(f'<div class="time-display">{gf_tz_dt.strftime("%p %I:%M:%S")}</div>', unsafe_allow_html=True)

    # 거리 텍스트 업데이트
    distance_placeholder.markdown(_distance_text(my_city, gf_city))

    # --- 지도 그리기 핵심 부분 ---
    a = TZ_COORDS.get(my_city)
    b = TZ_COORDS.get(gf_city)

    if a and b:
        # 이모지 데이터
        map_data = [
            {"emoji": "🦦", "lat": a[0], "lon": a[1]},
            {"emoji": "🐰", "lat": b[0], "lon": b[1]},
        ]

        # 1. 이모지 레이어 (크게 설정)
        emoji_layer = pdk.Layer(
            "TextLayer",
            map_data,
            get_position="[lon, lat]",
            get_text="emoji",
            get_size=60,         # 이모지 크기 키움
            size_units="pixels",
            get_color=[255, 255, 255],
            get_alignment_baseline="'bottom'", # 좌표 위에 얹히도록
        )

        # 2. 곡선 레이어 (GreatCircleLayer - 붉은색)
        # 지도에서 점선 곡선은 구현이 복잡하여, 가장 예쁜 '비행 경로(Solid Arc)' 스타일로 적용했습니다.
        arc_layer = pdk.Layer(
            "GreatCircleLayer",
            data=[{
                "from": [a[1], a[0]],
                "to": [b[1], b[0]]
            }],
            get_source_position="from",
            get_target_position="to",
            get_source_color=[255, 50, 50], # 시작점 빨강
            get_target_color=[255, 50, 50], # 도착점 빨강
            get_width=5,                    # 선 두께
            pickable=True,
        )

        # 3. 지도 뷰 설정
        view_state = pdk.ViewState(
            latitude=(a[0] + b[0]) / 2,
            longitude=(a[1] + b[1]) / 2,
            zoom=1,     # 줌 아웃해서 전체 경로가 보이게
            pitch=30,   # 약간의 입체감
        )

        # 4. 덱 생성 (Dark Mode 스타일 적용)
        deck = pdk.Deck(
            layers=[arc_layer, emoji_layer],
            initial_view_state=view_state,
          # 어두운 지도 배경
        )

        map_placeholder.pydeck_chart(deck)

    time.sleep(1)
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
from openai import OpenAI


# =========================
# App Constants
# =========================
APP_NAME = "MoodPick (무드픽)"
APP_TAGLINE = "기분과 상황만 고르면, 오늘의 선택을 대신해주는 감성 추천 앱"
HISTORY_FILE = Path(__file__).with_name("moodpick_history.json")

MOODS = ["피곤함", "우울함", "설렘", "무기력"]
WEATHERS = ["맑음", "비", "흐림"]
VIBES = ["혼자", "친구와", "데이트", "집에 있음"]
TIME_BUDGETS = ["짧게", "보통", "여유 있음"]

THEME = {
    "mood": {
        "피곤함": {"emoji": "😮‍💨", "accent": "#6B7280"},
        "우울함": {"emoji": "🌧️", "accent": "#3B82F6"},
        "설렘": {"emoji": "✨", "accent": "#EC4899"},
        "무기력": {"emoji": "🫥", "accent": "#8B5CF6"},
    },
    "weather": {"맑음": {"emoji": "☀️"}, "비": {"emoji": "☔"}, "흐림": {"emoji": "☁️"}},
    "vibe": {"혼자": {"emoji": "🎧"}, "친구와": {"emoji": "🫶"}, "데이트": {"emoji": "🌹"}, "집에 있음": {"emoji": "🏠"}},
    "time": {"짧게": {"emoji": "⏱️"}, "보통": {"emoji": "🕒"}, "여유 있음": {"emoji": "🗓️"}},
}

DEFAULT_MODEL = "gpt-4o-2024-08-06"

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"


# =========================
# Utilities: History
# =========================
def load_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(items: List[Dict[str, Any]]) -> None:
    HISTORY_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_history_entry(entry: Dict[str, Any]) -> None:
    history = load_history()
    history.insert(0, entry)
    save_history(history)


# =========================
# API Key Handling
# =========================
def get_secret(key_name: str) -> Optional[str]:
    try:
        val = st.secrets.get(key_name, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return None


def get_openai_key() -> Optional[str]:
    key = get_secret("OPENAI_API_KEY")
    if not key:
        key = os.getenv("OPENAI_API_KEY", "").strip() or None
    if not key:
        key = st.session_state.get("openai_key", None)
    return key.strip() if isinstance(key, str) and key.strip() else None


def get_tmdb_key() -> Optional[str]:
    key = get_secret("TMDB_API_KEY")
    if not key:
        key = os.getenv("TMDB_API_KEY", "").strip() or None
    if not key:
        key = st.session_state.get("tmdb_key", None)
    return key.strip() if isinstance(key, str) and key.strip() else None


def ensure_openai_key_or_stop() -> str:
    key = get_openai_key()
    if not key:
        st.error(
            "OpenAI API Key가 필요해요.\n\n"
            "- 사이드바에서 OpenAI API Key를 입력하거나\n"
            "- `.streamlit/secrets.toml`에 `OPENAI_API_KEY = \"sk-...\"` 추가하거나\n"
            "- 환경변수 `OPENAI_API_KEY`를 설정해주세요."
        )
        st.stop()
    return key


# =========================
# OpenAI: Prompt + Call
# =========================
def build_user_prompt(
    mood: str,
    weather: str,
    vibe: str,
    time_budget: str,
    extra_constraints: str = "",
) -> str:
    base = f"""
상황:
- 현재 기분: {mood}
- 날씨: {weather}
- 분위기/상황: {vibe}
- 시간 제약: {time_budget}

요청:
위 상황에서 "지금 이 순간에 어울리는" 소규모 일상 활동을 3개 이내로 추천해줘.
각 추천은 과하지 않고 현실적으로 바로 실행 가능한 것으로.
추천은 한국어로, 너무 길지 않게.
""".strip()

    if extra_constraints.strip():
        base += f"\n\n추가 제약/선호:\n{extra_constraints.strip()}\n"

    # TMDB 검색 fallback용 키워드 (작품 제목이 아니라 분위기/장르에 가까운 일반 단어)
    base += "\n\n추가 요청: 각 추천마다 TMDB 검색에 쓸 '검색 키워드'를 1~3개 단어(한국어 또는 영어)로 포함해줘."
    return base


def recommendations_json_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {"type": "string"},
            "tone": {"type": "string"},
            "recommendations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "one_liner": {"type": "string"},
                        "reason": {"type": "string"},
                        "how_to_start": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 3,
                            "items": {"type": "string"},
                        },
                        "tmdb_keywords": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 3,
                            "items": {"type": "string"},
                            "description": "TMDB 검색용 키워드 1~3개",
                        },
                    },
                    "required": ["title", "one_liner", "reason", "how_to_start", "tmdb_keywords"],
                },
            },
        },
        "required": ["headline", "tone", "recommendations"],
    }


def call_openai_recommendations(
    api_key: str,
    model: str,
    mood: str,
    weather: str,
    vibe: str,
    time_budget: str,
    extra_constraints: str,
) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)

    system_instructions = (
        "너는 사용자의 감정과 상황을 이해하고, 과도하지 않으면서 바로 실행 가능한 "
        "소규모 일상 활동 선택지를 제안하는 라이프스타일 추천 도우미다. "
        "항상 3개 이내로 추천하고, 각각에 부담 없는 이유를 한 문장으로 덧붙여라. "
        "TMDB 검색 키워드는 너무 구체적인 고유명사보다, 일반 키워드를 선호한다."
    )

    user_prompt = build_user_prompt(mood, weather, vibe, time_budget, extra_constraints)

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "moodpick_recommendations",
                "schema": recommendations_json_schema(),
                "strict": True,
            }
        },
    )
    return json.loads(resp.output_text)


# =========================
# TMDB (Discover-first + Weighting + TV Toggle)
# =========================
# TMDB Genre IDs (movie/tv 공통으로 많이 쓰임)
GENRE = {
    "action": 28,
    "adventure": 12,
    "animation": 16,
    "comedy": 35,
    "crime": 80,
    "documentary": 99,
    "drama": 18,
    "family": 10751,
    "fantasy": 14,
    "history": 36,
    "horror": 27,
    "music": 10402,
    "mystery": 9648,
    "romance": 10749,
    "scifi": 878,
    "thriller": 53,
    "war": 10752,
}

# "가중치"를 단순화해서: (primary_genres, secondary_genres)로 구성하고
# primary를 먼저 시도 → 부족하면 secondary 섞기
MOOD_TO_GENRES_WEIGHTED = {
    "피곤함": ([GENRE["comedy"], GENRE["animation"], GENRE["family"]], [GENRE["fantasy"], GENRE["music"], GENRE["drama"]]),
    "우울함": ([GENRE["drama"], GENRE["music"]], [GENRE["comedy"], GENRE["romance"], GENRE["mystery"]]),
    "설렘": ([GENRE["romance"], GENRE["comedy"], GENRE["fantasy"]], [GENRE["drama"], GENRE["adventure"]]),
    "무기력": ([GENRE["adventure"], GENRE["action"], GENRE["comedy"]], [GENRE["thriller"], GENRE["fantasy"], GENRE["crime"]]),
}

# vibe(상황)로 장르를 보정(가중치 느낌)
VIBE_GENRE_BOOST = {
    "혼자": [GENRE["mystery"], GENRE["drama"]],
    "친구와": [GENRE["comedy"], GENRE["adventure"]],
    "데이트": [GENRE["romance"], GENRE["comedy"]],
    "집에 있음": [GENRE["animation"], GENRE["family"], GENRE["documentary"]],
}

WEATHER_GENRE_BOOST = {
    "맑음": [GENRE["adventure"], GENRE["comedy"]],
    "비": [GENRE["drama"], GENRE["mystery"]],
    "흐림": [GENRE["fantasy"], GENRE["thriller"]],
}


def tmdb_discover(
    api_key: str,
    media: str,  # "movie" or "tv"
    genres: List[int],
    language: str = "ko-KR",
    region: str = "KR",
    vote_count_gte: int = 150,
    page: int = 1,
) -> List[Dict[str, Any]]:
    endpoint = f"{TMDB_BASE}/discover/{media}"
    params = {
        "api_key": api_key,
        "language": language,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "with_genres": ",".join(map(str, genres)) if genres else "",
        "vote_count.gte": vote_count_gte,
        "page": page,
    }
    # movie 전용 region 파라미터 (tv는 무시해도 되지만 넣어도 문제는 거의 없음)
    if region:
        params["region"] = region

    try:
        r = requests.get(endpoint, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results = []
    for item in (data.get("results") or []):
        title = item.get("title") or item.get("name") or "Untitled"
        overview = item.get("overview") or ""
        poster_path = item.get("poster_path")
        poster_url = f"{TMDB_IMG}{poster_path}" if poster_path else None
        results.append(
            {
                "media_type": media,
                "title": title,
                "overview": overview,
                "poster_url": poster_url,
                "id": item.get("id"),
            }
        )
    return results


def tmdb_search_multi(api_key: str, query: str, language: str = "ko-KR") -> List[Dict[str, Any]]:
    try:
        r = requests.get(
            f"{TMDB_BASE}/search/multi",
            params={"api_key": api_key, "query": query, "language": language, "include_adult": "false"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    results = []
    for item in (data.get("results") or []):
        media_type = item.get("media_type")
        if media_type not in ("movie", "tv"):  # person은 제외(원하면 포함 가능)
            continue
        title = item.get("title") or item.get("name") or "Untitled"
        overview = item.get("overview") or ""
        poster_path = item.get("poster_path") or item.get("profile_path")
        poster_url = f"{TMDB_IMG}{poster_path}" if poster_path else None
        results.append(
            {
                "media_type": media_type,
                "title": title,
                "overview": overview,
                "poster_url": poster_url,
                "id": item.get("id"),
            }
        )
    return results


def build_weighted_genre_lists(mood: str, vibe: str, weather: str) -> Tuple[List[int], List[int]]:
    """
    primary, secondary 장르 리스트 생성
    - mood 기반 primary/secondary
    - vibe/weather는 primary에 우선 가볍게 섞어 '가중치' 느낌을 줌
    """
    base_primary, base_secondary = MOOD_TO_GENRES_WEIGHTED.get(mood, ([GENRE["comedy"], GENRE["drama"]], [GENRE["romance"]]))

    boosts = []
    boosts += VIBE_GENRE_BOOST.get(vibe, [])
    boosts += WEATHER_GENRE_BOOST.get(weather, [])

    # primary는 base_primary + boosts(중복 제거)
    primary = []
    seen = set()
    for g in (base_primary + boosts):
        if g not in seen:
            seen.add(g)
            primary.append(g)

    # secondary는 base_secondary + (base_primary 일부) + boosts 일부 (중복 제거)
    secondary = []
    seen2 = set()
    for g in (base_secondary + base_primary + boosts):
        if g not in seen2:
            seen2.add(g)
            secondary.append(g)

    return primary, secondary


def dedupe_items(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for x in items:
        key = (x.get("media_type"), x.get("id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
        if len(out) >= limit:
            break
    return out


def tmdb_get_recommendations_weighted(
    api_key: str,
    content_mode: str,  # "movie" | "tv" | "both"
    mood: str,
    vibe: str,
    weather: str,
    fallback_query: str,
    language: str,
    region: str,
    vote_count_gte: int,
    n_items: int,
    use_search_fallback: bool,
) -> List[Dict[str, Any]]:
    """
    1) Discover-first (primary genres)
    2) 부족하면 Discover (secondary genres)
    3) still 부족하면 Search fallback (ko→en)
    """
    primary, secondary = build_weighted_genre_lists(mood, vibe, weather)

    media_list = []
    if content_mode == "both":
        media_list = ["movie", "tv"]
    else:
        media_list = [content_mode]

    collected: List[Dict[str, Any]] = []

    # 1) primary discover
    for media in media_list:
        collected += tmdb_discover(
            api_key=api_key,
            media=media,
            genres=primary,
            language=language,
            region=region,
            vote_count_gte=vote_count_gte,
            page=1,
        )

    collected = dedupe_items(collected, limit=n_items)
    if len(collected) >= n_items:
        return collected

    # 2) secondary discover
    more: List[Dict[str, Any]] = []
    for media in media_list:
        more += tmdb_discover(
            api_key=api_key,
            media=media,
            genres=secondary,
            language=language,
            region=region,
            vote_count_gte=max(0, vote_count_gte - 50),  # 조금 완화
            page=1,
        )
    collected = dedupe_items(collected + more, limit=n_items)
    if len(collected) >= n_items:
        return collected

    # 3) Search fallback
    if use_search_fallback:
        searched = tmdb_search_multi(api_key, fallback_query, language=language)
        if language != "en-US":
            searched += tmdb_search_multi(api_key, fallback_query, language="en-US")
        collected = dedupe_items(collected + searched, limit=n_items)

    return collected


# =========================
# UI Helpers
# =========================
def apply_dynamic_style(accent_hex: str) -> None:
    st.markdown(
        f"""
<style>
:root {{
  --moodpick-accent: {accent_hex};
}}
div.stButton > button {{
  border: 1px solid rgba(0,0,0,0.08);
}}
div.stButton > button:hover {{
  border-color: var(--moodpick-accent);
}}
.moodpick-card {{
  border: 1px solid rgba(0,0,0,0.08);
  border-left: 6px solid var(--moodpick-accent);
  border-radius: 14px;
  padding: 14px 14px 12px 14px;
  margin: 10px 0px;
  background: rgba(0,0,0,0.015);
}}
.moodpick-title {{
  font-size: 1.05rem;
  font-weight: 700;
  margin-bottom: 6px;
}}
.moodpick-sub {{
  color: rgba(0,0,0,0.70);
  margin-bottom: 10px;
}}
.moodpick-reason {{
  color: rgba(0,0,0,0.78);
  margin-bottom: 10px;
}}
.moodpick-chip {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(0,0,0,0.05);
  margin-right: 6px;
  font-size: 0.85rem;
}}
.tmdb-row {{
  border-top: 1px dashed rgba(0,0,0,0.12);
  margin-top: 10px;
  padding-top: 10px;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_tmdb_items(items: List[Dict[str, Any]]) -> None:
    if not items:
        st.caption("TMDB에서 추천을 가져오지 못했어요(키/네트워크/설정 확인).")
        return

    for item in items:
        cols = st.columns([1, 3], gap="small")
        with cols[0]:
            if item.get("poster_url"):
                st.image(item["poster_url"], use_container_width=True)
            else:
                st.caption("포스터 없음")
        with cols[1]:
            mt = item.get("media_type", "")
            mt_label = {"movie": "영화", "tv": "TV"}.get(mt, mt)
            st.markdown(f"**{item.get('title','Untitled')}**  ·  {mt_label}")
            overview = item.get("overview") or ""
            if overview:
                st.caption(overview[:220] + ("…" if len(overview) > 220 else ""))
            else:
                st.caption("요약이 없어요.")


def render_reco_cards(
    reco_payload: Dict[str, Any],
    mood: str,
    weather: str,
    vibe: str,
    time_budget: str,
    tmdb_key: Optional[str],
    tmdb_content_mode: str,
    tmdb_language: str,
    tmdb_region: str,
    tmdb_vote_count_gte: int,
    tmdb_n_items: int,
    tmdb_use_search_fallback: bool,
) -> None:
    headline = reco_payload.get("headline", "오늘의 추천")
    tone = reco_payload.get("tone", "기본")
    recos = reco_payload.get("recommendations", [])

    mood_emoji = THEME["mood"].get(mood, {}).get("emoji", "🙂")
    weather_emoji = THEME["weather"].get(weather, {}).get("emoji", "🌤️")
    vibe_emoji = THEME["vibe"].get(vibe, {}).get("emoji", "🎯")
    time_emoji = THEME["time"].get(time_budget, {}).get("emoji", "⏳")

    st.markdown(
        f"""
<div style="display:flex; align-items:center; gap:10px; margin: 10px 0 6px 0;">
  <div style="font-size: 1.7rem;">{mood_emoji}</div>
  <div>
    <div style="font-size: 1.25rem; font-weight: 800;">{headline}</div>
    <div style="color: rgba(0,0,0,0.65);">톤: {tone}</div>
  </div>
</div>

<div style="margin: 6px 0 14px 0;">
  <span class="moodpick-chip">{mood_emoji} {mood}</span>
  <span class="moodpick-chip">{weather_emoji} {weather}</span>
  <span class="moodpick-chip">{vibe_emoji} {vibe}</span>
  <span class="moodpick-chip">{time_emoji} {time_budget}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    for i, r in enumerate(recos, start=1):
        title = r.get("title", f"추천 {i}")
        one_liner = r.get("one_liner", "")
        reason = r.get("reason", "")
        how_to = r.get("how_to_start", [])
        keywords = r.get("tmdb_keywords", [])

        steps_html = "".join([f"<li>{step}</li>" for step in how_to]) if how_to else "<li>바로 해보기</li>"
        keyword_str = ", ".join([k for k in keywords if isinstance(k, str) and k.strip()])

        st.markdown(
            f"""
<div class="moodpick-card">
  <div class="moodpick-title">{i}. {title}</div>
  <div class="moodpick-sub">{one_liner}</div>
  <div class="moodpick-reason"><b>왜 좋아요?</b> {reason}</div>
  <div><b>바로 시작하기</b>
    <ol style="margin-top:6px; margin-bottom:0;">
      {steps_html}
    </ol>
  </div>
  <div class="tmdb-row">
    <div style="font-weight:700; margin-bottom:6px;">
      🎬 함께 보기({ "영화" if tmdb_content_mode=="movie" else ("TV" if tmdb_content_mode=="tv" else "영화/TV") })
      — 키워드: {keyword_str if keyword_str else "없음"}
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        if not tmdb_key:
            st.info("TMDB API Key가 없어서 영화/TV 추천을 표시할 수 없어요. 사이드바에 TMDB 키를 입력해 주세요.")
            continue

        fallback_q = keyword_str if keyword_str else title
        items = tmdb_get_recommendations_weighted(
            api_key=tmdb_key,
            content_mode=tmdb_content_mode,
            mood=mood,
            vibe=vibe,
            weather=weather,
            fallback_query=fallback_q,
            language=tmdb_language,
            region=tmdb_region,
            vote_count_gte=tmdb_vote_count_gte,
            n_items=tmdb_n_items,
            use_search_fallback=tmdb_use_search_fallback,
        )
        render_tmdb_items(items)


# =========================
# Streamlit App
# =========================
st.set_page_config(page_title=APP_NAME, page_icon="✨", layout="wide")

for k in [
    "current_payload",
    "current_inputs",
    "openai_key",
    "tmdb_key",
    "tmdb_content_mode",
    "tmdb_language",
    "tmdb_region",
    "tmdb_vote_count_gte",
    "tmdb_n_items",
    "tmdb_use_search_fallback",
]:
    if k not in st.session_state:
        st.session_state[k] = None

# Defaults for TMDB options
if st.session_state.tmdb_content_mode is None:
    st.session_state.tmdb_content_mode = "both"  # movie | tv | both
if st.session_state.tmdb_language is None:
    st.session_state.tmdb_language = "ko-KR"
if st.session_state.tmdb_region is None:
    st.session_state.tmdb_region = "KR"
if st.session_state.tmdb_vote_count_gte is None:
    st.session_state.tmdb_vote_count_gte = 150
if st.session_state.tmdb_n_items is None:
    st.session_state.tmdb_n_items = 3
if st.session_state.tmdb_use_search_fallback is None:
    st.session_state.tmdb_use_search_fallback = True

# Sidebar
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.caption(APP_TAGLINE)

    st.header("🔑 API 키 설정")
    openai_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        value="" if st.session_state.openai_key is None else st.session_state.openai_key,
    )
    tmdb_key_input = st.text_input(
        "TMDB API Key",
        type="password",
        value="" if st.session_state.tmdb_key is None else st.session_state.tmdb_key,
    )

    if openai_key_input.strip():
        st.session_state.openai_key = openai_key_input.strip()
    if tmdb_key_input.strip():
        st.session_state.tmdb_key = tmdb_key_input.strip()

    st.caption(f"OpenAI Key: {'✅' if get_openai_key() else '❌'}")
    st.caption(f"TMDB Key: {'✅' if get_tmdb_key() else '❌'}")

    st.markdown("---")
    model = st.text_input("모델", value=DEFAULT_MODEL, help="Structured Outputs 지원 모델 권장")

    st.markdown("---")
    st.subheader("🎛️ 영화/TV 추천 설정")

    # 토글(라디오)
    st.session_state.tmdb_content_mode = st.radio(
        "콘텐츠 타입",
        options=["both", "movie", "tv"],
        format_func=lambda x: "영화/TV 둘 다" if x == "both" else ("영화" if x == "movie" else "TV"),
        index=["both", "movie", "tv"].index(st.session_state.tmdb_content_mode),
        horizontal=False,
    )

    st.session_state.tmdb_language = st.selectbox(
        "언어",
        options=["ko-KR", "en-US", "ja-JP"],
        index=["ko-KR", "en-US", "ja-JP"].index(st.session_state.tmdb_language),
        help="ko-KR 추천. 검색 fallback은 자동으로 en-US도 한번 더 시도할 수 있어요.",
    )

    st.session_state.tmdb_region = st.selectbox(
        "지역(영화용)",
        options=["KR", "US", "JP"],
        index=["KR", "US", "JP"].index(st.session_state.tmdb_region),
        help="Discover(movie)에서 region에 영향을 줄 수 있어요.",
    )

    st.session_state.tmdb_n_items = st.slider(
        "추천 개수(카드당)",
        min_value=1,
        max_value=6,
        value=int(st.session_state.tmdb_n_items),
        step=1,
    )

    st.session_state.tmdb_vote_count_gte = st.slider(
        "최소 평점 참여 수(인기/안정성)",
        min_value=0,
        max_value=2000,
        value=int(st.session_state.tmdb_vote_count_gte),
        step=50,
        help="낮출수록 더 많이 나오고, 높일수록 유명작 위주로 나와요.",
    )

    st.session_state.tmdb_use_search_fallback = st.checkbox(
        "검색 fallback 사용(Discover 부족할 때 검색으로 보완)",
        value=bool(st.session_state.tmdb_use_search_fallback),
    )

    st.markdown("---")
    st.markdown("### 저장된 히스토리")
    history = load_history()

    if not history:
        st.caption("아직 저장된 추천이 없어요.")
    else:
        for idx, item in enumerate(history[:20]):
            ts = item.get("saved_at", "")
            inp = item.get("inputs", {})
            label = f"{ts} | {inp.get('mood','')} / {inp.get('weather','')} / {inp.get('vibe','')}"
            if st.button(label, key=f"hist_{idx}", use_container_width=True):
                st.session_state.current_payload = item.get("payload")
                st.session_state.current_inputs = item.get("inputs")

    st.markdown("---")
    if st.button("히스토리 전체 삭제", use_container_width=True):
        save_history([])
        st.success("히스토리를 삭제했어요. 새로고침하면 목록이 비어요.")


# Main UI
col_left, col_right = st.columns([1.0, 1.2], gap="large")

with col_left:
    st.markdown("# 오늘 어떤 기분인가요?")

    mood = st.radio("기분", MOODS, horizontal=True)
    weather = st.radio("날씨", WEATHERS, horizontal=True)
    vibe = st.radio("분위기", VIBES, horizontal=True)
    time_budget = st.radio("시간", TIME_BUDGETS, horizontal=True)

    extra = st.text_area(
        "추가 제약(선택)",
        placeholder="예: 예산 1만원 이하 / 집 근처에서 / 너무 활동적인 건 싫어요 / 조용한 곳 선호",
        height=100,
    )

    accent = THEME["mood"].get(mood, {}).get("accent", "#6B7280")
    apply_dynamic_style(accent)

    btn_cols = st.columns([1, 1, 1])
    with btn_cols[0]:
        go = st.button("✨ 추천 받기", use_container_width=True)
    with btn_cols[1]:
        reroll = st.button("🔄 다시 추천", use_container_width=True)
    with btn_cols[2]:
        save_btn = st.button("💾 저장하기", use_container_width=True, disabled=st.session_state.current_payload is None)

    if go or reroll:
        openai_key = ensure_openai_key_or_stop()

        with st.spinner("추천을 만드는 중..."):
            try:
                payload = call_openai_recommendations(
                    api_key=openai_key,
                    model=model,
                    mood=mood,
                    weather=weather,
                    vibe=vibe,
                    time_budget=time_budget,
                    extra_constraints=extra,
                )
            except Exception as e:
                st.error(f"OpenAI 호출에 실패했어요: {e}")
                st.stop()

        st.session_state.current_payload = payload
        st.session_state.current_inputs = {
            "mood": mood,
            "weather": weather,
            "vibe": vibe,
            "time_budget": time_budget,
            "extra_constraints": extra,
            "model": model,
            "tmdb_enabled": bool(get_tmdb_key()),
            "tmdb_content_mode": st.session_state.tmdb_content_mode,
            "tmdb_language": st.session_state.tmdb_language,
            "tmdb_region": st.session_state.tmdb_region,
            "tmdb_vote_count_gte": st.session_state.tmdb_vote_count_gte,
            "tmdb_n_items": st.session_state.tmdb_n_items,
            "tmdb_use_search_fallback": st.session_state.tmdb_use_search_fallback,
        }

    if save_btn and st.session_state.current_payload and st.session_state.current_inputs:
        entry = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "inputs": st.session_state.current_inputs,
            "payload": st.session_state.current_payload,
        }
        add_history_entry(entry)
        st.success("저장했어요! (사이드바 히스토리에서 다시 볼 수 있어요)")

with col_right:
    st.markdown("## 추천 결과")
    if st.session_state.current_payload is None:
        st.info("왼쪽에서 기분/날씨/분위기/시간을 고르고 **추천 받기**를 눌러주세요.")
    else:
        inp = st.session_state.current_inputs or {}
        render_reco_cards(
            st.session_state.current_payload,
            inp.get("mood", mood),
            inp.get("weather", weather),
            inp.get("vibe", vibe),
            inp.get("time_budget", time_budget),
            tmdb_key=get_tmdb_key(),
            tmdb_content_mode=st.session_state.tmdb_content_mode,
            tmdb_language=st.session_state.tmdb_language,
            tmdb_region=st.session_state.tmdb_region,
            tmdb_vote_count_gte=int(st.session_state.tmdb_vote_count_gte),
            tmdb_n_items=int(st.session_state.tmdb_n_items),
            tmdb_use_search_fallback=bool(st.session_state.tmdb_use_search_fallback),
        )

st.markdown("---")
st.caption(
    "보안 팁: 배포 시엔 `.streamlit/secrets.toml` 또는 환경변수 사용을 권장해요. "
    "사이드바 입력은 세션에만 저장됩니다."
)

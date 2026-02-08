import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def get_api_key_openai() -> Optional[str]:
    """
    우선순위:
    1) st.secrets["OPENAI_API_KEY"]
    2) 환경변수 OPENAI_API_KEY
    3) 사이드바 입력값 (st.session_state["openai_key"])
    """
    key = get_secret("OPENAI_API_KEY")
    if not key:
        key = os.getenv("OPENAI_API_KEY", "").strip() or None
    if not key:
        key = st.session_state.get("openai_key", None)
    return key.strip() if isinstance(key, str) and key.strip() else None


def get_api_key_tmdb() -> Optional[str]:
    """
    우선순위:
    1) st.secrets["TMDB_API_KEY"]
    2) 환경변수 TMDB_API_KEY
    3) 사이드바 입력값 (st.session_state["tmdb_key"])
    """
    key = get_secret("TMDB_API_KEY")
    if not key:
        key = os.getenv("TMDB_API_KEY", "").strip() or None
    if not key:
        key = st.session_state.get("tmdb_key", None)
    return key.strip() if isinstance(key, str) and key.strip() else None


def get_api_key_unsplash() -> Optional[str]:
    """
    우선순위:
    1) st.secrets["UNSPLASH_ACCESS_KEY"]
    2) 환경변수 UNSPLASH_ACCESS_KEY
    3) 사이드바 입력값 (st.session_state["unsplash_key"])
    """
    key = get_secret("UNSPLASH_ACCESS_KEY")
    if not key:
        key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip() or None
    if not key:
        key = st.session_state.get("unsplash_key", None)
    return key.strip() if isinstance(key, str) and key.strip() else None


def ensure_openai_key_or_stop() -> str:
    key = get_api_key_openai()
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
""".strip()

    if extra_constraints.strip():
        base += f"\n\n추가 제약/선호:\n{extra_constraints.strip()}\n"

    return base


def recommendations_schema() -> Dict[str, Any]:
    return {
        "name": "moodpick_recommendations",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "headline": {"type": "string"},
                "tone": {"type": "string", "description": "결과 화면 문구 톤(예: 차분한, 따뜻한, 발랄한 등)"},
                "recommendations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "one_liner": {"type": "string", "description": "짧은 설명(한 줄)"},
                            "reason": {"type": "string", "description": "부담 없는 이유(한 문장)"},
                            "how_to_start": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 3,
                                "items": {"type": "string"},
                                "description": "바로 시작할 수 있는 1~3단계",
                            },
                        },
                        "required": ["title", "one_liner", "reason", "how_to_start"],
                    },
                },
            },
            "required": ["headline", "tone", "recommendations"],
        },
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
        "항상 3개 이내로 추천하고, 각각에 부담 없는 이유를 한 문장으로 덧붙여라."
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
                "strict": True,
                "schema": recommendations_schema(),
            }
        },
    )

    return json.loads(resp.output_text)


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
</style>
""",
        unsafe_allow_html=True,
    )


def render_reco_cards(reco_payload: Dict[str, Any], mood: str, weather: str, vibe: str, time_budget: str) -> None:
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

        steps_html = "".join([f"<li>{step}</li>" for step in how_to]) if how_to else "<li>바로 해보기</li>"

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
</div>
""",
            unsafe_allow_html=True,
        )


# =========================
# Streamlit App
# =========================
st.set_page_config(page_title=APP_NAME, page_icon="✨", layout="wide")

# Session state init
for k in ["current_payload", "current_inputs", "openai_key", "tmdb_key", "unsplash_key"]:
    if k not in st.session_state:
        st.session_state[k] = None

# Sidebar: API Keys + Settings + History
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.caption(APP_TAGLINE)

    # ---- 사용자가 원한 UI 그대로 병합 ----
    st.header("🔑 API 키 설정")
    openai_key_input = st.text_input("OpenAI API Key", type="password", value="" if st.session_state.openai_key is None else st.session_state.openai_key)
    tmdb_key_input = st.text_input("TMDB API Key", type="password", value="" if st.session_state.tmdb_key is None else st.session_state.tmdb_key)
    unsplash_key_input = st.text_input("Unsplash Access Key", type="password", value="" if st.session_state.unsplash_key is None else st.session_state.unsplash_key)

    # 세션에 저장(페이지 새로고침/재실행 전까지 유지)
    if openai_key_input.strip():
        st.session_state.openai_key = openai_key_input.strip()
    if tmdb_key_input.strip():
        st.session_state.tmdb_key = tmdb_key_input.strip()
    if unsplash_key_input.strip():
        st.session_state.unsplash_key = unsplash_key_input.strip()

    # 현재 상태 표시
    st.caption(f"OpenAI Key: {'✅' if get_api_key_openai() else '❌'}")
    st.caption(f"TMDB Key: {'✅' if get_api_key_tmdb() else '❌'}")
    st.caption(f"Unsplash Key: {'✅' if get_api_key_unsplash() else '❌'}")

    st.markdown("---")

    model = st.text_input("모델", value=DEFAULT_MODEL, help="Structured Outputs 지원 모델 권장")

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
        api_key = ensure_openai_key_or_stop()
        with st.spinner("추천을 만드는 중..."):
            try:
                payload = call_openai_recommendations(
                    api_key=api_key,
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
            # 참고로 나중에 외부 API 연동할 때 쓰기 쉽도록 같이 저장
            "tmdb_key_set": bool(get_api_key_tmdb()),
            "unsplash_key_set": bool(get_api_key_unsplash()),
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
        )

st.markdown("---")
st.caption("보안 팁: 배포 시엔 secrets.toml 또는 환경변수 사용을 권장해요. 사이드바 입력은 세션에만 저장됩니다.")

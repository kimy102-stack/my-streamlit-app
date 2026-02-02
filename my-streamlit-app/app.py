import requests
import streamlit as st
from dataclasses import dataclass
from typing import Dict, List, Tuple

# =========================================================
# Page
# =========================================================
st.set_page_config(page_title="나와 어울리는 영화는?", page_icon="🎬", layout="wide")

# =========================================================
# ✅ 팀원끼리 바꿀 포인트(내가 기본값으로 정함)
# =========================================================
TEAM_TUNING = {
    # 질문/가중치
    "QUESTION_WEIGHTS": {  # 질문별 가중치(팀이 논의하면서 숫자만 바꾸면 됨)
        "q1": 1,
        "q2": 1,
        "q3": 1,
        "q4": 2,  # 과제/현실도피 문항은 성향이 강하게 드러난다고 가정
        "q5": 2,  # “주인공 설정”은 취향 확실하다고 가정
    },

    # 타이브레이커(동점일 때)
    "TIE_BREAKER_ORDER": ["sf_fantasy", "action_adventure", "romance_drama", "comedy"],

    # 혼합장르(Top2를 섞어서 추천)
    "MIXED_GENRE_TOP_N": 2,           # 2면 Top2 혼합 추천 / 1이면 단일 장르
    "MIXED_GENRE_RATIO": [0.6, 0.4],  # Top1:Top2 비율(추천 개수 배분)

    # 카드 UI
    "CARDS_PER_ROW": 3,
    "SHOW_OVERVIEW_PREVIEW": False,   # 카드에 줄거리 미리보기 표시 여부
    "OVERVIEW_PREVIEW_LEN": 90,

    # 정렬/추천수
    "TMDB_SORT_BY": "popularity.desc",  # popularity.desc / vote_average.desc / revenue.desc
    "RECOMMEND_COUNT": 6,              # 추천 영화 수
}

# =========================================================
# Data Models
# =========================================================
@dataclass(frozen=True)
class GenreProfile:
    key: str
    label: str
    tmdb_ids: List[int]
    base_reason: str

GENRES: Dict[str, GenreProfile] = {
    "romance_drama": GenreProfile(
        key="romance_drama",
        label="로맨스/드라마",
        tmdb_ids=[10749, 18],
        base_reason="감정선과 관계의 변화를 좋아하는 편이라, 여운이 긴 이야기와 몰입감 있는 드라마가 잘 맞아요.",
    ),
    "action_adventure": GenreProfile(
        key="action_adventure",
        label="액션/어드벤처",
        tmdb_ids=[28],
        base_reason="짜릿한 전개와 도전/성장 서사를 선호해서, 속도감 있는 액션 계열이 딱이에요.",
    ),
    "sf_fantasy": GenreProfile(
        key="sf_fantasy",
        label="SF/판타지",
        tmdb_ids=[878, 14],
        base_reason="세계관·상상력·설정에 끌리는 편이라, 현실을 확장하는 SF/판타지가 잘 맞아요.",
    ),
    "comedy": GenreProfile(
        key="comedy",
        label="코미디",
        tmdb_ids=[35],
        base_reason="웃음 포인트와 가벼운 템포를 즐겨서, 스트레스 풀기 좋은 코미디가 잘 맞아요.",
    ),
}

QUESTIONS: List[Dict] = [
    {
        "id": "q1",
        "text": "1. 오랜만에 하루가 통째로 비는 날, 가장 하고 싶은 건?",
        "options": [
            ("romance_drama", "A. 좋아하는 음악 틀어놓고 카페나 산책하면서 생각 정리하기"),
            ("action_adventure", "B. 즉흥으로 여행 떠나거나 새로운 액티비티 도전하기"),
            ("sf_fantasy", "C. 밤새 세계관 있는 영화·드라마 정주행하기"),
            ("comedy", "D. 친구들이랑 모여서 웃긴 영상이나 예능 보기"),
        ],
    },
    {
        "id": "q2",
        "text": "2. 시험이 끝난 날, 나의 기분은?",
        "options": [
            ("romance_drama", "A. “고생했다 나 자신…” 감정이 몰려와서 괜히 센치해진다"),
            ("action_adventure", "B. 해방감 MAX! 뭐든지 할 수 있을 것 같다"),
            ("sf_fantasy", "C. 이제야 현실로 돌아온 느낌… 아직도 머리는 딴 데 가 있음"),
            ("comedy", "D. 드디어 밈 돌려보고 썰 풀 시간이다"),
        ],
    },
    {
        "id": "q3",
        "text": "3. 처음 만난 사람과 빨리 친해지는 방법은?",
        "options": [
            ("romance_drama", "A. 진지한 얘기하다가 공감대 생기기"),
            ("action_adventure", "B. 같이 뭔가 해보면서 자연스럽게 친해지기"),
            ("sf_fantasy", "C. 취향·덕질 얘기로 깊게 파고들기"),
            ("comedy", "D. 농담 주고받다가 웃음 터지면서 친해지기"),
        ],
    },
    {
        "id": "q4",
        "text": "4. 과제하다가 현실 도피하고 싶을 때 드는 생각은?",
        "options": [
            ("romance_drama", "A. “이 시기 지나면 좀 더 괜찮아지겠지…”"),
            ("action_adventure", "B. “다 때려치우고 어디론가 떠나고 싶다”"),
            ("sf_fantasy", "C. “이건 내가 있는 세계선이 잘못된 게 분명해”"),
            ("comedy", "D. “이 상황 자체가 너무 웃기다ㅋㅋ”"),
        ],
    },
    {
        "id": "q5",
        "text": "5. 영화 속 주인공이 된다면 가장 끌리는 설정은?",
        "options": [
            ("romance_drama", "A. 관계와 감정의 변화를 섬세하게 겪는 인물"),
            ("action_adventure", "B. 위기 속에서 선택을 거듭하며 성장하는 인물"),
            ("sf_fantasy", "C. 다른 세계나 규칙을 마주한 특별한 존재"),
            ("comedy", "D. 사건 사고의 중심에서 분위기 메이커 역할"),
        ],
    },
]

TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"


# =========================================================
# Sidebar
# =========================================================
st.sidebar.header("TMDB 설정")
api_key = st.sidebar.text_input("TMDB API Key", type="password")
language = st.sidebar.selectbox("언어", ["ko-KR", "en-US"], index=0)
st.sidebar.caption("추천/로직 변경은 코드 상단 TEAM_TUNING만 수정하면 돼요.")


# =========================================================
# Scoring / Decision
# =========================================================
def score_answers(answers: Dict[str, str]) -> Dict[str, int]:
    scores = {k: 0 for k in GENRES.keys()}
    for qid, gkey in answers.items():
        w = TEAM_TUNING["QUESTION_WEIGHTS"].get(qid, 1)
        scores[gkey] += w
    return scores


def pick_top_genres(scores: Dict[str, int], top_n: int) -> List[str]:
    # 점수 내림차순, 동점 시 tie-breaker order로 정렬
    tie_rank = {k: i for i, k in enumerate(TEAM_TUNING["TIE_BREAKER_ORDER"])}
    ordered = sorted(
        scores.items(),
        key=lambda kv: (-kv[1], tie_rank.get(kv[0], 999)),
    )
    return [k for k, _ in ordered[:top_n]]


def build_result_reason(top_keys: List[str], scores: Dict[str, int]) -> str:
    total = sum(scores.values()) or 1
    parts = []
    for k in top_keys:
        pct = int(round(scores[k] / total * 100))
        parts.append(f"{GENRES[k].label} {pct}%")
    return " / ".join(parts)


def movie_reason(main: GenreProfile, movie: dict) -> str:
    overview = (movie.get("overview") or "").strip()
    vote = movie.get("vote_average")
    score_hint = f"평점 {vote:.1f}" if isinstance(vote, (int, float)) else "평점 정보"

    if main.key == "romance_drama":
        hook = "감정선과 관계의 흐름을 좋아하는 타입이라"
        extra = "여운이 남는 전개" if overview else "인물 중심 이야기"
    elif main.key == "action_adventure":
        hook = "전개가 빠르고 사건이 몰아치는 걸 좋아해서"
        extra = "긴장감 있는 흐름" if overview else "속도감 있는 액션"
    elif main.key == "sf_fantasy":
        hook = "세계관/설정 취향이 강해서"
        extra = "상상력 자극 설정" if overview else "독특한 분위기"
    else:
        hook = "가볍게 웃으며 보기 좋은 작품을 선호해서"
        extra = "유쾌한 톤" if overview else "기분 전환에 좋음"

    return f"{hook} **{extra}**가 잘 맞아요. ({score_hint})"


# =========================================================
# TMDB Client
# =========================================================
@st.cache_data(show_spinner=False, ttl=60 * 10)
def tmdb_discover(api_key: str, genre_id: int, language: str, sort_by: str, page: int) -> List[dict]:
    params = {
        "api_key": api_key,
        "with_genres": str(genre_id),
        "language": language,
        "sort_by": sort_by,
        "page": page,
    }
    r = requests.get(TMDB_DISCOVER_URL, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("results", [])


def fetch_movies_for_profile(api_key: str, profile: GenreProfile, language: str, sort_by: str, need: int) -> List[dict]:
    # profile.tmdb_ids 각각에서 1~2페이지 가져와 병합
    results, seen = [], set()
    for gid in profile.tmdb_ids:
        for page in (1, 2):
            chunk = tmdb_discover(api_key, gid, language, sort_by, page)
            for m in chunk:
                mid = m.get("id")
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                results.append(m)
            if len(results) >= need * 3:
                break
        if len(results) >= need * 3:
            break
    return results


def pick_top_unique(movies: List[dict], limit: int, poster_first: bool = True) -> List[dict]:
    def rating(m):
        v = m.get("vote_average")
        return v if isinstance(v, (int, float)) else 0.0

    if poster_first:
        movies = sorted(movies, key=lambda m: (m.get("poster_path") is None, -rating(m)))

    out, seen_titles = [], set()
    for m in movies:
        title = (m.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        out.append(m)
        if len(out) >= limit:
            break
    return out


def build_mixed_recommendations(
    api_key: str,
    top_keys: List[str],
    language: str,
    sort_by: str,
    total_count: int,
) -> List[Tuple[str, dict]]:
    """
    Top2 혼합 추천:
      - Top1에서 60%, Top2에서 40% 비율로 추천 개수 배분
      - 반환: [(genre_key, movie), ...]  (카드에 '출처 장르' 표시할 수도 있음)
    """
    ratios = TEAM_TUNING["MIXED_GENRE_RATIO"]
    # top_keys 길이에 맞춰 ratio를 자르거나 기본값 적용
    ratios = (ratios + [0.0] * len(top_keys))[: len(top_keys)]
    # 개수 배분
    counts = [max(0, int(round(total_count * r))) for r in ratios]
    # 라운딩 오차 보정: 부족분은 1번 장르에 더함
    diff = total_count - sum(counts)
    if counts:
        counts[0] += diff

    mixed: List[Tuple[str, dict]] = []
    for gkey, n in zip(top_keys, counts):
        if n <= 0:
            continue
        prof = GENRES[gkey]
        pool = fetch_movies_for_profile(api_key, prof, language, sort_by, need=n)
        picks = pick_top_unique(pool, n, poster_first=True)
        mixed.extend([(gkey, m) for m in picks])

    return mixed


# =========================================================
# UI: Quiz
# =========================================================
st.title("🎬 나와 어울리는 영화는?")
st.write("대학생 감성 5문항 심리테스트! 😄 가장 끌리는 선택지를 고르면, 취향에 맞는 영화를 추천해줘요.")
st.divider()

answers: Dict[str, str] = {}
for q in QUESTIONS:
    labels = [f"{text}  —  [{GENRES[g].label}]" for g, text in q["options"]]
    values = [g for g, _ in q["options"]]
    picked = st.radio(q["text"], labels, index=None, key=q["id"])
    if picked is not None:
        idx = labels.index(picked)
        answers[q["id"]] = values[idx]
    st.write("")

st.divider()

# =========================================================
# UI: Result
# =========================================================
if st.button("결과 보기", type="primary"):
    if not api_key:
        st.error("사이드바에 TMDB API Key를 입력해줘!")
        st.stop()

    if len(answers) < len(QUESTIONS):
        st.warning("모든 질문에 답해야 결과를 볼 수 있어요.")
        st.stop()

    scores = score_answers(answers)

    # 혼합 장르 Top2 추천 (기본)
    top_n = TEAM_TUNING["MIXED_GENRE_TOP_N"]
    top_keys = pick_top_genres(scores, top_n=top_n)

    # 결과 제목: 메인 장르(Top1)로 표시
    main_profile = GENRES[top_keys[0]]
    st.markdown(f"## ✨ 당신에게 딱인 장르는: **{main_profile.label}**!")
    st.caption(build_result_reason(top_keys, scores))
    st.caption(main_profile.base_reason)
    st.write("")

    with st.spinner("분석 중... (TMDB에서 인기 영화를 불러오는 중)"):
        try:
            mixed = build_mixed_recommendations(
                api_key=api_key,
                top_keys=top_keys,
                language=language,
                sort_by=TEAM_TUNING["TMDB_SORT_BY"],
                total_count=TEAM_TUNING["RECOMMEND_COUNT"],
            )
        except requests.HTTPError:
            st.error("TMDB 요청에 실패했어요. API Key가 맞는지 확인해줘요.")
            st.stop()
        except Exception as e:
            st.error("영화 데이터를 가져오는 중 오류가 발생했어요.")
            st.exception(e)
            st.stop()

    if not mixed:
        st.info("추천할 영화를 찾지 못했어요. 잠시 후 다시 시도해줘요.")
        st.stop()

    st.markdown("### 🎥 추천 영화")

    cols = st.columns(TEAM_TUNING["CARDS_PER_ROW"], gap="large")

    for i, (source_gkey, m) in enumerate(mixed):
        title = m.get("title") or "제목 없음"
        rating = m.get("vote_average")
        overview = (m.get("overview") or "").strip()
        poster_path = m.get("poster_path")

        with cols[i % TEAM_TUNING["CARDS_PER_ROW"]]:
            with st.container(border=True):
                # 포스터
                if poster_path:
                    st.image(POSTER_BASE + poster_path, use_container_width=True)
                else:
                    st.caption("포스터 없음")

                # 제목/평점
                st.markdown(f"**{title}**")
                if isinstance(rating, (int, float)):
                    st.write(f"⭐ 평점: **{rating:.1f}**")
                else:
                    st.write("⭐ 평점: 정보 없음")

                # (혼합 추천일 경우) 이 카드가 어느 쪽 장르에서 왔는지 표시
                if top_n >= 2:
                    st.caption(f"🎯 추천 출처: {GENRES[source_gkey].label}")

                # 카드에 줄거리 미리보기(옵션)
                if TEAM_TUNING["SHOW_OVERVIEW_PREVIEW"] and overview:
                    preview_len = TEAM_TUNING["OVERVIEW_PREVIEW_LEN"]
                    preview = overview if len(overview) <= preview_len else overview[:preview_len].rstrip() + "…"
                    st.caption(preview)

                # 상세 보기
                with st.expander("상세 보기"):
                    st.write(overview if overview else "줄거리 정보가 없어요.")
                    # 추천 이유는 메인 장르 기준으로 설명(팀 논의로 source_gkey 기준으로 바꿔도 됨)
                    st.info("💡 " + movie_reason(main_profile, m))

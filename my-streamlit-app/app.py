import requests
import streamlit as st
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# =========================================================
# Page
# =========================================================
st.set_page_config(page_title="나와 어울리는 영화는?", page_icon="🎬", layout="wide")

# =========================================================
# 1) Config Layer (팀 논의 결과를 반영하는 곳)
#    - 질문, 선택지, 장르 맵핑, TMDB 장르ID, 문구 등
# =========================================================

@dataclass(frozen=True)
class GenreProfile:
    key: str                      # 내부 키
    label: str                    # 사용자 노출
    tmdb_ids: List[int]           # TMDB 장르 ID(여러 개 가능)
    base_reason: str              # 결과 상단 문구
    tie_priority: int             # 동점일 때 우선순위 (낮을수록 우선)

GENRES: Dict[str, GenreProfile] = {
    "romance_drama": GenreProfile(
        key="romance_drama",
        label="로맨스/드라마",
        tmdb_ids=[10749, 18],
        base_reason="감정선과 관계의 변화를 좋아하는 편이라, 여운이 긴 이야기와 몰입감 있는 드라마가 잘 맞아요.",
        tie_priority=1,
    ),
    "action_adventure": GenreProfile(
        key="action_adventure",
        label="액션/어드벤처",
        tmdb_ids=[28],  # 요구사항에 어드벤처 ID는 없어서 액션 중심
        base_reason="짜릿한 전개와 도전/성장 서사를 선호해서, 속도감 있는 액션 계열이 딱이에요.",
        tie_priority=2,
    ),
    "sf_fantasy": GenreProfile(
        key="sf_fantasy",
        label="SF/판타지",
        tmdb_ids=[878, 14],
        base_reason="세계관·상상력·설정에 끌리는 편이라, 현실을 확장하는 SF/판타지가 잘 맞아요.",
        tie_priority=3,
    ),
    "comedy": GenreProfile(
        key="comedy",
        label="코미디",
        tmdb_ids=[35],
        base_reason="웃음 포인트와 가벼운 템포를 즐겨서, 스트레스 풀기 좋은 코미디가 잘 맞아요.",
        tie_priority=4,
    ),
}

# 질문/선택지:
# - (genre_key, text) 형태로 둬서 나중에 문항/선택지 교체해도 로직이 안 깨짐
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

POSTER_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"


# =========================================================
# 2) Sidebar Controls (팀이 실험할 수 있는 옵션들)
# =========================================================
st.sidebar.header("설정 / 실험 패널")

api_key = st.sidebar.text_input("TMDB API Key", type="password", help="TMDB API 키를 입력하세요.")

language = st.sidebar.selectbox("TMDB 언어", ["ko-KR", "en-US"], index=0)

# 추천 수, 레이아웃
num_recs = st.sidebar.slider("추천 영화 수", 3, 12, 6, step=1)
cards_per_row = st.sidebar.selectbox("카드 열 수", [2, 3, 4], index=1)

# 정렬 기준 실험(Discover API에 sort_by 활용)
sort_by = st.sidebar.selectbox(
    "정렬 기준",
    [
        ("popularity.desc", "인기순"),
        ("vote_average.desc", "평점순(주의: 표본 적을 수 있음)"),
        ("revenue.desc", "흥행(매출)순"),
    ],
    index=0,
    format_func=lambda x: x[1],
)[0]

poster_first = st.sidebar.checkbox("포스터 있는 영화 우선", value=True)
show_overview_in_card = st.sidebar.checkbox("카드에 줄거리 일부 표시", value=False)

st.sidebar.divider()


# =========================================================
# 3) Scoring Layer (심리테스트 방식 교체가 쉬운 부분)
#    - 지금은 기본: 다수결 + 동점 우선순위
#    - 팀 논의로: 가중치, 최근 선택 가중, 질문별 가중 등 쉽게 변경 가능
# =========================================================

def score_answers(answers: Dict[str, str]) -> Dict[str, int]:
    """
    answers: {question_id: genre_key}
    return:  {genre_key: score}
    """
    scores = {g: 0 for g in GENRES.keys()}
    for _, gkey in answers.items():
        if gkey in scores:
            scores[gkey] += 1
    return scores


def pick_genre(scores: Dict[str, int]) -> GenreProfile:
    """
    다수결. 동점이면 tie_priority가 낮은 장르 우선.
    """
    max_score = max(scores.values()) if scores else 0
    tied = [k for k, v in scores.items() if v == max_score]

    # tie priority로 선택
    tied_profiles = [GENRES[k] for k in tied]
    tied_profiles.sort(key=lambda gp: gp.tie_priority)
    return tied_profiles[0]


def build_reason(profile: GenreProfile, scores: Dict[str, int]) -> str:
    """
    결과 이유 문구(팀 논의로 얼마든지 확장 가능)
    """
    total = sum(scores.values()) or 1
    main_pct = int(round(scores[profile.key] / total * 100))
    return f"{profile.base_reason} (일치도 약 {main_pct}%)"


def movie_reason(profile: GenreProfile, movie: dict) -> str:
    """
    영화별 추천 이유(간단)
    """
    overview = (movie.get("overview") or "").strip()
    vote = movie.get("vote_average")
    score_hint = f"평점 {vote:.1f}" if isinstance(vote, (int, float)) else "평점 정보"

    if profile.key == "romance_drama":
        hook = "감정선/관계 변화에 몰입하기 좋은 타입이라"
        extra = "여운이 남는 전개" if overview else "인물 중심 이야기"
    elif profile.key == "action_adventure":
        hook = "속도감 있는 전개를 좋아해서"
        extra = "긴장감 있는 흐름" if overview else "액션/모험의 재미"
    elif profile.key == "sf_fantasy":
        hook = "세계관·설정 취향이 강해서"
        extra = "상상력 자극 설정" if overview else "독특한 분위기"
    else:
        hook = "기분 전환용 작품을 선호해서"
        extra = "유쾌한 톤" if overview else "가볍게 즐기기 좋음"

    return f"{hook} **{extra}**가 잘 맞아요. ({score_hint})"


# =========================================================
# 4) TMDB Client Layer (API 연동/캐시/에러 처리)
# =========================================================

@st.cache_data(show_spinner=False, ttl=60 * 10)
def tmdb_discover(
    api_key: str,
    genre_id: int,
    language: str,
    sort_by: str,
    page: int = 1,
) -> List[dict]:
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


def fetch_recommendations(
    api_key: str,
    profile: GenreProfile,
    language: str,
    sort_by: str,
    limit: int,
) -> List[dict]:
    """
    장르가 2개 이상일 수 있으므로:
    - 각 장르ID에서 1~2페이지 정도 가져와 병합
    - 중복 제거 후 상위 limit개 반환
    """
    results: List[dict] = []
    seen_ids = set()

    # 장르별로 병합
    for gid in profile.tmdb_ids:
        for page in (1, 2):
            chunk = tmdb_discover(api_key, gid, language, sort_by, page)
            for m in chunk:
                mid = m.get("id")
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                results.append(m)
            if len(results) >= max(limit * 3, 20):
                break
        if len(results) >= max(limit * 3, 20):
            break

    return results


# =========================================================
# 5) UI Rendering Layer (화면 구성만 담당)
# =========================================================

def render_quiz() -> Dict[str, str]:
    """
    질문 화면 렌더링 후 answers 반환
    answers: {question_id: genre_key}
    """
    st.title("🎬 나와 어울리는 영화는?")
    st.write("대학생 감성 5문항 심리테스트! 😄 가장 끌리는 선택지를 고르면, 취향에 맞는 영화를 추천해줘요.")
    st.divider()

    answers: Dict[str, str] = {}

    for q in QUESTIONS:
        opts = q["options"]
        # 라디오에 보여줄 라벨과 내부 값 분리
        labels = [f"{text}  —  [{GENRES[gkey].label}]" for (gkey, text) in opts]
        values = [gkey for (gkey, _) in opts]

        picked = st.radio(q["text"], labels, index=None, key=q["id"])
        if picked is not None:
            # label에서 인덱스 찾아 values로 매핑
            idx = labels.index(picked)
            answers[q["id"]] = values[idx]

        st.write("")

    st.divider()
    return answers


def render_movie_cards(
    movies: List[dict],
    profile: GenreProfile,
    limit: int,
    cards_per_row: int,
    poster_first: bool,
    show_overview_in_card: bool,
):
    # 정렬/필터(로컬 측)
    def rating_val(m): 
        v = m.get("vote_average")
        return v if isinstance(v, (int, float)) else 0.0

    if poster_first:
        movies = sorted(movies, key=lambda m: (m.get("poster_path") is None, -rating_val(m)))

    # top N
    final: List[dict] = []
    seen_title = set()
    for m in movies:
        title = (m.get("title") or "").strip()
        if not title or title in seen_title:
            continue
        seen_title.add(title)
        final.append(m)
        if len(final) >= limit:
            break

    if not final:
        st.info("추천할 영화를 찾지 못했어요. (TMDB 결과가 비었거나 필터링 중 제거됨)")
        return

    st.markdown("### 🎥 추천 영화")

    cols = st.columns(cards_per_row, gap="large")

    for i, m in enumerate(final):
        title = m.get("title") or "제목 없음"
        rating = m.get("vote_average")
        overview = (m.get("overview") or "").strip()
        poster_path = m.get("poster_path")

        with cols[i % cards_per_row]:
            with st.container(border=True):
                if poster_path:
                    st.image(POSTER_BASE + poster_path, use_container_width=True)
                else:
                    st.caption("포스터 없음")

                st.markdown(f"**{title}**")
                if isinstance(rating, (int, float)):
                    st.write(f"⭐ 평점: **{rating:.1f}**")
                else:
                    st.write("⭐ 평점: 정보 없음")

                if show_overview_in_card and overview:
                    preview = overview if len(overview) <= 90 else overview[:90].rstrip() + "…"
                    st.caption(preview)

                with st.expander("상세 보기"):
                    st.write(overview if overview else "줄거리 정보가 없어요.")
                    st.info("💡 " + movie_reason(profile, m))


# =========================================================
# 6) App Flow
# =========================================================
answers = render_quiz()

# 버튼 영역
if st.button("결과 보기", type="primary"):
    # 기본 검증
    if not api_key:
        st.error("사이드바에 TMDB API Key를 먼저 입력해줘!")
        st.stop()

    if len(answers) < len(QUESTIONS):
        st.warning("모든 질문에 답해야 결과를 볼 수 있어요.")
        st.stop()

    # 1) 분석
    scores = score_answers(answers)
    profile = pick_genre(scores)

    # 2) 결과 헤더 (요구사항 형태로)
    st.markdown(f"## ✨ 당신에게 딱인 장르는: **{profile.label}**!")
    st.caption(build_reason(profile, scores))
    st.write("")

    # 3) TMDB 로딩
    with st.spinner("분석 중... (TMDB에서 인기 영화를 불러오는 중)"):
        try:
            movies = fetch_recommendations(
                api_key=api_key,
                profile=profile,
                language=language,
                sort_by=sort_by,
                limit=num_recs,
            )
        except requests.HTTPError:
            st.error("TMDB 요청에 실패했어요. API Key가 맞는지 확인해줘요.")
            st.stop()
        except Exception as e:
            st.error("영화 데이터를 가져오는 중 오류가 발생했어요.")
            st.exception(e)
            st.stop()

    # 4) 카드 UI
    render_movie_cards(
        movies=movies,
        profile=profile,
        limit=num_recs,
        cards_per_row=cards_per_row,
        poster_first=poster_first,
        show_overview_in_card=show_overview_in_card,
    )


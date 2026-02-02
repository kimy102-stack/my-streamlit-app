import requests
import streamlit as st

st.set_page_config(page_title="나와 어울리는 영화는?", page_icon="🎬", layout="centered")

# ---------------------------
# Sidebar: API Key input
# ---------------------------
st.sidebar.header("TMDB 설정")
api_key = st.sidebar.text_input("TMDB API Key", type="password", help="TMDB API 키를 입력하세요.")
st.sidebar.caption("키는 화면에 저장되지 않아요. (세션 동안만 사용)")

# ---------------------------
# App header
# ---------------------------
st.title("🎬 나와 어울리는 영화는?")
st.write("대학생 감성 5문항 심리테스트! 😄 가장 끌리는 선택지를 골라보면, 취향에 맞는 영화를 5편 추천해줘요.")

st.divider()

# ---------------------------
# Genre mapping
# ---------------------------
GENRE_INFO = {
    "로맨스/드라마": {
        "tmdb_ids": [10749, 18],  # 로맨스 + 드라마
        "label": "로맨스/드라마",
        "reason": "감정선과 관계의 변화를 좋아하는 편이라, 여운이 긴 이야기와 몰입감 있는 드라마가 잘 맞아요.",
    },
    "액션/어드벤처": {
        "tmdb_ids": [28],  # 액션 (어드벤처는 별도 ID가 있지만 요구사항에 없어서 액션 중심)
        "label": "액션/어드벤처",
        "reason": "짜릿한 전개와 도전/성장 서사를 선호해서, 속도감 있는 액션 계열이 딱이에요.",
    },
    "SF/판타지": {
        "tmdb_ids": [878, 14],  # SF + 판타지
        "label": "SF/판타지",
        "reason": "세계관·상상력·설정에 끌리는 편이라, 현실을 확장하는 SF/판타지가 잘 맞아요.",
    },
    "코미디": {
        "tmdb_ids": [35],
        "label": "코미디",
        "reason": "웃음 포인트와 가벼운 템포를 즐겨서, 스트레스 풀기 좋은 코미디가 잘 맞아요.",
    },
}

# ---------------------------
# Questions
# Each option starts with a tag key we can parse reliably
# ---------------------------
questions = [
    {
        "q": "1. 오랜만에 하루가 통째로 비는 날, 가장 하고 싶은 건?",
        "options": [
            ("로맨스/드라마", "A. 좋아하는 음악 틀어놓고 카페나 산책하면서 생각 정리하기"),
            ("액션/어드벤처", "B. 즉흥으로 여행 떠나거나 새로운 액티비티 도전하기"),
            ("SF/판타지", "C. 밤새 세계관 있는 영화·드라마 정주행하기"),
            ("코미디", "D. 친구들이랑 모여서 웃긴 영상이나 예능 보기"),
        ],
    },
    {
        "q": "2. 시험이 끝난 날, 나의 기분은?",
        "options": [
            ("로맨스/드라마", "A. “고생했다 나 자신…” 감정이 몰려와서 괜히 센치해진다"),
            ("액션/어드벤처", "B. 해방감 MAX! 뭐든지 할 수 있을 것 같다"),
            ("SF/판타지", "C. 이제야 현실로 돌아온 느낌… 아직도 머리는 딴 데 가 있음"),
            ("코미디", "D. 드디어 밈 돌려보고 썰 풀 시간이다"),
        ],
    },
    {
        "q": "3. 처음 만난 사람과 빨리 친해지는 방법은?",
        "options": [
            ("로맨스/드라마", "A. 진지한 얘기하다가 공감대 생기기"),
            ("액션/어드벤처", "B. 같이 뭔가 해보면서 자연스럽게 친해지기"),
            ("SF/판타지", "C. 취향·덕질 얘기로 깊게 파고들기"),
            ("코미디", "D. 농담 주고받다가 웃음 터지면서 친해지기"),
        ],
    },
    {
        "q": "4. 과제하다가 현실 도피하고 싶을 때 드는 생각은?",
        "options": [
            ("로맨스/드라마", "A. “이 시기 지나면 좀 더 괜찮아지겠지…”"),
            ("액션/어드벤처", "B. “다 때려치우고 어디론가 떠나고 싶다”"),
            ("SF/판타지", "C. “이건 내가 있는 세계선이 잘못된 게 분명해”"),
            ("코미디", "D. “이 상황 자체가 너무 웃기다ㅋㅋ”"),
        ],
    },
    {
        "q": "5. 영화 속 주인공이 된다면 가장 끌리는 설정은?",
        "options": [
            ("로맨스/드라마", "A. 관계와 감정의 변화를 섬세하게 겪는 인물"),
            ("액션/어드벤처", "B. 위기 속에서 선택을 거듭하며 성장하는 인물"),
            ("SF/판타지", "C. 다른 세계나 규칙을 마주한 특별한 존재"),
            ("코미디", "D. 사건 사고의 중심에서 분위기 메이커 역할"),
        ],
    },
]

# ---------------------------
# Helpers
# ---------------------------
def decide_genre(selected_genres: list[str]) -> str:
    """Pick the most frequent genre. If tie, break by priority."""
    priority = ["로맨스/드라마", "액션/어드벤처", "SF/판타지", "코미디"]
    counts = {g: 0 for g in GENRE_INFO.keys()}
    for g in selected_genres:
        counts[g] = counts.get(g, 0) + 1

    max_count = max(counts.values())
    tied = [g for g, c in counts.items() if c == max_count]
    for g in priority:
        if g in tied:
            return g
    return tied[0]


@st.cache_data(show_spinner=False, ttl=60 * 10)
def fetch_movies(api_key: str, genre_ids: list[int], language: str = "ko-KR", page: int = 1):
    """
    Fetch popular movies from TMDB Discover by genres.
    Uses 'with_genres' as comma-separated which means AND by default in TMDB.
    To keep results broad, we'll try:
      1) first ID only
      2) if not enough, try each ID and merge
    """
    base_url = "https://api.themoviedb.org/3/discover/movie"

    def call(with_genres: str):
        params = {
            "api_key": api_key,
            "with_genres": with_genres,
            "language": language,
            "sort_by": "popularity.desc",
            "page": page,
        }
        r = requests.get(base_url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])

    results = []
    seen = set()

    # 1) first genre only (broad, usually enough)
    primary = call(str(genre_ids[0]))
    for m in primary:
        mid = m.get("id")
        if mid and mid not in seen:
            seen.add(mid)
            results.append(m)

    # 2) if still not enough and we have multiple ids, merge from others
    if len(results) < 10 and len(genre_ids) > 1:
        for gid in genre_ids[1:]:
            more = call(str(gid))
            for m in more:
                mid = m.get("id")
                if mid and mid not in seen:
                    seen.add(mid)
                    results.append(m)
                if len(results) >= 20:
                    break

    return results


def movie_reason(user_genre: str, movie: dict) -> str:
    """
    Simple explanation based on selected genre + movie metadata.
    Keep it short and friendly.
    """
    title = movie.get("title") or movie.get("name") or "이 작품"
    vote = movie.get("vote_average")
    overview = (movie.get("overview") or "").strip()

    if user_genre == "로맨스/드라마":
        base = "감정선과 관계의 흐름에 몰입하기 좋은 타입이라"
        extra = "여운이 남는 이야기" if overview else "캐릭터 중심 전개"
    elif user_genre == "액션/어드벤처":
        base = "전개가 빠르고 사건이 몰아치는 걸 좋아해서"
        extra = "긴장감 있는 흐름" if overview else "속도감 있는 분위기"
    elif user_genre == "SF/판타지":
        base = "세계관/설정에 끌리는 편이라"
        extra = "상상력 자극하는 설정" if overview else "독특한 분위기"
    else:  # 코미디
        base = "웃으며 보기 좋은 작품을 선호해서"
        extra = "가볍게 즐기기 좋은 톤" if overview else "텐션 좋은 전개"

    score = f" (평점 {vote:.1f})" if isinstance(vote, (int, float)) else ""
    return f"{title}{score}은/는 {base} **{extra}**가 잘 맞는 추천이에요."


# ---------------------------
# Render questions
# ---------------------------
selected = []
answers = {}

for idx, item in enumerate(questions, start=1):
    option_labels = [f"{text}  —  [{genre}]" for genre, text in item["options"]]
    choice = st.radio(item["q"], option_labels, index=None, key=f"q{idx}")
    if choice is not None:
        # Extract genre from label suffix "[장르]"
        genre = choice.split("[")[-1].replace("]", "").strip()
        selected.append(genre)
        answers[idx] = choice
    st.write("")

st.divider()

# ---------------------------
# Submit button
# ---------------------------
if st.button("결과 보기", type="primary"):
    if not api_key:
        st.error("사이드바에 TMDB API Key를 먼저 입력해줘!")
        st.stop()

    if len(selected) < 5:
        st.warning("5개 질문 모두 선택해야 결과를 볼 수 있어요.")
        st.stop()

    # 1) Analyze answers -> decide genre
    final_genre = decide_genre(selected)
    info = GENRE_INFO[final_genre]

    st.subheader(f"당신의 추천 장르: **{info['label']}**")
    st.caption(info["reason"])

    # 2) Fetch movies from TMDB
    with st.spinner("분석 중... (TMDB에서 영화 찾는 중)"):
        try:
            movies = fetch_movies(api_key, info["tmdb_ids"], language="ko-KR")
        except requests.HTTPError as e:
            st.error("TMDB 요청에 실패했어요. API Key가 맞는지 확인해줘요.")
            st.exception(e)
            st.stop()
        except Exception as e:
            st.error("영화 데이터를 가져오는 중 오류가 발생했어요.")
            st.exception(e)
            st.stop()

    # 3) Take top 5 movies with poster if possible
    # Prefer movies with posters
    movies_sorted = sorted(movies, key=lambda m: (m.get("poster_path") is None, ), reverse=False)
    top5 = []
    seen_titles = set()
    for m in movies_sorted:
        title = (m.get("title") or "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        top5.append(m)
        if len(top5) == 5:
            break

    if not top5:
        st.info("추천할 영화를 찾지 못했어요. 잠시 후 다시 시도해줘요.")
        st.stop()

    st.markdown("## 🎥 추천 영화 5편")

    poster_base = "https://image.tmdb.org/t/p/w500"

    for m in top5:
        title = m.get("title") or "제목 없음"
        rating = m.get("vote_average")
        overview = (m.get("overview") or "줄거리 정보가 없어요.").strip()
        poster_path = m.get("poster_path")

        col1, col2 = st.columns([1, 2], vertical_alignment="top")

        with col1:
            if poster_path:
                st.image(poster_base + poster_path, use_container_width=True)
            else:
                st.caption("포스터 없음")

        with col2:
            st.subheader(title)
            if isinstance(rating, (int, float)):
                st.write(f"⭐ 평점: **{rating:.1f}**")
            else:
                st.write("⭐ 평점: 정보 없음")

            st.write(overview)
            st.info("💡 " + movie_reason(final_genre, m))

        st.divider()

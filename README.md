# MoodPick (무드픽)

## 앱 소개
MoodPick은 사용자의 **기분·날씨·상황·시간**을 입력받아, 지금 하기 좋은 **현실적인 소규모 활동 1~3개**를 추천해주는 Streamlit AI 앱입니다. 추천과 어울리는 **영화/TV 콘텐츠**도 TMDB를 통해 함께 보여줍니다.

## 주요 기능
- **상황 입력 UI**: 기분/날씨/분위기/시간 + 추가 제약(선택)
- **AI 맞춤 추천**: 활동 1~3개 + 한 줄 설명 + 추천 이유 + 바로 시작 단계
- **영화/TV 추천 연동(TMDB)**: 영화/TV/둘 다 토글, 장르 기반(Discover) 추천 + 검색 보완
- **히스토리 저장/조회**: 추천 결과를 로컬 JSON 파일로 저장하고 다시 보기

## 사용법
1. 사이드바에 **OpenAI API Key**(필수)와 **TMDB API Key**(선택)를 입력합니다.  
2. 왼쪽에서 기분/날씨/상황/시간을 선택하고 **추천 받기**를 클릭합니다.  
3. 추천 카드와 함께 영화/TV 추천이 표시됩니다( TMDB 키 입력 시 ).  
4. 마음에 들면 **저장하기**로 히스토리에 저장합니다.

## 기술 스택
- **Frontend/App**: Streamlit
- **LLM**: OpenAI Responses API (Structured Outputs, JSON Schema)
- **콘텐츠 데이터**: TMDB API (Discover / Search)
- **기타**: Python, requests, 로컬 JSON 저장

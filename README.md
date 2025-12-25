# AI 뉴스 챗봇 (3Model AskMeAI)

## 📌 프로젝트 개요
AI 기반 뉴스 검색 및 대화형 챗봇 시스템입니다. MongoDB와 Elasticsearch를 활용하여 뉴스 기사를 크롤링, 저장, 검색하며, Gemini, ChatGPT, Claude 세 가지 AI 모델을 통해 사용자 질문에 답변합니다.

## ✨ 주요 기능

### 1. 다중 AI 모델 지원
- **Gemini (Google)**: gemini-2.0-flash-exp
- **ChatGPT (OpenAI)**: gpt-4o-mini
- **Claude (Anthropic)**: claude-3-5-sonnet-20241022

### 2. 뉴스 크롤링 시스템
- 뉴스 사이트(newstheai.com)에서 자동 크롤링
- 기사 본문, 제목, 발행일, URL 수집
- 텍스트 전처리 및 카테고리 자동 분류
- MongoDB에 저장 및 중복 체크

### 3. 의미 기반 검색
- Elasticsearch를 활용한 시맨틱 검색
- N-gram 분석 및 퍼지 매칭
- 관련도 점수(relevance score) 기반 기사 순위화
- 하이브리드 검색 모드 지원

### 4. 지능형 답변 생성
- 질문 의도 분석
- 기사 관련도에 따른 답변 전략 자동 선택:
  - **관련 기사 없음**: 일반 지식 기반 답변
  - **낮은 관련도 (< 0.3)**: 하이브리드 모드 (기사 + 일반 지식)
  - **높은 관련도 (≥ 0.3)**: 풀 컨텍스트 모드 (기사 중심)
- 2단계 답변 생성 및 검토 시스템

### 5. 사용자 인터페이스
- Streamlit 기반 웹 인터페이스
- 사용자 인증 시스템 (streamlit-authenticator)
- 검색 히스토리 관리
- 관련 기사 자동 표시 (최대 4개)
- 실시간 대화형 챗 인터페이스

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐
│   Streamlit UI  │
│    (app.py)     │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
┌────────▼────────┐  ┌─────▼──────────┐
│ Query Processing│  │   Crawling     │
│ (query_action)  │  │  (chrawling_   │
│                 │  │   mongoDB.py)  │
└────┬───────┬────┘  └───────┬────────┘
     │       │               │
     │       │               │
┌────▼───┐ ┌─▼────────┐ ┌───▼────────┐
│ Gemini │ │ ChatGPT  │ │  MongoDB   │
│ Claude │ │          │ │            │
└────────┘ └──────────┘ └─────┬──────┘
                              │
                        ┌─────▼──────┐
                        │Elasticsearch│
                        └────────────┘
```

## 📦 설치 방법

### 1. 필수 요구사항
- Python 3.8 이상
- MongoDB 계정
- Elasticsearch 계정
- AI 모델 API 키 (Gemini, OpenAI, Anthropic)

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 설정

#### config.yaml 설정
사용자 인증 정보를 설정합니다:
```yaml
credentials:
  usernames:
    admin:
      email: admin@example.com
      name: 관리자
      password: "$2b$12$..." # bcrypt 해시
cookie:
  expiry_days: 30
  key: some_signature_key
  name: news_chatbot_cookie
```

#### Streamlit Secrets 설정
`.streamlit/secrets.toml` 파일을 생성하고 API 키를 추가합니다:
```toml
GEMINI_API_KEY = "your-gemini-api-key"
OPENAI_API_KEY = "your-openai-api-key"
ANTHROPIC_API_KEY = "your-anthropic-api-key"
```

#### 데이터베이스 연결 정보
코드 내에서 다음 정보를 업데이트하세요:
- MongoDB 연결 문자열 (chrawling_mongoDB.py, query_action.py)
- Elasticsearch 연결 정보 및 API 키 (query_action.py)

##  실행 방법

### 1. 뉴스 크롤링 실행
```bash
python chrawling_mongoDB.py
```
- 최대 75페이지까지 크롤링
- 3페이지 연속 신규 기사 없을 시 자동 중단
- MongoDB에 자동 저장 및 인덱싱

### 2. 웹 애플리케이션 실행
```bash
streamlit run app.py
```
- 브라우저에서 자동으로 열림 (기본: http://localhost:8501)
- 초기 실행 시 MongoDB → Elasticsearch 동기화 자동 수행

### 3. 로그인
- **기본 계정**: admin
- **기본 비밀번호**: admin123

## 📖 사용 방법

1. **로그인**: config.yaml에 설정된 계정으로 로그인
2. **AI 모델 선택**: 드롭다운에서 Gemini, ChatGPT, Claude 중 선택
3. **질문 입력**: 채팅창에 뉴스 관련 질문 입력
   - 예: "최근 AI 기술 동향이 궁금해요"
   - 예: "스타트업 투자 현황에 대해 알려주세요"
4. **답변 확인**: AI가 관련 기사를 찾아 답변을 생성
5. **관련 기사 확인**: 답변 하단에 표시되는 관련 기사 링크 클릭

### 검색 히스토리
- 사이드바에서 이전 검색 기록 확인
- 클릭 시 해당 대화 내용 복원
- "대화 삭제" 버튼으로 현재 세션 초기화

##  파일 구조

```
3model_askmeai-main/
├── app.py                    # Streamlit 메인 앱
├── query_action.py           # 검색 및 답변 생성 로직
├── chrawling_mongoDB.py      # 뉴스 크롤링 스크립트
├── config.yaml               # 사용자 인증 설정
├── requirements.txt          # Python 의존성
└── README.md                 # 프로젝트 문서
```

## 🔧 주요 클래스 및 함수

### app.py
- `AuthenticatedChatbot`: 메인 애플리케이션 클래스
  - `login_user()`: 사용자 인증
  - `process_user_input()`: 사용자 질문 처리
  - `render_sidebar()`: 사이드바 렌더링
  - `run()`: 앱 실행

### query_action.py
- `DatabaseSearch`: MongoDB/Elasticsearch 검색
  - `semantic_search()`: 의미 기반 검색
  - `sync_mongodb_to_elasticsearch()`: DB 동기화
  
- `ResponseGeneration`: 초기 답변 생성
  - `generate_initial_response()`: 질문 분석 및 답변 생성
  - `_call_model()`: AI 모델 호출
  
- `ResponseReview`: 답변 검토 및 개선
  - `review_and_enhance_response()`: 답변 품질 향상
  
- `NewsChatbot`: 전체 프로세스 통합
  - `process_query()`: 검색 → 답변 생성 → 검토

### chrawling_mongoDB.py
- `get_full_article_content()`: 기사 본문 추출
- `get_article_date()`: 발행일 파싱
- `crawl_page()`: 페이지별 크롤링
- `save_to_mongodb()`: 데이터 전처리 및 저장
- `categorize_content()`: 기사 카테고리 자동 분류

## 🎨 기술 스택

### Frontend
- **Streamlit**: 웹 UI 프레임워크
- **streamlit-authenticator**: 사용자 인증

### Backend
- **Python 3.x**: 메인 개발 언어
- **AsyncIO**: 비동기 처리

### 데이터베이스
- **MongoDB**: 문서 저장소
- **Elasticsearch**: 검색 엔진

### AI/ML
- **Google Generative AI (Gemini)**: 구글 AI 모델
- **OpenAI (ChatGPT)**: GPT-4o-mini
- **Anthropic (Claude)**: Claude 3.5 Sonnet

### 크롤링
- **BeautifulSoup4**: HTML 파싱
- **Requests**: HTTP 요청

## 🔐 보안 고려사항

1. **API 키 관리**: 모든 API 키는 `secrets.toml`에 저장
2. **비밀번호 해싱**: bcrypt를 사용한 비밀번호 암호화
3. **쿠키 보안**: 서명 키를 통한 세션 쿠키 보호
4. **연결 암호화**: MongoDB/Elasticsearch HTTPS 연결

## ⚠️ 주의사항

1. **API 사용량**: 각 AI 모델의 API 사용량 및 요금 확인 필요
2. **크롤링 주기**: 과도한 크롤링은 서버 부담을 줄 수 있음
3. **데이터 저장**: MongoDB 용량 관리 필요
4. **네트워크 연결**: 안정적인 인터넷 연결 필요



## 📊 성능 최적화

- **벌크 인덱싱**: 500개 단위로 Elasticsearch 벌크 인덱싱
- **캐싱**: Streamlit 세션 스테이트를 통한 상태 관리
- **비동기 처리**: AsyncIO를 통한 검색 성능 향상
- **인덱스 최적화**: MongoDB에 URL, 카테고리, 날짜 인덱스 생성



import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from query_action import DatabaseSearch, ResponseGeneration, ResponseReview, NewsChatbot

# 페이지 설정
st.set_page_config(
    page_title="AI Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS
st.markdown(
    """
    <style>
    .stApp {
        background-color: white;
    }
    .css-1d391kg {
        padding-top: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        background-color: #f7f7f8;
    }
    .chat-history-item {
        padding: 0.5rem; cursor: pointer; border-radius: 0.3rem;
    }
    .chat-history-item:hover {
        background-color: #f0f0f0;
    }
    .model-selector {
        margin-top: 1rem; width: 100%;
    }
    .header-icon {
        font-size: 1.2rem; margin-right: 0.5rem; color: #666;
    }
    .search-box {
        padding: 0.5rem; border-radius: 0.3rem; border: 1px solid #ddd;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


class AuthenticatedChatbot:
    def __init__(self):
        # 1) config.yaml 로드
        with open("config.yaml") as file:
            self.config = yaml.load(file, SafeLoader)

        # 2) streamlit_authenticator 초기화
        self.authenticator = stauth.Authenticate(
            self.config["credentials"],
            self.config["cookie"]["name"],
            self.config["cookie"]["key"],
            self.config["cookie"]["expiry_days"],
        )
        self.init_session_state()

    def init_session_state(self):
        # 인증 상태
        if "authentication_status" not in st.session_state:
            st.session_state.authentication_status = None

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = {
                "today": [],
                "yesterday": [],
                "previous_7_days": [],
            }
        # 모델 선택 (기본값 Gemini)
        if "current_model" not in st.session_state:
            st.session_state.current_model = "Gemini"

        if "selected_chat" not in st.session_state:
            st.session_state.selected_chat = None
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "search_query" not in st.session_state:
            st.session_state.search_query = ""
        if "search_history" not in st.session_state:
            st.session_state.search_history = []
        if "article_history" not in st.session_state:
            st.session_state.article_history = []
        if "chatbot" not in st.session_state:
            st.session_state.chatbot = NewsChatbot()

    def login_user(self):
        """로그인 처리"""
        try:
            name, auth_status, username = self.authenticator.login("로그인", "main")

            if auth_status:
                self.authenticator.logout("로그아웃", "sidebar")
                st.sidebar.success(f"환영합니다 *{name}*님")
                return True
            elif auth_status == False:
                st.error("아이디/비밀번호가 올바르지 않습니다")
                return False
            elif auth_status == None:
                st.warning("아이디와 비밀번호를 입력해주세요")
                return False
        except Exception as e:
            st.error(f"로그인 처리 중 오류: {str(e)}")
            return False

    async def process_user_input(self, user_input):
        """사용자 입력 처리"""
        if not user_input:
            return

        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.status("AI가 답변을 생성하고 있습니다...") as status:
            try:
                # 사이드바에서 선택된 모델
                model_name = st.session_state.current_model

                # NewsChatbot 호출
                main_article, related_articles, score, response = (
                    await st.session_state.chatbot.process_query(user_input, model_name)
                )

                # “개선된 답변”, “개선 사항”, “개선점” 차단
                lines = response.splitlines()
                filtered_lines = []
                skip_remaining = False

                for line in lines:
                    if "개선된 답변" in line:
                        continue
                    if ("개선 사항" in line) or ("개선점" in line):
                        skip_remaining = True
                    if not skip_remaining:
                        filtered_lines.append(line)

                cleaned_response = "\n".join(filtered_lines)

                # 기사 목록
                combined = [main_article] + related_articles if main_article else []

                # 어시스턴트 메시지
                with st.chat_message("assistant"):
                    st.markdown(cleaned_response)
                    if combined:
                        st.markdown("### 📚 관련 기사")
                        for i in range(0, min(len(combined), 4), 2):
                            col1, col2 = st.columns(2)
                            with col1:
                                if i < len(combined):
                                    art = combined[i]
                                    st.markdown(
                                        f"""
                                        #### {i+1}. {art.get('title', '제목 없음')}
                                        - 📅 발행일: {art.get('published_date', '날짜 정보 없음')}
                                        - 🔗 [기사 링크]({art.get('url', '#')})
                                        - 📊 카테고리: {', '.join(art.get('categories', ['미분류']))}
                                    """
                                    )
                            with col2:
                                if i + 1 < len(combined):
                                    art = combined[i + 1]
                                    st.markdown(
                                        f"""
                                        #### {i+2}. {art.get('title', '제목 없음')}
                                        - 📅 발행일: {art.get('published_date', '날짜 정보 없음')}
                                        - 🔗 [기사 링크]({art.get('url', '#')})
                                        - 📊 카테고리: {', '.join(art.get('categories', ['미분류']))}
                                    """
                                    )

                # 히스토리
                if main_article:
                    st.session_state.article_history.append(main_article)

                st.session_state.search_history.append(
                    {
                        "question": user_input,
                        "answer": cleaned_response,
                        "articles": combined,
                    }
                )

                status.update(label="완료!", state="complete")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")
                status.update(label="오류 발생", state="error")

    def display_chat_message(self, role, content, articles=None):
        """대화 메시지 표시 (검색 히스토리 복원 등에서 사용)"""
        with st.chat_message(role):
            st.markdown(content)
            if articles and role == "assistant" and len(articles) > 0:
                st.markdown("### 📚 관련 기사")
                for i in range(0, min(len(articles), 4), 2):
                    col1, col2 = st.columns(2)
                    if i < len(articles):
                        art = articles[i]
                        with col1:
                            st.markdown(
                                f"""
                                #### {i+1}. {art.get('title', '제목 없음')}
                                - 📅 발행일: {art.get('published_date', '날짜 정보 없음')}
                                - 🔗 [기사 링크]({art.get('url', '#')})
                                - 📊 카테고리: {', '.join(art.get('categories', ['미분류']))}
                            """
                            )
                    if i + 1 < len(articles):
                        art = articles[i + 1]
                        with col2:
                            st.markdown(
                                f"""
                                #### {i+2}. {art.get('title', '제목 없음')}
                                - 📅 발행일: {art.get('published_date', '날짜 정보 없음')}
                                - 🔗 [기사 링크]({art.get('url', '#')})
                                - 📊 카테고리: {', '.join(art.get('categories', ['미분류']))}
                            """
                            )

    def render_sidebar(self):
        """사이드바: 모델 선택 + 히스토리 + 대화 삭제"""
        with st.sidebar:

            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown("### 검색 히스토리")
            with col2:
                if st.button("대화 삭제"):
                    st.session_state.messages = []
                    st.session_state.search_history = []
                    st.session_state.article_history = []
                    st.session_state.selected_chat = None
                    st.experimental_rerun()

            for i, item in enumerate(st.session_state.search_history):
                q = item["question"]
                if st.button(q if q else "무제", key=f"search_history_{i}"):
                    st.session_state.selected_chat = {
                        "question": item["question"],
                        "response": item["answer"],
                        "articles": item["articles"],
                    }

    def run(self):
        """메인 앱 실행"""
        # 인증 체크
        if "authentication_status" not in st.session_state:
            st.session_state["authentication_status"] = None

        if not st.session_state["authentication_status"]:
            if not self.login_user():
                return

        # 모델 선택
        st.selectbox(
            "AI 모델 선택", ["Gemini", "chatGPT", "Claude"], key="current_model"
        )

        st.markdown(
            """
         ### 👋 안녕하세요! AI 뉴스 챗봇입니다.
         뉴스 기사에 대해 궁금한 점을 자유롭게 물어보세요. 관련 기사를 찾아 답변해드립니다.

         **예시 질문:**
         - "최근 AI 기술 동향이 궁금해요"
         - "스타트업 투자 현황에 대해 알려주세요"
         - "새로운 AI 서비스에는 어떤 것들이 있나요?"
        """
        )

        # 사이드바 렌더링 (모델 선택 포함)
        self.render_sidebar()

        # 기존 검색 클릭 복원
        if st.session_state.selected_chat:
            self.display_chat_message(
                "user", st.session_state.selected_chat["question"]
            )
            self.display_chat_message(
                "assistant",
                st.session_state.selected_chat["response"],
                st.session_state.selected_chat["articles"],
            )

        # 새 입력
        user_input = st.chat_input("메시지를 입력하세요...")
        if user_input:
            asyncio.run(self.process_user_input(user_input))


def main():
    app = AuthenticatedChatbot()
    app.run()


if __name__ == "__main__":
    if "initialized" not in st.session_state:
        try:
            db = DatabaseSearch()
            db.sync_mongodb_to_elasticsearch()
            st.session_state.bot = AuthenticatedChatbot()
            st.session_state.initialized = True
        except Exception as e:
            st.error(f"초기화 오류: {str(e)}")
            st.stop()

    try:
        st.session_state.bot.run()
    except Exception as e:
        st.error(f"실행 오류: {str(e)}")

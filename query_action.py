from elasticsearch import Elasticsearch
from pymongo import MongoClient
from datetime import datetime
import asyncio
import os
import streamlit as st

# ======== Gemini (Google Generative AI) ========
from google.generativeai import configure as palm_configure
from google.generativeai import GenerativeModel as PalmModel

# ======== OpenAI (chatGPT) ========
import openai

# ======== Anthropic (Claude) ========
import anthropic


class DatabaseSearch:
    """Mongo + Elasticsearch 로 뉴스 기사 검색"""

    def __init__(self):
        # 1) Mongo 연결
        try:
            self.mongo_client = MongoClient(
                "mongodb+srv://clairetranslatorno1:qwFDNE011iRVTH1g@cluster0.guwrj.mongodb.net/crawlingdb",
                serverSelectionTimeoutMS=5000,
            )
            self.mongo_client.server_info()
            self.db = self.mongo_client["crawlingdb"]
            self.mongo_collection = self.db["articles"]
        except Exception as e:
            st.error(f"MongoDB 연결 실패: {e}")
            raise

        # 2) Elasticsearch 연결
        try:
            self.es = Elasticsearch(
                "https://my-elasticsearch-project-e8b084.es.us-east-1.aws.elastic.cloud:443",
                api_key="eld0RmVKUUI5LUtzQm51ZlJ1Sy06TVdOREExV2dRWWlDdGgxTjZuSHFKZw==",
                verify_certs=True,
            )
            if not self.es.ping():
                st.error("Elasticsearch 서버 연결 실패.")
                raise ConnectionError("Elasticsearch 서버에 연결할 수 없습니다.")
        except Exception as e:
            st.error(f"Elasticsearch 연결 실패: {e}")
            raise

    async def semantic_search(self, query, size=7):
        """의미 기반 검색"""
        try:
            # (간단 키워드 추출)
            words = query.replace("?", "").replace(".", "").split()
            keywords_str = " ".join(words)

            search_query = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match_phrase": {
                                    "cleaned_content": {
                                        "query": query,
                                        "boost": 5,
                                        "slop": 2,
                                    }
                                }
                            },
                            {
                                "multi_match": {
                                    "query": keywords_str,
                                    "fields": [
                                        "title^3",
                                        "title.ngram^2",
                                        "cleaned_content^2",
                                        "cleaned_content.ngram",
                                    ],
                                    "type": "best_fields",
                                    "operator": "or",
                                    "fuzziness": "AUTO",
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": size,
                "sort": [{"_score": "desc"}],
            }

            result = self.es.search(index="news_articles", body=search_query)
            processed = []
            for hit in result["hits"]["hits"]:
                s = hit["_source"]
                processed.append(
                    {
                        "title": s["title"],
                        "content": s["cleaned_content"],
                        "url": s["url"],
                        "published_date": s.get("published_date", "날짜 정보 없음"),
                        "categories": s.get("categories", []),
                        "score": hit["_score"],
                    }
                )
            return processed
        except Exception as e:
            st.error(f"검색 오류: {e}")
            return []


class ResponseGeneration:
    """
    뉴스 기사 기반 '초기 답변' 생성:
      1) 의도 분석
      2) 기사 없으면 knowledge mode
      3) 기사 있으면:
         - relevance<0.3 => 하이브리드
         - else => full context
      4) 모델별 (Gemini/chatGPT/Claude) 로직
    """

    def __init__(self):
        # Gemini API
        try:
            gem_key = st.secrets["GEMINI_API_KEY"]
            palm_configure(api_key=gem_key)
            self.gemini_model = PalmModel("gemini-2.0-flash-exp")
        except Exception as e:
            st.error(f"Gemini API 설정 오류: {e}")
            self.gemini_model = None

        # OpenAI API
        try:
            openai.api_key = st.secrets["OPENAI_API_KEY"]
        except Exception as e:
            st.error(f"OpenAI API 설정 오류: {e}")

        # Anthropic API
        try:
            self.anthropic_client = anthropic.Client(
                api_key=st.secrets["ANTHROPIC_API_KEY"]
            )
        except Exception as e:
            st.error(f"Anthropic API 설정 오류: {e}")
            self.anthropic_client = None

    def generate_initial_response(self, model_name, query, articles):
        """
        공통 '의도 분석 프롬프트' => (기사 없으면 / 하이브리드 / 풀컨텍스트) => 각 모델별 LLM 호출
        반환값: best_article, related_articles, relevance_score, initial_response, intent_analysis
        """
        # 1) 의도분석
        intent_prompt = f"""다음 질문의 의도를 파악하고, 핵심 키워드와 찾아야 할 정보를 요약해 주세요:
질문: {query}

출력 형식 예:
1. 질문 유형:
2. 핵심 키워드:
3. 필요한 정보:
"""
        intent_analysis = self._call_model(model_name, intent_prompt)

        if not articles:
            # 기사 없음 => general knowledge
            knowledge_prompt = f"""당신은 AI 뉴스 챗봇입니다.
질문 분석:
{intent_analysis}
기사가 없으므로 일반 지식으로 답변하세요.
"""
            init_resp = self._call_model(model_name, knowledge_prompt)
            return None, [], 0.0, init_resp, intent_analysis
        else:
            best = articles[0]
            score = best["score"]
            # (2) 하이브리드 vs 풀컨텍스트
            if score < 0.3:
                # 하이브리드
                prompt = f"""당신은 AI 뉴스 챗봇입니다.
질문: {query}
질문 분석:
{intent_analysis}

관련성이 낮은 기사:
제목: {best['title']}
내용: {best['content'][:500]}

- 기사 일부와 일반 지식을 함께 활용
- 기사 정보와 일반 지식 구분
"""
                init_resp = self._call_model(model_name, prompt)
                return best, articles[1:9], score, init_resp, intent_analysis
            else:
                # 풀컨텍스트
                extra = ""
                for i, art in enumerate(articles[1:3], start=1):
                    extra += (
                        f"- 추가기사{i}: {art['title']} (score={art['score']:.2f})\n"
                    )

                prompt = f"""당신은 AI 뉴스 챗봇입니다.
질문: {query}
질문 분석:
{intent_analysis}

주요 기사:
- 제목: {best['title']}
- 내용 일부: {best['content'][:500]}...
- score={score:.2f}

추가 기사:
{extra if extra else '없음'}

가능하면 기사 내용 우선 활용, 필요한 경우 일반 지식.
"""
                init_resp = self._call_model(model_name, prompt)
                return best, articles[1:9], score, init_resp, intent_analysis

    def _call_model(self, model_name, prompt_text):
        """모델별 호출"""
        if model_name == "Gemini":
            if not self.gemini_model:
                return "Gemini 모델 오류"
            resp = self.gemini_model.generate_content(prompt_text)
            return resp.text

        elif model_name == "chatGPT":
            # gpt-4o-mini
            completion = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=512,
            )
            return completion.choices[0].message.content

        elif model_name == "Claude":
            if not self.anthropic_client:
                return "Anthropic 설정 오류"
            claude_prompt = (
                f"{anthropic.HUMAN_PROMPT} {prompt_text}\n{anthropic.AI_PROMPT}"
            )
            resp = self.anthropic_client.completions.create(
                model="claude-3-5-sonnet-20241022",
                prompt=claude_prompt,
                max_tokens_to_sample=512,
            )
            return resp.completion
        else:
            return "알 수 없는 모델"


class ResponseReview:
    """답변 검토(리뷰) -> 동일 모델로 재호출"""

    def __init__(self):
        # 모델별 객체 재사용하려면 ResponseGeneration 객체를 참조해야 함
        # 여기서는 간단히 secrets 재활용
        try:
            gem_key = st.secrets["GEMINI_API_KEY"]
            palm_configure(api_key=gem_key)
            self.gemini_model = PalmModel("gemini-2.0-flash-exp")
        except:
            self.gemini_model = None

        try:
            openai.api_key = st.secrets["OPENAI_API_KEY"]
        except:
            pass

        try:
            self.anthropic_client = anthropic.Client(
                api_key=st.secrets["ANTHROPIC_API_KEY"]
            )
        except:
            self.anthropic_client = None

    def review_and_enhance_response(
        self,
        model_name,
        query,
        initial_response,
        intent_analysis,
        best_article,
        has_articles,
    ):
        """(기사 있으면 기사 기반, 없으면 일반) -> 동일 모델로 '개선 프롬프트'"""
        if has_articles and best_article:
            # 기사 기반
            review_prompt = f"""답변 검토:
질문: {query}
의도분석: {intent_analysis}
주요 기사: {best_article['title']} (score={best_article.get('score',0):.2f})
현재 답변: {initial_response}

답변이 적절한지 평가 후, 필요 시 개선된 최종 답만 제시.
불필요하면 '원본 답변 사용'만 출력.
"""
        else:
            # 일반
            review_prompt = f"""답변 검토:
질문: {query}
의도분석: {intent_analysis}
(기사 없음)
현재 답변: {initial_response}

답변이 적절한지 평가 후, 필요 시 개선된 최종 답만 제시.
불필요하면 '원본 답변 사용'만 출력.
"""

        improved = self._review_call(model_name, review_prompt)

        if "원본 답변 사용" in improved:
            return initial_response
        return improved

    def _review_call(self, model_name, prompt_text):
        """모델별 재호출 -> 개선된 답변"""
        if model_name == "Gemini":
            if not self.gemini_model:
                return "Gemini 모델 오류"
            resp = self.gemini_model.generate_content(prompt_text)
            return resp.text

        elif model_name == "chatGPT":
            c = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=512,
            )
            return c.choices[0].message.content

        elif model_name == "Claude":
            if not self.anthropic_client:
                return "(Claude 오류)"
            claude_prompt = (
                f"{anthropic.HUMAN_PROMPT} {prompt_text}\n{anthropic.AI_PROMPT}"
            )
            resp = self.anthropic_client.completions.create(
                model="claude-3-5-sonnet-20241022",
                prompt=claude_prompt,
                max_tokens_to_sample=512,
            )
            return resp.completion
        else:
            return prompt_text  # 알 수 없는 모델 -> 그대로 반환


class NewsChatbot:
    """검색 -> 초기답변 -> 리뷰 -> 최종"""

    def __init__(self):
        self.db_search = DatabaseSearch()
        self.response_gen = ResponseGeneration()
        self.response_review = ResponseReview()

    async def process_query(self, query, model_name="Gemini"):
        try:
            # 1) 기사 검색
            articles = await self.db_search.semantic_search(query)

            # 2) 초기답변
            result = self.response_gen.generate_initial_response(
                model_name, query, articles
            )
            # unpack
            if len(result) == 5:
                (
                    best_article,
                    related_articles,
                    relevance_score,
                    init_resp,
                    intent_analysis,
                ) = result
            else:
                # (best_article, related_articles, score, init_resp)
                best_article, related_articles, relevance_score, init_resp = result
                intent_analysis = "(분석 없음)"

            # 3) 리뷰
            final_resp = self.response_review.review_and_enhance_response(
                model_name,
                query,
                init_resp,
                intent_analysis,
                best_article,
                bool(best_article),
            )

            return best_article, related_articles, relevance_score, final_resp

        except Exception as e:
            st.error(f"쿼리 처리 중 오류: {e}")
            return None, [], 0.0, "오류가 발생했습니다."

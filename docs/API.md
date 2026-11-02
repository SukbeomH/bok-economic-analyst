# API Reference

> Wiki-multiagents v2.4 — 모듈별 공개 인터페이스 문서

## 목차

- [core.config](#coreconfig)
- [core.model_factory](#coremodel_factory)
- [core.rag_pipeline](#corerag_pipeline)
- [core.state_manager](#corestate_manager)
- [core.chart_generator](#corechart_generator)
- [core.citation](#corecitation)
- [core.feedback](#corefeedback)
- [core.kosis_client](#corekosis_client)
- [core.logger](#corelogger)
- [core.report_generator](#corereport_generator)
- [core.web_search](#coreweb_search)
- [components](#components)
- [utils](#utils)
- [app (메인)](#app-메인)

---

## core.config

중앙 설정 관리. `.env` 파일에서 환경 변수를 로드하여 애플리케이션 전체에 제공.

### `Config`

| 설정 그룹 | 주요 항목 |
|-----------|----------|
| 모델 API | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL` |
| RAG | `RAG_SEARCH_STRATEGY`, `RAG_K`, `RAG_FETCH_K`, `RAG_LAMBDA_MULT`, `RAG_SCORE_THRESHOLD`, `RAG_USE_COMPRESSION` |
| 앱 동작 | `MAX_ITERATIONS`, `TIMEOUT_SECONDS`, `MAX_HISTORY_TURNS`, `DATA_DIR` |
| 선택 | `KOSIS_API_KEY`, `DEBUG_MODE`, `USE_CACHE` |

**메서드**

```python
validate_required_settings() -> Dict[str, str]
```
선택한 제공자의 모델·키·호환 API 주소를 검증. 임베딩 제공자는 Claude를 지원하지 않음. 누락 항목을 `{"항목명": "설명"}` 형태로 반환.

```python
get_all_settings() -> Dict[str, Any]
```
설정값을 딕셔너리로 반환. API 키는 값 대신 설정 여부만 포함.

```python
get_environment_info() -> Dict[str, Any]
```
Python 버전, 플랫폼, 파일 존재 여부, 유효성 검증 결과를 반환.

---

## core.model_factory

선택한 채팅·임베딩 모델 인스턴스의 생성과 캐싱을 관리. 채팅과 임베딩의 키·모델·주소는 독립적으로 사용.

### `ModelFactory`

```python
get_chat_model(temperature: float = 0) -> BaseChatModel
```
OpenAI·Claude·OpenAI 호환 Chat 모델 인스턴스를 반환. 동일 temperature 요청 시 캐시된 인스턴스 재사용.

```python
get_embedding_model() -> Embeddings
```
OpenAI 또는 호환 API의 임베딩 모델을 반환. 인스턴스별로 캐시함.

```python
clear_cache() -> None
```
모든 캐시된 모델 인스턴스를 제거.

---

## core.rag_pipeline

PDF 로드, FAISS 벡터화, 리트리버 생성을 담당하는 RAG 파이프라인.

### `RAGPipeline(model_factory: ModelFactory)`

```python
build_pipeline(cache_key: str) -> Retriever
```
`data/` 폴더의 PDF를 로드하여 FAISS 인덱스를 구축하고 리트리버를 반환. PDF 파일 목록·수정시각·크기, 임베딩 제공자·모델·주소와 `cache_key`가 일치하면 캐시된 인덱스를 재사용. 이전 숫자 형식 마커는 재구축.

```python
create_mmr_retriever(vectorstore, k=5, fetch_k=20, lambda_mult=0.7) -> Retriever
```
MMR(Maximal Marginal Relevance) 기반 리트리버 생성. 다양성과 관련성의 균형.

```python
create_similarity_retriever(vectorstore, k=5, score_threshold=0.7) -> Retriever
```
유사도 점수 기반 리트리버 생성.

```python
create_relaxed_similarity_retriever(vectorstore, k=10, score_threshold=0.3) -> Retriever
```
낮은 임계값의 폴백 리트리버. 주 리트리버가 결과를 못 찾을 때 사용.

```python
create_compressed_retriever(base_retriever, llm) -> Retriever
```
LLM 기반 문맥 압축을 적용한 리트리버. `RAG_USE_COMPRESSION=true` 시 활성화.

### 모듈 함수

```python
build_rag_pipeline(cache_key: str) -> Retriever
```
`@st.cache_resource` 데코레이터로 캐싱되는 최상위 파이프라인 빌더.

---

## core.state_manager

Streamlit 세션 상태의 중앙 관리.

### `StateManager`

| 상태 키 | 용도 |
|---------|------|
| `MESSAGES` | 대화 메시지 목록 |
| `AGENT_GRAPH` | 컴파일된 LangGraph 인스턴스 |
| `WEB_SEARCH_ENABLED` | 웹 검색 토글 |
| `SHOW_LOGS` | 로그 표시 토글 |
| `FEEDBACK_INDEX` | 피드백 위젯 키 인덱스 |

**주요 메서드** (모두 `@classmethod`)

```python
initialize_session_state() -> None        # 전체 상태 초기화
get_messages() -> List[Dict[str, str]]    # 메시지 목록 반환
add_message(role: str, content: str)      # 메시지 추가
clear_messages() -> None                  # 대화 초기화
get_agent_graph()                         # 그래프 반환
set_agent_graph(graph, version=None)      # 그래프 저장
is_agent_graph_valid() -> bool            # 버전 일치 확인
reset_all() -> None                       # 전체 리셋
```

---

## core.chart_generator

LLM 응답에서 차트 데이터를 추출하여 Plotly 차트로 변환.

```python
extract_chart_data(text: str) -> Optional[dict]
```
응답 텍스트에서 ` ```chart_data ... ``` ` 블록을 파싱. JSON 파싱 실패 시 `None` 반환.

```python
create_chart(data: dict) -> Optional[go.Figure]
```
파싱된 차트 데이터를 Plotly Figure로 변환.

**지원 차트 형식:**
- `type`: `"line"`, `"bar"`, `"scatter"`
- 단일 시리즈: `{"labels": [...], "values": [...]}`
- 멀티 시리즈: `{"labels": [...], "series": [{"name": "...", "values": [...]}]}`

---

## core.citation

출처 정보 추출 및 포매팅.

```python
format_retriever_results(docs: List[Document]) -> str
```
LangChain Document 리스트를 출처 정보(파일명, 페이지)가 포함된 텍스트로 변환.

```python
wrap_retriever_with_citation(retriever) -> Callable
```
리트리버를 래핑하여 검색 결과에 출처 정보를 자동 추가하는 함수를 반환.

---

## core.feedback

사용자 피드백 수집 및 저장. JSONL 파일 기반.

```python
save_feedback(query: str, response: str, rating: int, comment: Optional[str] = None) -> bool
```
피드백을 `feedback.jsonl`에 저장. `rating`: 1=긍정, 0=부정.

```python
get_feedback_stats() -> dict
```
반환: `{"total": int, "positive": int, "negative": int}`

---

## core.kosis_client

국가통계포털(KOSIS) API 클라이언트. `KOSIS_API_KEY` 설정 시 활성화.

```python
search_kosis(query: str, org_id: str = "", tbl_id: str = "", max_results: int = 5) -> str
```
CPI, GDP, 실업률 등 경제 통계를 검색하여 포매팅된 문자열을 반환.

---

## core.logger

버퍼 기반 로깅 시스템. UI에 로그를 표시하기 위한 캡처 기능 포함.

### `Logger`

```python
info(message, *args) -> None
warning(message, *args) -> None
error(message, *args) -> None
debug(message, *args) -> None
get_recent_logs(count: int = 20) -> List[str]   # 최근 로그 반환
clear_logs() -> None
```

### 전역 인스턴스

```python
from core.logger import logger
logger.info("메시지")
```

---

## core.report_generator

분석 결과를 Markdown 보고서로 생성.

```python
generate_report(
    query: str,
    response: str,
    sources: List[dict],
    chart_titles: Optional[List[str]] = None
) -> str
```
타임스탬프, 질문, 분석 결과, 출처 목록, 차트 제목을 포함한 Markdown 문자열을 반환.

---

## core.web_search

DuckDuckGo 기반 웹 검색. 지수 백오프 재시도 로직 포함.

### `WebSearchTool(max_retries=3, initial_retry_delay=1.0)`

```python
search(query: str, max_results: int = 5) -> str
```
검색 결과를 포매팅된 문자열로 반환. 최대 3회 재시도.

### 전역 인스턴스

```python
from core.web_search import web_search_func
result = web_search_func("한국은행 기준금리", max_results=5)
```

---

## components

Streamlit UI 컴포넌트.

### `components.chat_interface`

```python
render_chat_interface() -> Optional[str]       # 채팅 UI 렌더링, 사용자 입력 반환
render_chat_messages() -> None                  # 저장된 메시지 표시
render_evidence_preview(final_response) -> None # 출처 미리보기 (PDF 뷰어 포함)
```

### `components.sidebar`

```python
render_sidebar() -> Optional[UploadedFile]     # 사이드바 렌더링, 업로드 파일 반환
export_conversation() -> None                   # 대화 내역 다운로드 버튼
```

### `components.common`

```python
render_header(title: str, description: str = "")
render_footer()
render_status_badge(status: str, color: str = "blue")
render_metric_card(title: str, value: str, description: str = "")
render_info_box(title: str, content: str)
render_warning_box(title: str, content: str)
render_success_box(title: str, content: str)
render_error_box(title: str, content: str)
render_pdf_page(filename: str, page: int = 1, height: int = 500)
```

---

## utils

### `utils.env_validator.EnvironmentValidator`

```python
validate_all() -> Tuple[bool, Dict[str, List[str]]]  # (유효여부, {errors, warnings, info})
create_env_file() -> bool                              # env.example 기반 .env 생성
get_setup_instructions() -> str                        # 설치 가이드 문자열
```

### `utils.helpers`

```python
setup_environment() -> None                                          # .env 로드 + 필수 변수 검증
extract_source_info(content: str) -> Dict[str, str]                 # 텍스트에서 출처 메타데이터 추출
format_citations(sources: List[Dict[str, str]]) -> str              # 출처 목록 포매팅
evaluate_evidence_quality(content, sources) -> Dict[str, int]       # 품질/신뢰성/최신성 점수 (1-10)
extract_preview_sources(content: str) -> List[Dict[str, str]]       # 응답에서 구조화된 출처 추출
```

---

## app (메인)

LangGraph 워크플로우 구성 및 Streamlit 앱 진입점.

### 에이전트 생성

```python
create_agent(llm, tools: list, system_prompt: str, use_react: bool = True)
```
LangChain 에이전트 생성. `use_react=True`이면 Tool-Calling ReAct 에이전트, `False`이면 단순 래퍼.

### 그래프 구성

```python
create_graph(llm, retriever) -> CompiledGraph
```
Supervisor → Researcher → Analyst → ChartProcessor 워크플로우를 구성하여 컴파일된 LangGraph를 반환.

**노드 구조:**
```
supervisor → researcher (RAG + 웹 검색 + KOSIS) → supervisor
           → analyst (분석 + chart_data 생성) → chart_processor → END
           → END
```

### 앱 실행

```python
main() -> None                    # 페이지 설정, 상태 초기화, 사이드바/채팅 렌더링
main_chat_interface() -> None     # 채팅 루프 — 입력 처리, 그래프 실행, 응답 수집
```

---

*Generated: 2026-04-03 | v2.4*

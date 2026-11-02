# AI 한국은행 경제 분석팀

> LangGraph 기반 협업형 멀티 에이전트 경제 분석 시스템 (v2.4)

## PDF 텍스트 검색 CLI

로그인된 Codex·Claude Code의 검색·분석 사용법은 [에이전트 가이드](docs/AGENT_GUIDE.md)를 참고하세요.

기존 의존성을 설치한 Python 환경에서 실행합니다.

```bash
.venv/bin/python -m bok_cli search "생산성" --data-dir data --limit 5
```

`--data-dir` 기본값은 프로젝트의 `data/`입니다. 검색은 해당 폴더의 PDF만 읽습니다.
하위 폴더와 기존 FAISS 인덱스는 읽지 않습니다. 파일과 인덱스를 변경하지 않습니다.

CLI는 API 설정이나 네트워크 없이 PDF 텍스트를 검색합니다. 공백으로 나눈 검색어 중
하나 이상을 포함하는 페이지를 찾고, 일치한 검색어 수가 많은 순서로 반환합니다.
대소문자를 구분하지 않습니다. 동점은 파일명과 페이지 순서입니다.
기존 Streamlit 화면의 API 기반 의미 검색과는 별도 방식이며 결과에 `method="text"`를 표시합니다.
동의어 검색과 스캔 문서 OCR은 지원하지 않습니다.

성공하면 stdout에 JSON 하나를 출력하고 종료 코드 0을 반환합니다.

- `status`는 `ok`, `empty_corpus`, `no_matches` 중 하나입니다.
- `results`의 각 항목은 `source`, 1부터 시작하는 `page`, 페이지 전체 `text`를 포함합니다.
- `published_at`은 `null`입니다. 파일 수정 시각을 발행일로 추정하지 않습니다.
- 문서가 없거나 일치하는 페이지가 없으면 `results`는 빈 배열입니다. 가상 문서는 만들지 않습니다.

잘못된 인자, 존재하지 않는 폴더, 읽을 수 없는 PDF는 stderr에 오류 JSON을 출력하고
종료 코드 2를 반환합니다. 이때 stdout은 비어 있습니다. PDF 하나라도 읽을 수 없으면
부분 검색 결과를 성공으로 반환하지 않습니다. `--help`는 일반 도움말을 출력합니다.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

테스트는 실제 PDF 파일과 CLI 프로세스, 외부 모델 호출을 대체한 LangGraph 실행,
Streamlit 화면의 응답 수집을 검증합니다. 실제 모델 API는 호출하지 않습니다.
`MAX_ITERATIONS`는 요청당 Supervisor 판단 횟수입니다. 시간 제한도 요청마다 새로 시작하며,
Supervisor가 다시 실행될 때 확인합니다. 진행 중인 외부 API 호출을 중단하는 제한은 아닙니다.
기존 환경에서 `APP_GRAPH_VERSION`을 지정했다면 `5`로 갱신하고 앱을 다시 실행하세요.

## 로컬 MCP·검색 서버·웹 UI

기존 앱과 분리된 Python 3.12 환경에서 저장소 루트를 기준으로 실행합니다.
기존 `.venv`와 `requirements.txt`는 변경할 필요가 없습니다.

```bash
uv venv .venv-server --python 3.12
uv pip install --python .venv-server/bin/python -r requirements-server.txt
.venv-server/bin/python -m bok_server --port 8765
```

| 경로 | 용도 |
|---|---|
| `http://127.0.0.1:8765/` | PDF 검색·본문 확인·파일명과 페이지 인용 복사 |
| `http://127.0.0.1:8765/api/search?query=생산성&limit=5` | 기존 CLI와 같은 검색 JSON |
| `http://127.0.0.1:8765/mcp` | MCP Streamable HTTP. 도구는 `search_pdf(query, limit=5)` 하나 |

기본 검색 폴더는 저장소의 `data/`입니다. 다른 폴더는 서버 시작 시 `--data-dir`로 지정합니다.
도구·API는 폴더나 파일 경로를 받지 않습니다. 검색어는 1~500자, 결과 수는 1~20개 페이지입니다.
HTTP 입력·PDF 오류는 상태 코드 400의 `invalid_input` JSON이며, MCP는 도구 오류로 반환합니다.
`empty_corpus`, `no_matches`는 성공한 요청의 빈 결과 상태입니다.

서버 실행 후 원하는 에이전트에서 등록합니다. 다음 명령은 해당 에이전트의 MCP 설정을 변경합니다.

```bash
codex mcp add bok --url http://127.0.0.1:8765/mcp
# Claude Code를 사용하는 경우
claude mcp add --transport http bok http://127.0.0.1:8765/mcp
```

HTTP 대신 에이전트가 서버를 직접 시작하는 stdio를 사용할 수도 있습니다.
아래 경로는 현재 작업 경로이므로 다른 위치에 복제했다면 바꾸세요. HTTP와 stdio 중 하나만 등록합니다.

```bash
codex mcp add bok -- /Users/sukbeom/Documents/bok-analysis/.venv-server/bin/python \
  /Users/sukbeom/Documents/bok-analysis/bok_server.py --transport stdio
```

MCP·API·웹 UI는 모델을 호출하거나 로그인 정보를 읽지 않습니다. 분석은 연결된 에이전트가 수행합니다.
서버는 `127.0.0.1`에만 열고 동일 출처의 브라우저 요청만 허용합니다. 공개 배포·업로드·DB는 제공하지 않습니다.
PDF 검색은 직렬 처리하므로 큰 폴더에서는 다른 요청도 기다릴 수 있습니다. 종료는 실행 터미널에서 Ctrl+C입니다.

선택 서버의 실제 HTTP·MCP 통합 테스트는 별도로 실행합니다. 모델 API는 호출하지 않습니다.

```bash
.venv-server/bin/python -m unittest discover -s tests_server -v
```

## 기존 Streamlit 앱

AI 에이전트 팀(Supervisor, Researcher, Analyst)이 협업하여 경제 질문에 대한 심층 분석을 제공하는 Streamlit 웹 애플리케이션입니다. 사용자가 PDF 문서를 업로드하고 자연어로 질문하면, RAG 파이프라인과 웹 검색을 결합하여 근거 기반 분석 보고서를 생성합니다.

### 설계 의도

이 시스템은 **"단일 LLM 호출로는 달성하기 어려운 복합 경제 분석"** 을 해결하기 위해 설계되었습니다.

```
기존 방식: 사용자 → LLM → 답변 (출처 불명, 환각 위험)

본 시스템: 사용자 → Supervisor(계획) → Researcher(근거 수집) → Analyst(심층 분석) → 답변
                                          ↑                        ↑
                                     RAG + 웹 + KOSIS         차트 자동 생성
                                     (출처 추적 포함)          (데이터 시각화)
```

**핵심 설계 원칙:**
1. **근거 기반 분석** : 모든 분석은 검색된 문서/데이터에 기반하며, 출처(문서명, 페이지, URL)를 명시합니다
2. **역할 분리** : 정보 수집(Researcher)과 분석(Analyst)을 분리하여 각 단계의 품질을 보장합니다
3. **동적 라우팅** : Supervisor가 질문의 성격에 따라 최적의 에이전트 경로를 판단합니다
4. **투명한 과정** : 에이전트 진행 상황을 실시간으로 표시하여 사용자 신뢰를 확보합니다

### 주요 특징

- **멀티 에이전트 협업** : Supervisor-Worker 아키텍처, 텍스트 기반 라우팅
- **고급 RAG** : FAISS + MMR/유사도 검색, 2단계 폴백, 출처(문서명/페이지) 자동 추적
- **대화 히스토리** : 이전 대화 맥락을 활용한 연속 질문 지원 (최근 6턴)
- **차트 시각화** : Analyst 응답의 수치 데이터를 plotly 차트로 자동 변환 (단일/멀티시리즈)
- **보고서 다운로드** : 분석 결과를 Markdown 보고서로 내보내기
- **사용자 피드백** : 좋아요/싫어요 위젯으로 응답 품질 수집
- **KOSIS 연동** : 국가통계포털 API로 공식 경제 통계 조회 (선택)
- **실시간 웹 검색** : DuckDuckGo 기반 최신 경제 정보 수집

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| UI | Streamlit (멀티페이지, 네이티브 컴포넌트) |
| 에이전트 오케스트레이션 | LangGraph (StateGraph) |
| LLM 프레임워크 | LangChain |
| LLM | OpenAI, Claude, OpenAI 호환 API 중 선택 |
| 임베딩 | OpenAI 또는 OpenAI 호환 API, 채팅과 별도 설정 |
| 벡터DB | FAISS (로컬 캐시) |
| PDF 처리 | PyMuPDF |
| 웹 검색 | DDGS (DuckDuckGo) |
| 차트 | plotly |
| 통계 API | KOSIS (선택) |

## 시스템 아키텍처

```mermaid
graph TD
    subgraph "사용자 인터페이스"
        INPUT["질문 입력"] --> SM["StateManager<br/>대화 히스토리 변환"]
        UPLOAD["PDF 업로드"] --> DATA["data/ 폴더"]
    end

    subgraph "LangGraph 에이전트 시스템"
        SM -->|"히스토리 + 질문"| SUP{Supervisor}
        SUP -->|"ROUTE: researcher"| RES["Researcher<br/>4개 도구"]
        SUP -->|"ROUTE: analyst"| ANA["Analyst<br/>분석 + chart_data"]
        SUP -->|"ROUTE: END"| END_NODE["종료"]
        RES --> SUP
        ANA --> CP["Chart Processor<br/>plotly 변환"]
        CP --> END_NODE
    end

    subgraph "데이터 소스"
        RES --> RAG["RAG 파이프라인<br/>FAISS + MMR"]
        RES --> WEB["웹 검색<br/>DuckDuckGo"]
        RES --> KOSIS["KOSIS API<br/>(선택)"]
        RAG --> DATA
    end

    subgraph "출력"
        END_NODE --> CITE["출처 정보<br/>문서명/페이지/URL"]
        END_NODE --> CHART["차트 렌더링"]
        END_NODE --> REPORT["보고서 다운로드"]
        END_NODE --> FB["피드백 위젯"]
    end
```

### 에이전트 역할

| 에이전트 | 역할 | 도구 |
|---------|------|------|
| **Supervisor** | 라우팅 결정, 반복/타임아웃 관리, 대화 맥락 인식 | 없음 (텍스트 출력만) |
| **Researcher** | 정보 수집, 출처 추적, 2단계 검색 전략 | `bok_document_search`, `web_search`, `relaxed_document_search`, `kosis_statistics_search` |
| **Analyst** | 심층 분석, 보고서 작성, 차트 데이터 생성 | 없음 (최종 응답 전용) |
| **Chart Processor** | Analyst 응답에서 chart_data 추출 → plotly 변환 | 자동 실행 (Analyst 후단) |

### 작동 흐름: 질문에서 답변까지

```mermaid
sequenceDiagram
    participant U as 사용자
    participant S as Supervisor
    participant R as Researcher
    participant A as Analyst
    participant C as Chart Processor

    U->>S: "기준금리 동결 영향 분석해줘"
    Note over S: 대화 히스토리 포함 (최근 6턴)
    S->>R: ROUTE: researcher

    R->>R: bok_document_search → [문서1] 통화정책보고서.pdf (p.3)
    R->>R: web_search → 최신 뉴스 3건
    R-->>S: 수집 결과 + 출처 정보

    S->>A: ROUTE: analyst

    A->>A: 심층 분석 + chart_data 생성
    A-->>C: 분석 보고서 전달
    C->>C: chart_data → plotly Figure

    C-->>U: 분석 결과 + 출처 + 차트 + 보고서 다운로드 + 피드백 위젯
```

### RAG 파이프라인

```mermaid
flowchart LR
    PDF["PDF 업로드"] --> LOAD["PyMuPDFLoader<br/>metadata 보강"]
    LOAD --> SPLIT["TextSplitter<br/>1000자/100 overlap"]
    SPLIT --> EMBED["Configured Embeddings"]
    EMBED --> FAISS["FAISS 벡터DB<br/>로컬 캐시"]
    FAISS --> MMR["MMR Retriever<br/>k=5, fetch_k=20"]
    FAISS --> RELAX["Relaxed Retriever<br/>k=10, threshold=0.3"]
    MMR --> CITE["Citation Wrapper<br/>[문서 N] file.pdf (p.X)"]
    RELAX --> CITE
```

## 프로젝트 구조

```
├── app.py                          # 메인 앱 + 에이전트 + 그래프 정의
├── core/                           # 핵심 비즈니스 로직
│   ├── config.py                   # 환경변수 및 설정 (Config 클래스)
│   ├── logger.py                   # 구조화된 로깅
│   ├── model_factory.py            # 채팅·임베딩 모델 팩토리
│   ├── rag_pipeline.py             # RAG: PDF → FAISS → Retriever
│   ├── state_manager.py            # Streamlit 세션 상태 중앙 관리
│   ├── web_search.py               # DuckDuckGo 웹 검색 + 재시도
│   ├── citation.py                 # Retriever → 출처 포함 텍스트 변환
│   ├── feedback.py                 # 피드백 JSONL 저장/통계
│   ├── chart_generator.py          # LLM 응답 → plotly 차트 (단일/멀티시리즈)
│   ├── report_generator.py         # 분석 결과 → Markdown 보고서
│   └── kosis_client.py             # KOSIS 통계청 API 클라이언트
├── components/                     # UI 컴포넌트
│   ├── sidebar.py                  # 사이드바 (컨트롤/업로드/참고자료/PDF뷰어)
│   ├── chat_interface.py           # 채팅 메시지 + 출처 렌더링
│   └── common.py                   # 공통 컴포넌트 + PDF 페이지 뷰어
├── utils/                          # 유틸리티
│   ├── helpers.py                  # 출처 추출/포맷/평가
│   └── env_validator.py            # 환경 변수 검증
├── pages/                          # Streamlit 멀티페이지
│   ├── 01_⚙️_설정.py              # 설정 + 환경검증 + 피드백통계
│   └── 02_📖_도움말.py            # 사용 가이드 + FAQ
├── data/                           # PDF 문서 + FAISS 캐시 + 피드백 기록
├── docs/
│   ├── ARCHITECTURE.md             # 상세 아키텍처 문서 (Mermaid 12개)
│   └── plans/                      # 구현 계획 문서
├── requirements.txt                # Python 의존성
└── env.example                     # 환경 변수 템플릿
```

## 설치 및 실행

### 사전 준비

- 채팅과 임베딩에 사용할 모델 이름과 API 키
- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (권장) 또는 pip

### 설정

```bash
git clone https://github.com/SukbeomH/bok-economic-analyst.git
cd bok-economic-analyst

# 가상환경 생성 및 의존성 설치
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 환경 변수 설정
cp env.example .env
# .env 파일에 채팅과 임베딩 제공자·모델·키를 각각 입력
```

### 실행

```bash
streamlit run app.py
# 또는
uv run streamlit run app.py
```

## 환경 변수

```env
# === 채팅 ===
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=
LLM_BASE_URL=

# === 임베딩, 채팅과 별도 설정 ===
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=

# === 앱 설정 (선택) ===
MAX_ITERATIONS=10              # 에이전트 최대 반복 (기본: 10)
TIMEOUT_SECONDS=300            # 실행 타임아웃 초 (기본: 300)
MAX_HISTORY_TURNS=6            # 대화 히스토리 턴 수 (기본: 6)
LOG_LEVEL=INFO                 # 로그 레벨 (기본: INFO)

# === RAG 설정 (선택) ===
RAG_SEARCH_STRATEGY=mmr        # 검색 전략: mmr 또는 similarity (기본: mmr)
RAG_K=5                        # 검색 결과 수 (기본: 5)
RAG_FETCH_K=20                 # MMR 후보 수 (기본: 20)
RAG_LAMBDA_MULT=0.7            # MMR 다양성 계수 (기본: 0.7)
RAG_SCORE_THRESHOLD=0.7        # 유사도 임계값 (기본: 0.7)
RAG_USE_COMPRESSION=false      # 컨텍스트 압축 (기본: false)

# === 외부 연동 (선택) ===
KOSIS_API_KEY=                 # KOSIS 통계청 API 키 (https://kosis.kr/openapi/)
```

채팅 제공자는 다음 값 중 하나를 지정합니다. 모델 이름과 키는 선택한 서비스에서 직접 설정합니다.

| 제공자 | `LLM_PROVIDER` | `LLM_MODEL` | `LLM_BASE_URL` |
|---|---|---|---|
| OpenAI | `openai` | 사용할 OpenAI 모델 이름 | 비워두면 공식 주소 |
| Claude | `claude` | 사용할 Claude 모델 이름 | 비워두면 공식 주소 |
| OpenAI 호환 API | `openai_compatible` | 서버가 제공하는 모델 이름 | API 루트 주소, 예를 들어 `http://localhost:8000/v1` |

임베딩 제공자는 `openai` 또는 `openai_compatible`을 지정합니다. Claude는 자체 임베딩을 제공하지 않습니다.
`EMBEDDING_MODEL`, `EMBEDDING_API_KEY`를 채팅과 별도로 설정하고, 호환 API라면
`EMBEDDING_BASE_URL`도 지정합니다. 같은 키를 사용하려면 두 키 항목에 각각 직접 지정합니다.
호환 서버는 채팅의 도구 호출과 임베딩 API 중 실제 사용하는 기능을 지원해야 합니다.
설정을 바꾸면 앱을 다시 실행하세요. 임베딩 제공자·모델·주소가 바뀌거나 이전 형식의 인덱스가 있으면
FAISS 인덱스를 다시 만듭니다. API 키는 캐시 식별값에 포함하거나 파일에 저장하지 않습니다.

로그인된 Codex·Claude Code는 기존 BOK CLI를 외부에서 호출합니다.
앱이 CLI 로그인 정보나 토큰을 읽어 API 키로 사용하지 않습니다.

## 사용 방법

### 기본 분석 흐름

1. (선택) 사이드바에서 PDF 문서 업로드
2. 채팅창에 경제 질문 입력 (예: "기준금리 동결이 경제에 미치는 영향은?")
3. 에이전트 협업 과정 실시간 확인 (Supervisor → Researcher → Analyst)
4. 분석 결과 확인: 본문 + 출처 정보 + 차트 (해당 시)
5. 보고서 다운로드 또는 피드백 제출

### 연속 분석

이전 대화를 참조하여 연속 질문이 가능합니다:
- "아까 분석에서 이어서, 금리가 경제에 미치는 영향은?"
- "위에서 언급한 GDP 수치를 좀 더 자세히 분석해줘"

### 차트 시각화

Analyst가 수치 데이터를 포함한 분석을 생성하면 자동으로 plotly 차트가 렌더링됩니다. 단일 지표 및 여러 지표 비교(멀티시리즈) 모두 지원합니다.

### PDF 출처 딥링크

출처 정보에서 **[📖 보기]** 버튼을 클릭하면 해당 PDF의 해당 페이지를 바로 열람할 수 있습니다.

### 멀티페이지

| 페이지 | 내용 |
|--------|------|
| 메인 | 채팅 인터페이스, 분석 실행, 결과 표시 |
| ⚙️ 설정 | 환경 검증, RAG/앱 설정 확인, 피드백 통계 |
| 📖 도움말 | 사용 가이드, 에이전트 역할 설명, FAQ |

## 개발 및 디버깅

### 로그 접두사

| 접두사 | 영역 |
|--------|------|
| `[env]` | 환경 설정 |
| `[model]` | 선택한 채팅·임베딩 모델 |
| `[rag]` | RAG 파이프라인 |
| `[supervisor]` | Supervisor 라우팅 |
| `[agent-node:<name>]` | 에이전트 실행 |
| `[chart]` | 차트 생성 |
| `[feedback]` | 피드백 저장 |
| `[report]` | 보고서 생성 |
| `[kosis]` | KOSIS API |
| `[run]` | 스트림 실행 흐름 |
| `[state]` | 세션 상태 변경 |

### 트러블슈팅

| 문제 | 해결 |
|------|------|
| 모델 API 연결 실패 | 제공자·모델 이름·API 키·호환 API 주소 확인 |
| SSL 인증서 검증 실패 | DDGS `verify=False`로 자동 해결됨 |
| 최종 응답이 비어있음 | 2단계 검색 + 폴백 로직으로 자동 처리됨 |
| RAG 반복 빌드 | 사이드바 "🔄 그래프 재구성" 클릭 |
| 로그 상세 확인 | `.env`에서 `LOG_LEVEL=DEBUG` 설정 |

## 변경 이력

### v2.4 (최신) - Phase 3
- 대화 히스토리 연속 분석 (최근 6턴, Supervisor 맥락 인식)
- 멀티시리즈 차트 (series 배열로 여러 지표 비교)
- PDF 출처 딥링크 (페이지 번호 클릭 → PDF 뷰어)
- 분석 보고서 Markdown 다운로드

### v2.3 - Phase 2
- 답변 출처 명시 (문서명/페이지/URL 구조화)
- 사용자 피드백 (좋아요/싫어요 + 통계 대시보드)
- plotly 차트 자동 생성
- KOSIS 국가통계포털 연동

### v2.2 - UI/UX
- Streamlit 네이티브 컴포넌트 전환 (CSS 제거)
- 사이드바/헤더/참고자료 UI 개선
- 미사용 코드 정리

### v2.1 - 안정성
- SSL 인증서 오류 해결
- 2단계 검색 전략 (기본 → 완화된 검색)
- 메시지 타입 처리 개선

### v2.0 - 구조화
- 모듈화 (단일 파일 → core/components/utils 분리)
- StateManager 중앙화, 환경 변수 검증
- Streamlit 멀티페이지 구조

### v1.0 - 초기
- Supervisor 텍스트 라우팅, RAG 캐시, 기본 UI

## 상세 문서

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** : 데이터 워크플로우, 시나리오별 시퀀스 다이어그램, 모듈 의존성 (Mermaid 12개)
- **[PRD.txt](PRD.txt)** : 제품 요구사항 정의서

---

**AI 한국은행 경제 분석팀** - LangGraph 기반 협업형 멀티 에이전트 시스템

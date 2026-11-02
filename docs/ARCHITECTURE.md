# AI 한국은행 경제 분석팀 - 시스템 아키텍처 문서

> v2.4 기준 | 2026-04-02 작성

---

## 1. 시스템 전체 구조

```mermaid
graph TB
    subgraph "사용자 인터페이스 (Streamlit)"
        UI_INPUT["채팅 입력<br/>st.chat_input"]
        UI_SIDEBAR["사이드바<br/>PDF 업로드 / 설정"]
        UI_CHAT["채팅 영역<br/>메시지 / 출처 / 차트"]
        UI_REPORT["보고서 다운로드<br/>st.download_button"]
        UI_FEEDBACK["피드백 위젯<br/>st.feedback"]
    end

    subgraph "상태 관리"
        SM["StateManager<br/>core/state_manager.py"]
    end

    subgraph "AI 에이전트 시스템 (LangGraph)"
        SUP["Supervisor<br/>라우팅 결정"]
        RES["Researcher<br/>정보 수집"]
        ANA["Analyst<br/>심층 분석"]
        CP["Chart Processor<br/>차트 생성"]
    end

    subgraph "데이터 소스"
        RAG["RAG 파이프라인<br/>FAISS + PyMuPDF"]
        WEB["웹 검색<br/>DuckDuckGo"]
        KOSIS["KOSIS API<br/>국가통계포털"]
        PDF["PDF 문서<br/>data/*.pdf"]
    end

    subgraph "출력 모듈"
        CIT["출처 추적<br/>core/citation.py"]
        CHT["차트 생성<br/>core/chart_generator.py"]
        RPT["보고서 생성<br/>core/report_generator.py"]
        FBK["피드백 저장<br/>core/feedback.py"]
    end

    UI_INPUT --> SM
    UI_SIDEBAR --> PDF
    SM --> SUP
    SUP -->|"ROUTE: researcher"| RES
    SUP -->|"ROUTE: analyst"| ANA
    RES --> SUP
    ANA --> CP
    CP --> UI_CHAT

    RES --> RAG
    RES --> WEB
    RES --> KOSIS
    RAG --> PDF
    RAG --> CIT

    CP --> CHT
    UI_CHAT --> RPT
    UI_CHAT --> UI_REPORT
    UI_FEEDBACK --> FBK
```

---

## 2. LangGraph 에이전트 워크플로우

```mermaid
stateDiagram-v2
    [*] --> Supervisor: 사용자 질문 + 대화 히스토리

    Supervisor --> Researcher: ROUTE: researcher
    Supervisor --> Analyst: ROUTE: analyst
    Supervisor --> [*]: ROUTE: END

    Researcher --> Supervisor: 수집 결과 반환

    Analyst --> ChartProcessor: 분석 결과 전달
    ChartProcessor --> [*]: 차트 추출 후 종료

    note right of Supervisor
        텍스트 기반 라우팅
        최대 10회 반복
        300초 타임아웃
        대화 맥락 인식
    end note

    note right of Researcher
        도구 4개:
        - bok_document_search (RAG)
        - web_search (DDGS)
        - relaxed_document_search (폴백)
        - kosis_statistics_search (선택)
    end note

    note right of Analyst
        도구 없음 (최종 응답 전용)
        chart_data 블록 출력 가능
        단일/멀티시리즈 차트 지원
    end note
```

---

## 3. 데이터 워크플로우

### 3.1 사용자 질문 처리 흐름

```mermaid
sequenceDiagram
    participant U as 사용자
    participant UI as Streamlit UI
    participant SM as StateManager
    participant G as LangGraph
    participant S as Supervisor
    participant R as Researcher
    participant A as Analyst
    participant CP as Chart Processor

    U->>UI: 질문 입력
    UI->>SM: add_message("user", prompt)

    Note over SM: 대화 히스토리 변환<br/>HumanMessage / AIMessage<br/>최근 6턴 제한

    SM->>G: stream({messages: all_messages})
    G->>S: 초기 라우팅 요청

    S->>S: LLM 판단
    S-->>G: "ROUTE: researcher"
    G->>R: 정보 수집 요청

    R->>R: bok_document_search()
    R->>R: web_search()
    R-->>G: 수집 결과

    G->>S: 재라우팅 판단
    S-->>G: "ROUTE: analyst"
    G->>A: 분석 요청

    A->>A: 심층 분석 + chart_data 생성
    A-->>G: 분석 보고서

    G->>CP: chart_data 추출
    CP->>CP: plotly Figure 생성
    CP-->>G: pending_charts에 저장

    G-->>UI: 최종 응답 스트리밍

    UI->>UI: 출처 정보 렌더링
    UI->>UI: 차트 렌더링
    UI->>UI: 보고서 다운로드 버튼
    UI->>U: 피드백 위젯 표시

    U->>UI: 👍 피드백
    UI->>SM: save_feedback() → JSONL
```

### 3.2 RAG 파이프라인 흐름

```mermaid
flowchart LR
    subgraph "입력"
        PDF["📄 PDF 파일<br/>data/*.pdf"]
    end

    subgraph "문서 처리"
        LOAD["PyMuPDFLoader<br/>PDF → Document[]"]
        META["metadata 보강<br/>source_filename<br/>page_number"]
        SPLIT["RecursiveCharacterTextSplitter<br/>chunk_size=1000<br/>overlap=100"]
    end

    subgraph "벡터화"
        EMBED["설정된 임베딩 API<br/>text-embedding-3-large"]
        FAISS["FAISS VectorStore<br/>로컬 캐시 저장"]
    end

    subgraph "검색"
        MMR["MMR Retriever<br/>k=5, fetch_k=20<br/>lambda=0.7"]
        RELAX["Relaxed Retriever<br/>k=10, threshold=0.3"]
        CITE["Citation Wrapper<br/>[문서 N] file (p.X)"]
    end

    subgraph "캐시 관리"
        INV["invalidation.txt<br/>PDF mtime 추적"]
        CACHE{캐시 유효?}
    end

    PDF --> LOAD --> META --> SPLIT --> EMBED --> FAISS
    FAISS --> CACHE
    CACHE -->|Yes| MMR
    CACHE -->|No| LOAD
    FAISS --> MMR
    FAISS --> RELAX
    MMR --> CITE
    RELAX --> CITE
    CITE --> |"Tool: bok_document_search"| RES["Researcher 에이전트"]
    INV -.-> CACHE
```

### 3.3 PDF 업로드 → RAG 업데이트 흐름

```mermaid
flowchart TD
    UPLOAD["사용자 PDF 업로드<br/>sidebar.py:83"]
    SAVE["파일 저장<br/>data/*.pdf"]
    CLEAR["캐시 초기화<br/>st.cache_resource.clear()"]
    RERUN["앱 재실행<br/>st.rerun()"]
    INIT["그래프 재초기화<br/>is_agent_graph_valid() = False"]
    RAG["RAG 파이프라인 재구축<br/>build_rag_pipeline()"]
    READY["분석 준비 완료"]

    UPLOAD --> SAVE --> CLEAR --> RERUN --> INIT --> RAG --> READY
```

---

## 4. 모듈 의존성 구조

```mermaid
graph TD
    subgraph "진입점"
        APP["app.py<br/>메인 앱 + 에이전트 정의"]
    end

    subgraph "core/ — 핵심 비즈니스 로직"
        CFG["config.py<br/>환경변수 / 설정"]
        LOG["logger.py<br/>로깅 시스템"]
        MF["model_factory.py<br/>모델 API 팩토리"]
        RAG["rag_pipeline.py<br/>RAG 파이프라인"]
        WS["web_search.py<br/>DuckDuckGo 검색"]
        SM["state_manager.py<br/>세션 상태 관리"]
        CIT["citation.py<br/>출처 추적"]
        FB["feedback.py<br/>피드백 저장"]
        CG["chart_generator.py<br/>차트 생성"]
        RG["report_generator.py<br/>보고서 생성"]
        KO["kosis_client.py<br/>KOSIS API"]
    end

    subgraph "components/ — UI 컴포넌트"
        SB["sidebar.py<br/>사이드바"]
        CI["chat_interface.py<br/>채팅 UI"]
        CM["common.py<br/>공통 컴포넌트"]
    end

    subgraph "utils/ — 유틸리티"
        HP["helpers.py<br/>출처 추출 / 포맷"]
        EV["env_validator.py<br/>환경 검증"]
    end

    subgraph "pages/ — 멀티페이지"
        P1["01_설정.py"]
        P2["02_도움말.py"]
    end

    APP --> CFG & LOG & MF & RAG & WS & SM & CIT
    APP --> SB & CI
    APP --> CG & FB & RG & KO

    RAG --> CFG & LOG & MF
    WS --> LOG & SM
    CIT --> LOG
    FB --> CFG & LOG
    CG --> LOG
    RG --> LOG
    KO --> CFG & LOG

    SB --> CFG & LOG & SM
    CI --> SM & HP & CM
    CM --> CFG

    P1 --> CFG & SM & EV & FB
    P2 -.-> |독립| P2

    MF --> CFG & LOG

    style APP fill:#e1f5fe
    style SM fill:#fff3e0
    style RAG fill:#e8f5e9
```

---

## 5. 작동 시나리오

### 시나리오 1: 첫 번째 질문 (그래프 초기화 포함)

```mermaid
flowchart TD
    START["앱 실행<br/>streamlit run app.py"]
    INIT["세션 상태 초기화<br/>StateManager.initialize_session_state()"]
    CHECK{"에이전트 그래프<br/>유효?"}
    BUILD["그래프 구축<br/>LLM + RAG + LangGraph 컴파일"]
    READY["분석 준비 완료"]
    Q1["사용자: '기준금리 추이는?'"]
    HIST["히스토리 변환<br/>이전 대화 없음 → []"]
    STREAM["graph.stream({messages: [HumanMessage]})"]
    SUP1["Supervisor → ROUTE: researcher"]
    RES1["Researcher: RAG 검색 + 웹 검색"]
    SUP2["Supervisor → ROUTE: analyst"]
    ANA1["Analyst: 심층 분석 + chart_data"]
    CHART["Chart Processor: plotly 차트 생성"]
    RENDER["응답 렌더링<br/>출처 + 차트 + 보고서 버튼"]

    START --> INIT --> CHECK
    CHECK -->|No| BUILD --> READY
    CHECK -->|Yes| READY
    READY --> Q1 --> HIST --> STREAM
    STREAM --> SUP1 --> RES1 --> SUP2 --> ANA1 --> CHART --> RENDER
```

### 시나리오 2: 연속 질문 (대화 맥락 활용)

```mermaid
flowchart TD
    PREV["이전 대화:<br/>'기준금리 추이는?' → (분석 결과)"]
    Q2["사용자: '아까 분석에서 이어서,<br/>금리가 경제에 미치는 영향은?'"]
    HIST["히스토리 변환<br/>[HumanMessage(Q1), AIMessage(A1)]"]
    MERGE["all_messages =<br/>히스토리 + [HumanMessage(Q2)]"]
    STREAM["graph.stream({messages: all_messages})"]
    SUP["Supervisor: 이전 맥락 인식<br/>'아까' → 대화 히스토리 참조"]
    RES["Researcher: 추가 정보 수집"]
    ANA["Analyst: 이전 분석 기반 확장"]

    PREV --> Q2 --> HIST --> MERGE --> STREAM --> SUP --> RES --> ANA
```

### 시나리오 3: PDF 업로드 후 분석

```mermaid
flowchart TD
    UPLOAD["사이드바: PDF 업로드<br/>'통화정책보고서.pdf'"]
    SAVE["data/ 폴더에 저장"]
    REBUILD["RAG 파이프라인 재구축<br/>새 PDF 포함"]
    Q["사용자: '업로드한 보고서를 바탕으로<br/>금리 동결 영향을 분석해줘'"]
    RES["Researcher:<br/>bok_document_search() →<br/>[문서 1] 통화정책보고서.pdf (p.3)<br/>기준금리 3.50% 동결 결정..."]
    ANA["Analyst: 문서 기반 심층 분석"]
    CITE["출처 표시:<br/>📄 통화정책보고서.pdf p.3<br/>[📖 보기] 버튼"]

    UPLOAD --> SAVE --> REBUILD --> Q --> RES --> ANA --> CITE
```

### 시나리오 4: 차트 포함 분석 응답

```mermaid
flowchart TD
    Q["사용자: 'GDP 성장률과<br/>물가상승률을 비교해줘'"]
    RES["Researcher: KOSIS + 웹 검색"]
    ANA["Analyst 응답:<br/>분석 텍스트 +<br/>```chart_data<br/>{series: [GDP, CPI]}```"]
    EXTRACT["extract_chart_data():<br/>JSON 파싱"]
    CREATE["create_chart():<br/>멀티시리즈 plotly Figure"]
    RENDER["st.plotly_chart():<br/>인터랙티브 차트 표시"]
    REPORT["보고서에 차트 제목 포함"]

    Q --> RES --> ANA --> EXTRACT --> CREATE --> RENDER
    ANA --> REPORT
```

---

## 6. 세션 상태 관리

```mermaid
graph LR
    subgraph "StateManager 키"
        MSG["messages<br/>List[Dict]<br/>대화 히스토리"]
        GRAPH["agent_graph<br/>CompiledGraph<br/>LangGraph 인스턴스"]
        VER["agent_graph_version<br/>str<br/>캐시 검증"]
        WEB["web_search_enabled<br/>bool<br/>웹검색 토글"]
        LOG["show_logs<br/>bool<br/>로그 표시"]
        UP["uploader_key<br/>int<br/>업로더 리프레시"]
        FB["feedback_index<br/>int<br/>피드백 위젯 키"]
    end

    subgraph "외부 상태"
        CHART["pending_charts<br/>List[Figure]<br/>렌더링 대기 차트"]
        JSONL["data/feedback.jsonl<br/>피드백 영구 저장"]
        FAISS["data/faiss_index/<br/>FAISS 벡터 캐시"]
    end

    MSG -->|"stream() 입력"| GRAPH
    GRAPH -->|"검증"| VER
    WEB -->|"토글"| RES["Researcher"]
    FB -->|"위젯 키"| JSONL
    CHART -->|"st.plotly_chart"| UI["UI 렌더링"]
    FAISS -->|"캐시 히트"| RAG["RAG 검색"]
```

---

## 7. 파일 구조

```
Wiki-multiagents/
├── app.py                          # 메인 앱 + 에이전트 + 그래프 정의
│
├── core/                           # 핵심 비즈니스 로직
│   ├── __init__.py                 # 모듈 export
│   ├── config.py                   # 환경변수 및 설정 (Config 클래스)
│   ├── logger.py                   # 구조화된 로깅
│   ├── model_factory.py            # 채팅·임베딩 모델 팩토리
│   ├── rag_pipeline.py             # RAG: PDF → FAISS → Retriever
│   ├── state_manager.py            # Streamlit 세션 상태 중앙 관리
│   ├── web_search.py               # DuckDuckGo 웹 검색 + 재시도
│   ├── citation.py                 # Retriever → 출처 포함 텍스트 변환
│   ├── feedback.py                 # 피드백 JSONL 저장/통계
│   ├── chart_generator.py          # LLM 응답 → plotly 차트 변환
│   ├── report_generator.py         # 분석 결과 → Markdown 보고서
│   └── kosis_client.py             # KOSIS 통계청 API 클라이언트
│
├── components/                     # UI 컴포넌트
│   ├── __init__.py
│   ├── sidebar.py                  # 사이드바 (컨트롤/업로드/참고자료)
│   ├── chat_interface.py           # 채팅 메시지 + 출처 렌더링
│   └── common.py                   # 공통 컴포넌트 + PDF 뷰어
│
├── utils/                          # 유틸리티
│   ├── __init__.py
│   ├── helpers.py                  # 출처 추출/포맷/평가
│   └── env_validator.py            # 환경 변수 검증
│
├── pages/                          # Streamlit 멀티페이지
│   ├── 01_⚙️_설정.py              # 설정 + 환경검증 + 피드백통계
│   └── 02_📖_도움말.py            # 사용 가이드 + FAQ
│
├── data/                           # 데이터 저장소
│   ├── *.pdf                       # 업로드된 PDF 문서
│   ├── faiss_index/                # FAISS 벡터 인덱스 캐시
│   └── feedback.jsonl              # 사용자 피드백 기록
│
├── .streamlit/config.toml          # Streamlit 테마/서버 설정
├── requirements.txt                # Python 의존성 (91개 패키지)
├── env.example                     # 환경 변수 템플릿
└── docs/
    ├── ARCHITECTURE.md             # ← 이 문서
    └── plans/                      # 구현 계획 문서
```

---

## 8. 기술 스택 요약

| 레이어 | 기술 | 용도 |
|--------|------|------|
| **UI** | Streamlit | 웹 인터페이스, 멀티페이지 |
| **에이전트 오케스트레이션** | LangGraph (StateGraph) | Supervisor-Worker 패턴 |
| **LLM 프레임워크** | LangChain | 에이전트, 프롬프트, 도구 |
| **LLM** | 설정된 채팅 모델 | 추론 엔진 |
| **임베딩** | OpenAI 또는 OpenAI 호환 임베딩 | 문서 벡터화 |
| **벡터DB** | FAISS (로컬) | 유사도 검색 |
| **PDF 처리** | PyMuPDF | PDF → 텍스트 + metadata |
| **웹 검색** | DDGS (DuckDuckGo) | 실시간 정보 수집 |
| **차트** | plotly | 인터랙티브 시각화 |
| **통계 API** | KOSIS | 공공 경제 데이터 |
| **상태 관리** | Streamlit Session State | 대화/그래프/설정 |
| **피드백 저장** | JSONL | 경량 파일 기반 |

---

## 9. 설정 파라미터 참조

| 카테고리 | 변수 | 기본값 | 설명 |
|---------|------|--------|------|
| **채팅** | `LLM_PROVIDER` | openai | openai, claude, openai_compatible |
| | `LLM_MODEL`, `LLM_API_KEY` | 직접 설정 | 모델 이름과 API 키 |
| | `LLM_BASE_URL` | 공식 주소 | 호환 API는 필수 |
| **임베딩** | `EMBEDDING_PROVIDER` | openai | openai, openai_compatible |
| | `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` | 직접 설정 | 채팅과 별도 설정 |
| | `EMBEDDING_BASE_URL` | 공식 주소 | 호환 API는 필수 |
| **앱** | `MAX_ITERATIONS` | 10 | 에이전트 최대 반복 |
| | `TIMEOUT_SECONDS` | 300 | 실행 타임아웃 |
| | `MAX_HISTORY_TURNS` | 6 | 대화 히스토리 턴 수 |
| **RAG** | `RAG_SEARCH_STRATEGY` | mmr | 검색 전략 (mmr/similarity) |
| | `RAG_K` | 5 | 검색 결과 수 |
| | `RAG_FETCH_K` | 20 | MMR 후보 수 |
| | `RAG_LAMBDA_MULT` | 0.7 | MMR 다양성 계수 |
| | `RAG_SCORE_THRESHOLD` | 0.7 | 유사도 임계값 |
| | `RAG_USE_COMPRESSION` | false | 컨텍스트 압축 |
| **외부** | `KOSIS_API_KEY` | — | KOSIS API 키 (선택) |
| **디버그** | `DEBUG_MODE` | false | 디버그 모드 |
| | `LOG_LEVEL` | INFO | 로그 레벨 |

# SPEC.md — Project Specification

> **Status**: `FINALIZED`
>
> **Version**: v2.4 기반, CLI·제공자 전환 반영 (2026-11-02)

## Vision

PDF 근거를 검색하고 출처를 인용하는 경제 분석 도구입니다. 기존 Streamlit 앱은
LangGraph의 Supervisor·Researcher·Analyst로 분석합니다. 외부 에이전트는 BOK CLI로
로컬 PDF를 검색하고 로그인된 세션에서 분석합니다.

## Goals

1. 문서명·PDF 페이지·URL을 제공하여 분석 근거를 확인할 수 있게 합니다.
2. 기존 앱에서 정보 수집과 분석의 역할을 분리합니다.
3. PDF RAG와 웹 검색을 연결하고, 선택적으로 KOSIS 통계 목록을 조회합니다.
4. 외부 에이전트가 별도 모델 API 키 없이 로컬 PDF 근거를 사용할 수 있게 합니다.

## Non-Goals and Deferred Scope

- 실시간 주가·환율 스트리밍, 사용자 인증·권한 관리, 다국어·모바일 앱은 범위 밖입니다.
- 별도 벡터 DB 서버를 운영하지 않습니다. 기존 앱은 로컬 FAISS 캐시를 사용합니다.
- MCP, 새 서버·새 UI, 다른 레포의 기능 통합·중복 정리는 보류합니다.
- CLI의 OCR·의미 검색 확장은 현재 합의 범위에 포함하지 않습니다.

## Execution Paths and Configuration

| 경로 | 검색·분석 방식 | 설정 |
|---|---|---|
| 기존 Streamlit 앱 | FAISS 의미 검색, 내부 LangGraph 분석팀 | 채팅·임베딩 API 설정 필요 |
| 외부 Codex·Claude Code | BOK CLI 텍스트 검색, 로그인된 에이전트가 분석 | BOK 모델 API 설정 불필요 |

기존 앱의 제공자 설정은 다음과 같습니다. 모델 이름과 키는 사용자가 직접 지정합니다.

| 항목 | 환경변수 | 허용값·조건 |
|---|---|---|
| 채팅 제공자 | `LLM_PROVIDER` | `openai`, `claude`, `openai_compatible`. 기본 `openai` |
| 채팅 모델·키 | `LLM_MODEL`, `LLM_API_KEY` | 필수 |
| 채팅 API 주소 | `LLM_BASE_URL` | 호환 API는 필수. 그 외 비우면 제공자의 공식 주소 |
| 임베딩 제공자 | `EMBEDDING_PROVIDER` | `openai`, `openai_compatible`. 기본 `openai` |
| 임베딩 모델·키 | `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` | 채팅과 별도로 필수 |
| 임베딩 API 주소 | `EMBEDDING_BASE_URL` | 호환 API는 필수. 그 외 비우면 OpenAI 공식 주소 |

Claude는 이 앱의 임베딩 제공자로 지원하지 않습니다. 호환 서버는 사용하는 도구 호출·임베딩
기능을 지원해야 합니다. 임베딩 제공자·모델·주소가 바뀌면 캐시를 무효화합니다.
BOK는 Codex·Claude Code의 로그인 토큰을 API 키로 읽거나 전환하지 않습니다.

## Runtime Constraints

- 기존 명세의 런타임 기준은 Python 3.9+입니다. 최소 버전별 호환성은 이번 작업에서 검증하지 않았습니다.
- 앱은 최근 `MAX_HISTORY_TURNS`턴의 대화를 유지합니다. 기본값은 6입니다.
- `MAX_ITERATIONS`는 요청별 Supervisor 판단 횟수이며 기본값은 10입니다.
- `TIMEOUT_SECONDS`는 요청마다 시작하고 Supervisor 재실행 시 확인합니다. 진행 중인 외부 호출을 중단하는 제한은 아닙니다.
- DuckDuckGo는 API 키 없이, KOSIS 목록 조회는 `KOSIS_API_KEY`가 있을 때 사용합니다.

## Implemented Features

아래 완료 표시는 코드 구현을 뜻합니다. 실환경 검증 여부는 다음 절에서 별도로 구분합니다.

| 단계 | 구현 완료 항목 |
|---|---|
| Phase 1 | Supervisor·Researcher·Analyst, PDF 업로드·FAISS RAG, Streamlit 채팅·진행 표시, 웹 검색 |
| Phase 2 | 문서명·페이지·URL 출처 표시, 피드백 위젯·JSONL 저장·통계, KOSIS 목록 조회, 차트 처리 노드 |
| Phase 3 | 대화 히스토리 전달, 멀티시리즈 차트, PDF 페이지 뷰어, Markdown 보고서 다운로드 |
| 실행 안정화 | 분석 근거 전달, 요청별 실행 한도, 최종 응답 표시, 문서가 없을 때 가상 PDF 생성 제거 |
| 제공자 전환 | OpenAI·Claude·호환 API 채팅, 독립적인 임베딩 설정·캐시 식별 |
| 외부 에이전트 사용 | 로컬 PDF 검색 JSON CLI 및 로그인된 에이전트용 가이드 |

차트는 Analyst의 `chart_data`를 Plotly로 변환하는 처리 노드입니다. 별도 LLM 에이전트가 아닙니다.
KOSIS는 목록의 제목·기관·기간을 반환하며 수치 시계열 수집은 구현하지 않았습니다.

### PDF CLI Contract

- `python -m bok_cli search "검색어" --limit 5`로 실행합니다. `analyze` 명령은 없습니다.
- API·네트워크·FAISS 없이 지정 폴더 바로 아래 PDF의 텍스트를 검색합니다. 기본 폴더는 저장소 `data/`입니다.
- 공백으로 나눈 검색어 중 하나 이상을 부분 문자열로 포함하는 페이지를 반환합니다.
- stdout JSON의 `results`는 파일명 `source`, 물리적 1-based `page`, 전체 페이지 `text`를 포함합니다. `published_at`은 `null`입니다.
- 종료 코드 0에서도 `status`가 `ok`, `empty_corpus`, `no_matches`인지 확인해야 합니다.
- 입력·폴더·PDF 읽기 오류는 종료 코드 2와 stderr JSON으로 반환합니다. 부분 결과는 반환하지 않습니다.

## Verification Status

2026-11-02 기준입니다. API 키나 인증정보를 읽지 않고 검증했습니다.

| 구분 | 확인 범위 |
|---|---|
| 검증 완료 | 네트워크 차단·모델 대체 상태에서 기존 테스트 30개 통과. PDF CLI, 근거 전달·실행 한도·최종 응답, 제공자 요청 형식·임베딩 캐시 검증 |
| 실제 사용 확인 | 로그인된 Codex에서 로컬 CLI로 서비스 산업 생산성 PDF를 검색하고 파일명·PDF 페이지를 인용한 분석 수행 |
| 문서 검증 완료 | 가이드의 셸 예시 구문·링크와 설치된 Codex·Claude Code의 옵션 확인 |
| 미검증 | 실제 제공자·임베딩 API의 응답 및 품질, DuckDuckGo·KOSIS 실연동, 전체 Streamlit 사용자 흐름, Claude Code 로그인 기반 추론 |
| 미구현 | KOSIS 수치 시계열 수집·분석 연결 |
| 보류 | MCP, 새 서버·새 UI, 다른 레포 통합·정리 |

Streamlit의 PDF 업로드부터 실제 모델 분석·차트·뷰어·다운로드·피드백 저장까지의 전체 흐름은
실환경 검증 완료로 표시하지 않습니다. 테스트 통과가 분석 품질이나 모든 제공자의 호환성을 보장하지는 않습니다.

## References

- [진행 상태](STATE.md)
- [제품 로드맵](../PRD.txt#development-roadmap)
- [외부 에이전트 가이드](../docs/AGENT_GUIDE.md)
- [설정 및 실행](../README.md#환경-변수)

*Last updated: 2026-11-02*

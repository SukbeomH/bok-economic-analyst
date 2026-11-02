# SPEC.md — Project Specification

> **Status**: `FINALIZED`
>
> **Version**: v2.4 (2026-04-03)

## Vision

LangGraph 기반 멀티 에이전트(Supervisor-Researcher-Analyst) 협업 시스템으로, 사용자가 업로드한 PDF와 웹/통계 데이터를 결합하여 근거 기반 경제 분석 보고서를 생성하는 Streamlit 웹 애플리케이션.

## Goals

1. **근거 기반 분석** — 모든 분석 결과에 출처(문서명, 페이지, URL)를 명시하여 환각을 최소화
2. **역할 분리 협업** — 정보 수집(Researcher)과 심층 분석(Analyst)을 분리하여 각 단계 품질 보장
3. **동적 데이터 통합** — 사용자 PDF, 웹 검색, KOSIS 통계를 실시간으로 결합하는 유연한 데이터 파이프라인
4. **투명한 분석 과정** — 에이전트 진행 상황을 실시간 표시하여 사용자 신뢰 확보

## Non-Goals (Out of Scope)

- 실시간 주가/환율 스트리밍 데이터 처리
- 사용자 인증/권한 관리 (단일 사용자 환경 가정)
- 영구 벡터 DB 서버 운영 (FAISS 로컬 인메모리 사용)
- 다국어 지원 (한국어 전용)
- 모바일 네이티브 앱

## Constraints

- **LLM**: OpenAI·Claude·OpenAI 호환 API 중 선택. 모델 이름과 키 직접 설정
- **임베딩**: OpenAI 또는 OpenAI 호환 API. 채팅과 별도 설정
- **런타임**: Python 3.9+, Streamlit
- **벡터 DB**: FAISS (로컬, 파일 변경 시 재구축)
- **외부 API**: DuckDuckGo (무인증), KOSIS (API 키 선택)
- **대화 컨텍스트**: 최근 6턴 히스토리 유지
- **에이전트 반복**: 최대 MAX_ITERATIONS(기본 10)회

## Implemented Features (v2.4)

### Phase 1 — MVP
- [x] Supervisor-Researcher-Analyst 3-에이전트 LangGraph 워크플로우
- [x] PDF 동적 업로드 및 FAISS RAG 파이프라인
- [x] Streamlit 채팅 UI + 실시간 에이전트 상태 표시
- [x] 채팅·임베딩 API 연동 (제공자별 설정)
- [x] DuckDuckGo 웹 검색 통합

### Phase 2
- [x] 출처 추적 — 문서명, 페이지, URL 자동 추출 및 표시
- [x] 사용자 피드백 — 좋아요/싫어요 위젯 + JSONL 저장
- [x] KOSIS 통계청 API 연동
- [x] 차트 자동 생성 — Analyst 응답의 수치 데이터를 Plotly 차트 변환

### Phase 3
- [x] 대화 히스토리 — 최근 6턴 맥락을 LangGraph에 주입
- [x] 멀티시리즈 차트 — series 배열로 여러 지표 비교
- [x] PDF 출처 딥링크 — 페이지 번호 클릭으로 PDF 뷰어 표시
- [x] Markdown 분석 보고서 생성 및 다운로드

## Success Criteria

- [x] 사용자 질문 → 에이전트 협업 → 출처 포함 분석 결과 반환
- [x] PDF 업로드 후 해당 문서 기반 RAG 검색 동작
- [x] 웹 검색 + KOSIS + RAG 결과를 통합한 분석 제공
- [x] 수치 데이터 포함 응답 시 차트 자동 생성
- [x] 대화 맥락을 유지한 연속 질문 지원

---

*Last updated: 2026-04-03*

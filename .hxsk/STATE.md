---
updated: 2026-11-02
---

# Project State

## Current Position

**Milestone:** BOK 실행 안정화 및 외부 에이전트용 PDF 검색 CLI
**Phase:** 합의한 최소 범위 구현·검증 완료
**Status:** 후속 작업 대기
**Plan:** [현재 명세](SPEC.md), [제품 로드맵](../PRD.txt#development-roadmap)

## Completed

- `d580eef`: 분석 근거 전달, 요청별 반복·시간 한도, 최종 응답 표시 수정 및 PDF 검색 JSON CLI 추가.
- `0529b63`: Azure 전용 설정을 OpenAI·Claude·OpenAI 호환 채팅 제공자 선택 방식으로 전환. 임베딩 설정 분리.
- `6ecfc18`: [에이전트 가이드](../docs/AGENT_GUIDE.md) 작성 및 README·AGENTS 안내 링크 추가.
- 위 세 커밋은 원격 `master`에 반영됨.
- 로그인된 Codex에서 BOK CLI로 실제 PDF를 검색하고, 파일명·PDF 페이지를 인용한 서비스 산업 생산성 분석 수행.

## Verification

2026-11-02 기준 검증 결과입니다.

- 네트워크 연결을 차단하고 `.env` 로드를 대체한 상태에서 기존 테스트 30개 통과.
- PDF CLI, 모델 호출을 대체한 LangGraph·Streamlit 실행, 모의 HTTP 전송을 통한 제공자 설정·요청 형식 검증.
- 가이드의 셸 예시 8개 구문, 내부 링크 6개, 공식 문서 링크 7개 확인.
- 실제 모델·임베딩 API, DuckDuckGo·KOSIS 외부 연동, 전체 Streamlit 사용자 흐름은 이번 작업에서 실환경 검증하지 않음.
- Claude Code의 로그인 기반 분석 명령은 도움말·문서로 확인했으며 실제 추론은 실행하지 않음.

## Active Decisions

| Decision | Choice |
|----------|--------|
| 외부 에이전트 연결 | API 설정 없이 로컬 PDF를 검색하는 BOK CLI 사용 |
| 분석 역할 | 로그인된 Codex·Claude Code가 검색 근거를 해석. BOK는 로그인 토큰을 읽지 않음 |
| 기존 앱 | Streamlit·LangGraph 유지. 채팅·임베딩의 제공자·모델·키를 각각 설정 |
| 범위 제한 | MCP·새 서버·새 UI와 다른 레포 변경은 보류 |

## Unverified and Deferred

- 구현 항목별 검증 한계와 KOSIS 수치 시계열 미구현은 [SPEC](SPEC.md#verification-status)에 기록.
- `llm-trader`, `tossquant-local-poc`, `trade-dashboard`, `quantrade-ng`, `QuanTrade`의 기능 통합·중복 레포 정리는 보류.
- OCR·의미 검색 등 CLI 확장은 현재 합의 범위에 포함하지 않음.

## Next Steps

합의한 최소 범위에 남은 필수 구현 작업은 없습니다. 추가 개발 범위는 아직 확정하지 않았습니다.
실제 사용 중 검색·인용의 부족을 확인한 뒤 필요한 항목만 후속 작업으로 정합니다.

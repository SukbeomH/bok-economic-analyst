---
updated: 2026-11-02
---

# Project State

## Current Position

**Milestone:** 로컬 MCP·검색 서버·웹 UI
**Phase:** 구현·검증·코드 검토 완료
**Status:** 로컬 서버 검증 완료
**Plan:** [로컬 서버 구현 계획](PLAN.md), [현재 명세](SPEC.md)

## Completed

- `d580eef`: 분석 근거 전달, 요청별 반복·시간 한도, 최종 응답 표시 수정 및 PDF 검색 JSON CLI 추가.
- `0529b63`: Azure 전용 설정을 OpenAI·Claude·OpenAI 호환 채팅 제공자 선택 방식으로 전환. 임베딩 설정 분리.
- `6ecfc18`: [에이전트 가이드](../docs/AGENT_GUIDE.md) 작성 및 README·AGENTS 안내 링크 추가.
- 기존 가이드 보완 `fe9d1ff`까지 원격 `master`에 반영됨.
- 로컬 MCP·검색 API·정적 웹 UI 구현. SDK는 승인받은 별도 `.venv-server`와 선택 의존성으로 분리.
- 구형 QuanTrade와 trade-dashboard는 사용자 승인으로 GitHub 아카이브 완료. 배포 서비스는 변경하지 않음.
- 로그인된 Codex에서 BOK CLI로 실제 PDF를 검색하고, 파일명·PDF 페이지를 인용한 서비스 산업 생산성 분석 수행.

## Verification

2026-11-02 기준 검증 결과입니다.

- 네트워크 연결을 차단하고 `.env` 로드를 대체한 상태에서 기존 테스트 30개 통과.
- 서버 환경의 실제 HTTP·MCP 통합 테스트 7개 통과. HTTP 두 프로토콜 모드와 stdio 확인.
- 브라우저의 실제 PDF 검색·인용 복사·빈 결과·문서 오류·모바일 너비·HTML 문자열의 텍스트 표시 확인.
- PDF CLI, 모델 호출을 대체한 LangGraph·Streamlit 실행, 모의 HTTP 전송을 통한 제공자 설정·요청 형식 검증.
- 가이드와 안내 문서의 셸 예시 구문·내부 링크·공식 문서 링크 확인.
- 실제 모델·임베딩 API, DuckDuckGo·KOSIS 외부 연동, 전체 Streamlit 사용자 흐름은 이번 작업에서 실환경 검증하지 않음.
- Claude Code의 로그인 기반 분석 명령은 도움말·문서로 확인했으며 실제 추론은 실행하지 않음.

## Active Decisions

| Decision | Choice |
|----------|--------|
| 외부 에이전트 연결 | API 설정 없는 기존 BOK CLI 또는 선택 설치한 MCP 검색 도구 사용 |
| 분석 역할 | 로그인된 Codex·Claude Code가 검색 근거를 해석. BOK는 로그인 토큰을 읽지 않음 |
| 기존 앱 | Streamlit·LangGraph 유지. 채팅·임베딩의 제공자·모델·키를 각각 설정 |
| 로컬 서버 | MCP·HTTP·정적 UI를 서버 하나로 제공. 폴더는 시작 시 고정, HTTP는 loopback에만 바인딩 |
| 범위 제한 | 다른 레포 변경·기능 통합은 이번 구현에서 제외 |

## Unverified and Deferred

- 구현 항목별 검증 한계와 KOSIS 수치 시계열 미구현은 [SPEC](SPEC.md#verification-status)에 기록.
- 다른 레포의 기능 통합은 보류. 아카이브된 레포를 이번 작업에서 변경하지 않음.
- OCR·의미 검색 등 CLI 확장은 현재 합의 범위에 포함하지 않음.

## Next Steps

기존 CLI와 선택 서버의 합의 범위는 구현·검증했습니다. 실제 에이전트 설정 등록과 모델을 통한
MCP 호출은 실행하지 않았습니다. 최종 검토 후 한 커밋으로 정리하며 원격 푸시는 별도 요청 시 진행합니다.

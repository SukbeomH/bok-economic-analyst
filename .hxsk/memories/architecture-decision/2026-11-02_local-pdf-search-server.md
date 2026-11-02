---
title: "로컬 PDF 검색 서버의 SDK 환경 분리"
tags: [arch, mcp, pdf-search]
type: architecture-decision
created: 2026-11-02T12:19:47+09:00
contextual_description: "MCP·HTTP·정적 UI를 한 서버에 두고 SDK 의존성을 기존 앱과 분리한다."
keywords: [MCP, Pydantic, stdio, loopback]
---

## 로컬 PDF 검색 서버의 SDK 환경 분리

공식 MCP SDK 2.3.0은 기존 앱의 Pydantic 핀과 다른 버전을 요구하므로 승인받은
`requirements-server.txt`와 `.venv-server`를 사용한다. 기존 CLI는 SDK 없이 동작한다.
서버 하나에서 검색 API·MCP·정적 UI를 제공하고 검색 폴더는 시작 때 고정한다.
모델·업로드·DB는 추가하지 않는다. 설계 대안과 실제 검증은 `.hxsk/PLAN.md`에 기록했다.

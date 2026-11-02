# 로컬 MCP·검색 서버·웹 UI 구현 계획

상태: 구현·검증 완료. 공식 SDK의 선택 의존성 추가와 별도 가상환경 사용을 승인받았습니다.

## 목표와 범위

기존 `bok_documents.search_documents`를 HTTP API, MCP 도구, 작은 검색 화면에서 공유합니다.
별도 모델 API 키 없이 PDF 근거를 제공하고, 분석은 로그인된 외부 에이전트가 수행합니다.
기존 CLI와 Streamlit 앱의 동작은 유지합니다. 다른 레포는 변경하지 않습니다.

## 사용 흐름

저장소 루트에서 실행합니다. Python 3.12 환경에서 검증했습니다.

```bash
uv venv .venv-server --python 3.12
uv pip install --python .venv-server/bin/python -r requirements-server.txt
.venv-server/bin/python -m bok_server --port 8765 --data-dir data
```

- 웹 UI: `http://127.0.0.1:8765/`
- 검색 API: `GET /api/search?query=생산성&limit=5`
- MCP: `http://127.0.0.1:8765/mcp`, 검색 도구 하나.
- 로컬 에이전트가 프로세스를 직접 시작하는 stdio도 같은 도구 등록을 재사용합니다.

## 선택한 구성

공식 MCP Python SDK 2.3.0의 ASGI 앱 하나에 검색 API와 정적 UI를 등록합니다.
SDK와 PyMuPDF는 `requirements-server.txt`로 선택 설치합니다. SDK 2.x의 Pydantic 요구사항이
기존 앱의 핀과 다르므로 `.venv-server`를 사용하고 기존 `requirements.txt`는 변경하지 않습니다.

| 파일 | 소유하는 책임 |
|---|---|
| `bok_documents.py` | 기존 PDF 읽기·검색과 공용 검색 결과 직렬화 |
| `bok_cli.py` | 기존 명령·종료 코드 유지, 공용 직렬화 사용 |
| `bok_server.py` | 서버 시작 설정, MCP·HTTP 입력 검증, 고정 검색 폴더, 로컬 접근 제한 |
| `web/index.html` | 검색어·결과 수 입력, 결과·파일명·페이지 표시와 인용 복사 |
| `tests_server/test_server.py` | HTTP·MCP 호출과 기존 CLI의 결과 일치·오류·접근 경계 검증 |

구현한 서버 진입점과 공용 직렬화 함수입니다.

```python
def search_result_payload(result: SearchResult) -> dict: ...
def create_server(data_dir: Path) -> MCPServer: ...
def create_http_app(server: MCPServer): ...
def main(argv=None) -> int: ...
```

공개 검색 입력은 `query`, `limit`뿐입니다. 폴더는 서버 시작 때 지정하고 도구·API에서
임의 경로나 파일을 받지 않습니다. 검색 성공 JSON은 기존 CLI와 같은 필드를 유지합니다.
빈 문서함과 일치 없음은 정상 상태로 구분하고 입력·문서 오류는 전송 방식에 맞는 실패로 반환합니다.

## 비교한 대안

- 선택안은 MCP·HTTP·UI의 프로세스와 검색 폴더 설정을 하나로 유지합니다.
- stdio MCP와 표준 라이브러리 HTTP 서버를 분리하는 대안은 SDK 없이 HTTP를 쓸 수 있지만,
  두 서버의 파싱·오류·접근 제한·설정 관리가 필요합니다. 이번 범위에서는 선택하지 않습니다.
- 대안에서 검색 폴더를 시작 설정으로 고정하는 경계를 반영했습니다. 별도 공용 서비스 계층은 만들지 않습니다.
- 두 설계 후보는 같은 모델로 검토했습니다. 서로 다른 모델의 교차 심사로 취급하지 않습니다.

## 경계와 수용한 한계

- HTTP는 `127.0.0.1`에만 바인딩합니다. API·UI에도 Host·Origin 검증을 적용합니다.
- MCP stdout에는 프로토콜 메시지만 출력합니다. PDF 진단 출력이 섞이지 않는지 검증합니다.
- PDF 검색은 단일 프로세스에서 직렬 처리합니다. 큰 폴더 검색 중 응답이 지연될 수 있습니다.
- UI는 본문을 HTML로 실행하지 않고 텍스트로 표시합니다.
- 모델 호출, 업로드, DB·캐시, 백그라운드 수집, 계정·로그인 토큰 접근, 공개 배포는 추가하지 않습니다.

## 구현·검증 결과

- [x] 기존 검색 코어·CLI·의존성 영향 범위 확인, 두 설계 후보 비교.
- [x] 공식 SDK 선택 의존성 추가 승인.
- [x] 서버와 공용 직렬화 구현. 기존 CLI JSON 계약 유지.
- [x] 검색 화면 구현. 검색·결과·오류·인용 복사 흐름 제공.
- [x] 실제 SDK 클라이언트로 MCP 도구 조회·호출, HTTP와 CLI 결과 비교.
- [x] 임시 PDF로 빈 문서함·일치 없음·입력 오류·손상 PDF·출력 오염·접근 제한 검증.
- [x] 브라우저에서 데스크톱·모바일 검색 흐름 확인.
- [x] 기존 테스트 회귀 확인. 문서에 실행·연결 방법과 검증 한계 반영.

검증은 실제 모델 API 없이 수행했습니다.

- 기존 앱 환경의 테스트 30개 통과. 모델을 대체하고 네트워크 연결을 차단했습니다.
- 별도 서버 환경의 통합 테스트 7개 통과. CLI·HTTP·MCP 응답 일치, HTTP의 두 프로토콜 모드,
  stdio, 빈 결과·손상 PDF·입력 오류·Host·Origin·파일 접근 제한을 확인했습니다.
- 서버 테스트는 로컬 HTTP·MCP를 실제 호출합니다. 테스트 클라이언트의 외부 연결은 차단합니다.
- 내장 브라우저에서 실제 PDF 검색·인용 복사·일치 없음·빈 폴더·손상 PDF 오류를 확인했습니다.
  1280px·390px 너비에서 가로 넘침이 없었고 PDF의 HTML 문자열은 실행되지 않았습니다.
- SDK 등록 시 일반 `dict` 반환 선언이 거부되는 문제를 발견해 `dict[str, object]`로 수정했습니다.
  이후 도구 조회·호출과 통합 테스트가 통과했습니다.
- Codex·Claude Code 등록 명령은 도움말로 확인했습니다. 사용자 MCP 설정 변경이나 모델 호출은 하지 않았습니다.
- 선택 서버 테스트는 기존 앱 테스트와 별도로 실행하여 SDK 없는 CLI 환경도 유지합니다.

참고: [공식 SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0),
[HTTP 앱·추가 경로](https://py.sdk.modelcontextprotocol.io/run/asgi/).

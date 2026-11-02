"""
AI 한국은행 경제 분석팀 - 메인 Streamlit 앱
Streamlit 네이티브 컴포넌트 우선 사용으로 안정적이고 일관된 UI 제공
"""
import os
import hashlib
import time
import streamlit as st
from typing import TypedDict, Annotated, List
from typing_extensions import NotRequired
from langchain_core.messages import HumanMessage, AIMessage, convert_to_messages

# LangGraph 관련
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool

# 분리된 모듈들 import
from core import Config, logger, ModelFactory, web_search_func, build_rag_pipeline
from core.citation import wrap_retriever_with_citation
from core.state_manager import StateManager
from utils import setup_environment, EnvironmentValidator
from components.sidebar import render_sidebar
from components.chat_interface import (
    render_chat_interface, 
    render_evidence_preview
)


# ==============================================================================
# 멀티 에이전트 정의
# ==============================================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    started_at: NotRequired[float]
    iterations: NotRequired[int]


class _SimpleAgentExecutor:
    """도구 없이 최종 응답만 생성하는 간단 실행기."""
    def __init__(self, runnable):
        self._runnable = runnable

    def invoke(self, inputs):
        text = self._runnable.invoke(inputs)
        return {"output": text}


def create_agent(llm, tools: list, system_prompt: str, use_react: bool = True):
    """에이전트를 생성합니다."""
    tools_desc = "\n".join([f"- {t.name}: {getattr(t, 'description', '')}" for t in tools])
    tool_names = ", ".join([t.name for t in tools])
    logger.info("[agent] 에이전트 생성: tools=[%s], mode=%s", tool_names, "react" if use_react else "final")

    if use_react and len(tools) > 0:
        from langchain.agents import create_tool_calling_agent
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "{system_prompt}\n\n사용 가능한 도구:\n{tools}\n\n도구 이름 목록: {tool_names}\n\n중요: 반드시 제공된 도구를 사용하여 정보를 수집하세요. 도구 사용 없이 일반적인 답변을 하지 마세요."
            ),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]).partial(system_prompt=system_prompt, tools=tools_desc, tool_names=tool_names)
        
        agent = create_tool_calling_agent(llm, tools, prompt)
        return AgentExecutor(agent=agent, tools=tools, verbose=False)

    # 도구가 없거나 최종 응답만 원하는 경우
    from langchain_core.output_parsers import StrOutputParser
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}\n\n요청에 대해 최종 답변만 생성하세요. 불필요한 사고과정이나 도구 호출 지시문을 출력하지 마세요. 항상 구체적인 결론을 포함한 한국어 최종 답변을 간결히 작성하세요."),
        ("human", "{input}")
    ]).partial(system_prompt=system_prompt)
    runnable = prompt | llm | StrOutputParser()
    return _SimpleAgentExecutor(runnable)


def agent_node(state, agent, name):
    """에이전트 노드 실행 함수"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conversation = []
            for message in state["messages"]:
                content = message.text()
                if not isinstance(message, HumanMessage) and content.strip().upper().startswith("ROUTE:"):
                    continue
                speaker = message.name or message.type
                conversation.append(f"[{speaker}]\n{content}")
            worker_input = "\n\n".join(conversation)
            result_text = AIMessage(content=agent.invoke({"input": worker_input}).get("output", "")).text()

            return {"messages": [{"content": result_text, "role": "assistant", "name": name}]}
            
        except Exception as e:
            logger.warning("[agent-node:%s] 시도 %d/%d 실패: %s", name, attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.exception("[agent-node:%s] 모든 시도 실패", name)
                error_message = f"Error in {name} Agent: {e}"
                return {"messages": [{"content": error_message, "role": "assistant", "name": "error"}]}
    
    error_message = f"Error in {name} Agent: 모든 재시도 실패"
    return {"messages": [{"content": error_message, "role": "assistant", "name": "error"}]}


def create_supervisor(llm, agent_names: List[str]):
    """Supervisor를 생성합니다."""
    system_prompt = (
        "당신은 여러 AI 에이전트를 관리하는 감독관입니다. 당신의 유일한 임무는 라우팅 결정입니다.\n\n"
        "**엄격한 출력 규칙:**\n"
        "당신은 반드시 다음 중 하나만 정확히 출력해야 합니다:\n"
        "1. ROUTE: researcher  (정보 수집 필요)\n"
        "2. ROUTE: analyst     (분석 필요)\n"
        "3. ROUTE: END         (작업 완료)\n\n"
        "**금지사항:**\n"
        "- 'Final Answer:' 사용 금지 (Analyst가 담당)\n"
        "- 설명, 생각, JSON, 도구호출 금지\n"
        "- 규칙 외 모든 출력 금지\n\n"
        "**대화 맥락:**\n"
        "- 이전 대화 히스토리가 messages에 포함될 수 있습니다\n"
        "- 사용자가 '아까', '위에서', '이전에' 등으로 이전 대화를 참조하면 맥락을 활용하세요\n"
        "- 새로운 주제의 질문이면 이전 맥락을 무시하세요\n\n"
        "**라우팅 기준:**\n"
        "- 정보 부족 시: ROUTE: researcher\n"
        "- 분석 필요 시: ROUTE: analyst\n"
        "- 완료 시: ROUTE: END\n"
        "- 불명확 시: ROUTE: END (안전한 종료)\n\n"
        "**반복 한도:**\n"
        "- 최대 10회 반복 후 자동 종료\n"
        "- 무한 루프 방지를 위해 보수적 라우팅\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        MessagesPlaceholder("messages"),
    ]).partial(system_prompt=system_prompt)

    def supervisor_node(state):
        messages = state.get("messages", []) if isinstance(state, dict) else []
        logger.info("[supervisor] 입력 메시지 수=%d", len(messages))
        
        now = time.monotonic()
        started_at = state.get("started_at", now)
        iterations = state.get("iterations", 0)
        update = {"started_at": started_at, "iterations": iterations}
        if iterations >= Config.MAX_ITERATIONS or now - started_at >= Config.TIMEOUT_SECONDS:
            logger.warning("[supervisor] 요청별 실행 한도 도달")
            return {**update, "messages": [AIMessage(content="ROUTE: END", name="supervisor")]}

        formatted = prompt.invoke({"messages": messages})
        ai_msg = llm.invoke(formatted)
        return {**update, "iterations": iterations + 1, "messages": [ai_msg]}

    return supervisor_node


def create_graph(llm, retriever):
    """LangGraph를 생성합니다."""
    
    # 기본 검색 도구
    researcher_tools = [
        Tool(
            name="bok_document_search",
            func=wrap_retriever_with_citation(retriever),
            description="사용자가 업로드한 PDF 문서나 한국은행 공식 문서를 검색하여 특정 경제 용어, 정책, 보고서 내용을 찾습니다. 결과에 문서명과 페이지 번호가 포함됩니다."
        ),
        Tool(
            name="web_search",
            func=web_search_func,
            description="최신 경제 뉴스나 실시간 시장 반응 등 현재 정보를 위해 웹을 검색합니다."
        ),
    ]
    
    # 완화된 검색 도구 (RAG 파이프라인에서 생성)
    relaxed_retriever = None
    try:
        from core.rag_pipeline import rag_pipeline
        if rag_pipeline and hasattr(rag_pipeline, 'create_relaxed_retriever'):
            relaxed_retriever = rag_pipeline.create_relaxed_retriever()
            if relaxed_retriever:
                logger.info("[graph] 완화된 검색 도구 생성 완료")
    except Exception as e:
        logger.warning("[graph] 완화된 검색 도구 생성 실패: %s", e)
    
    # 완화된 검색 도구가 있으면 추가
    if relaxed_retriever:
        researcher_tools.append(
            Tool(
                name="relaxed_document_search",
                func=wrap_retriever_with_citation(relaxed_retriever),
                description="유사도 제한을 완화하여 더 넓은 범위에서 관련 문서를 검색합니다. 결과에 문서명과 페이지 번호가 포함됩니다."
            )
        )
    
    # KOSIS 도구 추가 (API 키가 있을 경우만)
    if Config.KOSIS_API_KEY:
        from core.kosis_client import search_kosis
        researcher_tools.append(
            Tool(
                name="kosis_statistics_search",
                func=search_kosis,
                description="KOSIS 국가통계포털에서 공식 통계 데이터를 검색합니다. 소비자물가지수, GDP, 실업률 등 한국 경제 통계를 조회할 때 사용하세요."
            )
        )
        logger.info("[graph] KOSIS 검색 도구 추가 완료")

    researcher_system_prompt = """당신은 전문 경제 연구원입니다. 사용자의 요청에 따라 제공된 문서와 웹에서 정확하고 객관적인 정보를 찾아서 제공하는 역할을 합니다.

**중요: 반드시 도구를 사용하세요!**
- bok_document_search: PDF 문서나 한국은행 공식 문서 검색 (기본 검색)
- web_search: 최신 경제 뉴스나 실시간 정보 검색
- relaxed_document_search: 유사도 제한을 완화한 문서 검색 (기본 검색 실패 시)
- kosis_statistics_search: KOSIS 국가통계포털 공식 통계 데이터 검색 (API 키 필요)

**검색 전략:**
1. **1단계: 기본 검색** - bok_document_search와 web_search를 사용하여 정확한 정보 검색
1-1. **공식 통계** - 수치 데이터가 필요하면 kosis_statistics_search를 사용
2. **2단계: 완화된 검색** - 기본 검색에서 정보를 찾지 못한 경우 relaxed_document_search 사용
3. **결과 평가** - 검색 결과가 충분하지 않으면 더 넓은 범위에서 재검색

**출처 정보 포함 필수:**
- 모든 정보는 반드시 출처를 명시해야 합니다
- PDF 문서: 파일명과 페이지 번호 포함
- 웹 검색: URL과 사이트명 포함
- 한국은행 공식 문서: 문서명과 발행일 포함

**출력 형식:**
[수집된 정보]
- 구체적이고 객관적인 정보 내용

[출처 정보]
1. 출처: [파일명/URL] 페이지/사이트 정보
   근거: 관련 텍스트 요약
   신뢰도: 높음/중간/낮음

[신뢰도 평가]
- 정보 품질: X/10
- 출처 신뢰성: X/10  
- 최신성: X/10

**검색 실패 시 대응:**
- 기본 검색에서 정보를 찾지 못하면 relaxed_document_search를 사용하세요
- 완화된 검색에서도 정보가 부족하면 구체적인 검색어 제안을 포함하세요
- 최소한의 관련 정보라도 찾아서 제공하세요

**금지사항:**
- 도구 사용 없이 일반적인 설명이나 추측을 하지 마세요
- 반드시 실제 검색 결과를 바탕으로 답변하세요
- 검색을 시도하지 않고 바로 포기하지 마세요"""

    researcher_agent = create_agent(
        llm,
        researcher_tools,
        researcher_system_prompt,
        use_react=True,
    )
    
    analyst_system_prompt = """당신은 날카로운 통찰력을 가진 경제 분석가입니다. 주어진 데이터(context)를 바탕으로 사용자의 질문에 대한 깊이 있는 분석과 명확한 답변을 생성합니다.

**분석 요구사항:**
1. 핵심 트렌드 및 패턴 식별
2. 원인과 결과 관계 분석  
3. 잠재적 영향 및 시사점 도출
4. 근거 기반 결론 제시

**출력 형식:**
[분석 결과]
- 심층적이고 통찰력 있는 분석 내용
- 데이터 기반의 객관적 분석

[근거 및 출처]
- 분석에 사용된 주요 근거들
- 출처 정보 포함 (Researcher가 제공한 출처 활용)

[결론]
- 명확하고 실행 가능한 결론
- 신뢰도와 한계점 명시

**인용 필수:**
- 모든 분석은 반드시 근거를 제시해야 합니다
- Researcher가 제공한 출처 정보를 활용하세요
- 출처 없이 추측이나 의견만으로 분석하지 마세요

**수치 데이터 시각화:**
분석에 시계열, 비교, 추이 등 수치 데이터가 포함되면 아래 형식으로 차트 데이터를 함께 출력하세요:

```chart_data
{
  "title": "차트 제목",
  "type": "line|bar|scatter",
  "x": ["label1", "label2"],
  "y": [value1, value2],
  "x_label": "X축 레이블",
  "y_label": "Y축 레이블"
}
```

여러 지표를 비교할 때는 series를 사용하세요:

```chart_data
{
  "title": "경제지표 비교",
  "type": "line",
  "x": ["Q1", "Q2", "Q3"],
  "series": [
    {"name": "GDP", "y": [2.1, 2.3, 2.0]},
    {"name": "CPI", "y": [3.2, 2.8, 2.5]}
  ],
  "x_label": "분기",
  "y_label": "%"
}
```

수치 데이터가 없거나 시각화가 불필요한 경우에는 chart_data 블록을 생략하세요."""

    analyst_agent = create_agent(
        llm,
        [],
        analyst_system_prompt,
        use_react=False,
    )
    
    logger.info("[graph] 노드 생성: researcher, analyst, chart_processor, supervisor")

    # chart_processor 노드: Analyst 응답에서 chart_data를 추출하여 차트 생성
    from core.chart_generator import extract_chart_data, create_chart

    def chart_processor_node(state):
        """Analyst 응답에서 chart_data를 추출하고 차트를 생성한다."""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_msg = messages[-1]
        content = last_msg.text()

        chart_data = extract_chart_data(content)
        if chart_data:
            fig = create_chart(chart_data)
            if fig:
                if "pending_charts" not in st.session_state:
                    st.session_state["pending_charts"] = []
                st.session_state["pending_charts"].append(fig)
                logger.info("[chart] 차트를 pending_charts에 추가")

        return {"messages": []}

    workflow = StateGraph(AgentState)
    workflow.add_node("researcher", lambda state: agent_node(state, researcher_agent, "researcher"))
    workflow.add_node("analyst", lambda state: agent_node(state, analyst_agent, "analyst"))
    workflow.add_node("chart_processor", chart_processor_node)

    supervisor_chain = create_supervisor(llm, ["researcher", "analyst"])
    workflow.add_node("supervisor", supervisor_chain)

    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("analyst", "chart_processor")
    workflow.add_edge("chart_processor", END)
    
    def route_action(state):
        messages = state["messages"]
        last_message = messages[-1]
        content = last_message.text()
        
        logger.info("[route_action] 분석 중: %s", content[:100])
        
        if isinstance(content, str):
            upper = content.strip().upper()
            
            if upper.startswith("ROUTE:"):
                route = upper.split(":", 1)[1].strip()
                logger.info("[route_action] ROUTE 감지: %s", route)
                
                if route == "RESEARCHER":
                    return "researcher"
                elif route == "ANALYST":
                    return "analyst"
                elif route == "END":
                    return END
                else:
                    logger.warning("[route_action] 잘못된 ROUTE 값: %s, 안전 종료", route)
                    return END
            
            elif upper.startswith("FINAL ANSWER:"):
                logger.warning("[route_action] Final Answer 패턴 감지 (규칙 위반)")
                stripped = content[len("Final Answer:"):].strip()
                if stripped.lower().startswith("route:"):
                    route = stripped.split(":", 1)[1].strip().lower()
                    if route == "researcher":
                        return "researcher"
                    elif route == "analyst":
                        return "analyst"
                    elif route == "end":
                        return END
                if stripped:
                    return "analyst"
                return END
            
            elif "추가 검색 필요" in content or "근거가 부족" in content:
                logger.info("[route_action] 근거 부족 감지, Researcher로 재라우팅")
                return "researcher"
            
            elif upper:
                logger.warning("[route_action] 규칙 외 출력 감지: %s, 안전 종료", content[:50])
                return END
        
        logger.warning("[route_action] 예상치 못한 형식, 안전 종료")
        return END

    workflow.add_conditional_edges("supervisor", route_action)
    workflow.set_entry_point("supervisor")

    compiled_graph = workflow.compile()
    logger.info("[graph] Supervisor 판단 한도: %d", Config.MAX_ITERATIONS)
    
    return compiled_graph


# ==============================================================================
# 메인 앱
# ==============================================================================
def main():
    """메인 앱 함수"""
    # 페이지 설정
    st.set_page_config(
        page_title="🏦 AI 한국은행 경제 분석팀",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Streamlit 네이티브 컴포넌트 사용
    
    # 데이터 디렉토리 생성
    os.makedirs(Config.DATA_DIR, exist_ok=True)

    # 세션 상태 초기화
    StateManager.initialize_session_state()
    
    # 메인 채팅 인터페이스
    main_chat_interface()


def main_chat_interface():
    """메인 채팅 인터페이스"""
    try:
        # 환경 설정
        setup_environment()
        model_factory = ModelFactory()

        # 사이드바 렌더링
        uploaded_files = render_sidebar()

        # 헤더 렌더링
        st.header("🏦 AI 한국은행 경제 분석팀")
        st.caption("멀티 에이전트가 협력하여 질문에 대한 심층 분석을 제공합니다.")

        # 그래프 초기화
        if not StateManager.is_agent_graph_valid():
            # 초기화 과정을 채팅 영역에 통합
            with st.chat_message("assistant"):
                st.info("🔄 **AI 분석팀을 구성하는 중입니다...**")
                
                # LLM 초기화
                st.write("🧠 **LLM 초기화 중...**")
                llm = model_factory.get_chat_model()
                st.write(f"✅ {Config.LLM_PROVIDER} 채팅 모델 준비 완료")
                logger.info("[init] LLM 초기화 완료")

                # RAG 파이프라인 구축
                st.write("📚 **RAG 파이프라인 구축 중...**")
                import glob
                pdf_files = glob.glob(os.path.join(Config.DATA_DIR, "*.pdf"))
                
                # 캐시 키 생성
                def _file_sig(path: str) -> str:
                    try:
                        return f"{os.path.basename(path)}:{int(os.path.getmtime(path))}"
                    except Exception:
                        return os.path.basename(path)
                
                key_src = Config.APP_GRAPH_VERSION + "|" + Config.embedding_signature() + "|" + ",".join(sorted([_file_sig(p) for p in pdf_files]))
                cache_key = hashlib.sha256(key_src.encode()).hexdigest()
                
                retriever = build_rag_pipeline(cache_key)
                st.write("✅ RAG 리트리버 준비 완료")
                logger.info("[init] RAG 리트리버 준비 완료")

                # 그래프 생성
                st.write("🕸️ **LangGraph 그래프 컴파일 중...**")
                graph = create_graph(model_factory.get_chat_model(), retriever)
                StateManager.set_agent_graph(graph, Config.APP_GRAPH_VERSION)
                
                st.success("✅ **초기화 완료!** 이제 질문하실 수 있습니다.")
                logger.info("[init] 그래프 컴파일 완료")

        # 구분선 렌더링
        st.divider()
        
        # 채팅 인터페이스 렌더링
        prompt = render_chat_interface()

        if prompt:
            # 사용자 메시지 추가
            StateManager.add_message("user", prompt)
            
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                try:
                    # 분석 시작 메시지
                    st.info("🔄 **분석팀이 작업을 시작합니다...**")
                    
                    final_response = ""
                    accumulated_messages = []

                    # 대화 히스토리를 LangChain 메시지로 변환
                    history_messages = []
                    for msg in StateManager.get_messages()[:-1]:  # 마지막(현재) 메시지 제외
                        if msg["role"] == "user":
                            history_messages.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            history_messages.append(AIMessage(content=msg["content"]))

                    # 최근 N턴만 포함 (토큰 제한 방지)
                    if len(history_messages) > Config.MAX_HISTORY_TURNS * 2:
                        history_messages = history_messages[-(Config.MAX_HISTORY_TURNS * 2):]

                    all_messages = history_messages + [HumanMessage(content=prompt)]

                    for chunk in StateManager.get_agent_graph().stream(
                        {"messages": all_messages},
                        config={"recursion_limit": Config.MAX_ITERATIONS * 2 + 3},
                        stream_mode="updates"
                    ):
                        logger.debug("[run] chunk=%s", chunk)
                        
                        for node, label in (
                            ("supervisor", "🧠 Supervisor가 다음 단계를 결정 중입니다..."),
                            ("researcher", "🔍 Researcher가 정보를 수집하고 있습니다..."),
                            ("analyst", "✍️ Analyst가 데이터를 분석하고 보고서를 작성 중입니다..."),
                        ):
                            if node not in chunk:
                                continue
                            st.write(label)
                            for message in convert_to_messages(chunk[node].get("messages", [])):
                                content = message.text().strip()
                                if not content or content.upper().startswith("ROUTE:"):
                                    continue
                                if node == "supervisor":
                                    continue
                                accumulated_messages.append(content)
                                if node == "analyst":
                                    final_response = content

                    if not final_response:
                        final_response = accumulated_messages[-1] if accumulated_messages else (
                            "요청하신 정보를 찾지 못했습니다. 더 구체적인 키워드나 다른 질문으로 다시 시도해주세요."
                        )
                    render_evidence_preview(final_response)
                    for figure in st.session_state.pop("pending_charts", []):
                        st.plotly_chart(figure, use_container_width=True)
                    st.success("✅ 분석 완료!")

                except Exception as e:
                    logger.exception("[run] 상태 업데이트 중 오류")
                    final_response = "분석 중 오류가 발생했습니다. 다시 시도해주세요."

                st.write(final_response)
                logger.info("[run] 최종 응답 길이=%d", len(final_response))

                # 보고서 다운로드 버튼
                from core.report_generator import generate_report
                from utils.helpers import extract_preview_sources
                import re as _re
                report_sources = extract_preview_sources(final_response)
                chart_titles = [m.group(1) for m in _re.finditer(r'"title":\s*"([^"]+)"', final_response)]
                last_query_for_report = ""
                for msg in reversed(StateManager.get_messages()):
                    if msg["role"] == "user":
                        last_query_for_report = msg["content"]
                        break
                report_md = generate_report(last_query_for_report, final_response, report_sources, chart_titles or None)
                report_timestamp = __import__("time").strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📥 보고서 다운로드",
                    data=report_md,
                    file_name=f"경제분석보고서_{report_timestamp}.md",
                    mime="text/markdown",
                    key=f"report_dl_{StateManager.get_feedback_index()}",
                )

                # 피드백 위젯
                from core.feedback import save_feedback
                feedback_key = f"feedback_{StateManager.get_feedback_index()}"
                feedback_val = st.feedback("thumbs", key=feedback_key)
                if feedback_val is not None:
                    last_query = ""
                    for msg in reversed(StateManager.get_messages()):
                        if msg["role"] == "user":
                            last_query = msg["content"]
                            break
                    save_feedback(last_query, final_response, feedback_val)
                    StateManager.increment_feedback_index()
                    if feedback_val == 1:
                        st.toast("감사합니다! 피드백이 저장되었습니다.", icon="👍")
                    else:
                        st.toast("피드백이 저장되었습니다. 개선에 참고하겠습니다.", icon="📝")

                # 어시스턴트 메시지 추가
                StateManager.add_message("assistant", final_response)

    except Exception as e:
        logger.exception("[app] 전역 오류")
        st.error(f"오류가 발생했습니다: {str(e)}")



if __name__ == "__main__":
    main()

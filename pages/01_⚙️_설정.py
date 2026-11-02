"""
⚙️ 설정 페이지
환경설정 및 검증 기능을 제공합니다.
Streamlit 네이티브 컴포넌트 우선 사용으로 안정적이고 일관된 UI 제공
"""
import streamlit as st
from core import Config
from core.state_manager import StateManager
from utils import EnvironmentValidator


def main():
    """설정 페이지 메인 함수"""
    st.title("⚙️ 환경설정")
    st.markdown("애플리케이션의 설정을 관리합니다.")
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs(["🔧 기본 설정", "🔍 환경 검증", "📊 상태 정보", "📊 피드백 통계"])

    with tab1:
        basic_settings_interface()

    with tab2:
        environment_validation_interface()

    with tab3:
        state_info_interface()

    with tab4:
        feedback_stats_interface()


def basic_settings_interface():
    """기본 설정 인터페이스"""
    st.subheader("🔧 기본 설정")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("채팅 제공자", Config.LLM_PROVIDER)
        st.metric("채팅 모델", Config.LLM_MODEL)
        st.metric("임베딩 제공자", Config.EMBEDDING_PROVIDER)
        st.metric("임베딩 모델", Config.EMBEDDING_MODEL)
        st.metric("데이터 디렉토리", Config.DATA_DIR)
        st.metric("앱 그래프 버전", Config.APP_GRAPH_VERSION)
    
    with col2:
        st.metric("최대 반복 횟수", Config.MAX_ITERATIONS)
        st.metric("타임아웃 (초)", Config.TIMEOUT_SECONDS)
    
    st.subheader("📚 RAG 설정")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("검색 전략", Config.RAG_SEARCH_STRATEGY)
        st.metric("검색 결과 수 (K)", Config.RAG_K)
        st.metric("가져올 결과 수 (Fetch K)", Config.RAG_FETCH_K)
    
    with col2:
        st.metric("MMR 람다", Config.RAG_LAMBDA_MULT)
        st.metric("점수 임계값", Config.RAG_SCORE_THRESHOLD)
        st.metric("압축 사용", "예" if Config.RAG_USE_COMPRESSION else "아니오")
    
    st.subheader("📝 출력 형식")
    
    with st.expander("인용 형식", expanded=False):
        st.code(Config.CITATION_FORMAT, language="text")
    
    with st.expander("Researcher 출력 형식", expanded=False):
        st.code(Config.RESEARCHER_OUTPUT_FORMAT, language="text")
    
    with st.expander("Analyst 출력 형식", expanded=False):
        st.code(Config.ANALYST_OUTPUT_FORMAT, language="text")
    
    st.subheader("🔍 환경 변수")
    
    env_vars = Config.get_all_settings()

    for key, value in env_vars.items():
        st.text(f"{key}: {value}")
    
    st.info("💡 환경 변수를 변경하려면 .env 파일을 수정하고 애플리케이션을 재시작하세요.")


def environment_validation_interface():
    """환경 검증 인터페이스"""
    st.subheader("🔍 환경 검증")
    st.markdown("환경 변수와 설정의 유효성을 검증합니다.")
    
    # 검증 실행
    if st.button("🔍 환경 검증 실행", type="primary"):
        is_valid, results = EnvironmentValidator.validate_all()
        
        # 결과 표시
        if results["errors"]:
            st.error("❌ 오류 발견")
            for error in results["errors"]:
                st.error(f"   - {error}")
        
        if results["warnings"]:
            st.warning("⚠️ 경고 발견")
            for warning in results["warnings"]:
                st.warning(f"   - {warning}")
        
        if results["info"]:
            st.info("ℹ️ 정보")
            for info in results["info"]:
                st.info(f"   - {info}")
        
        if is_valid:
            st.success("✅ 환경 설정이 유효합니다!")
        else:
            st.error("❌ 환경 설정에 문제가 있습니다. 위의 오류를 수정하세요.")
    
    # 환경 정보 표시
    st.subheader("🌍 환경 정보")
    
    env_info = Config.get_environment_info()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Python 버전", env_info["python_version"])
        st.metric("플랫폼", env_info["platform"])
    
    with col2:
        st.metric(".env 파일", "존재" if env_info["env_file_exists"] else "없음")
        st.metric("데이터 디렉토리", "존재" if env_info["data_dir_exists"] else "없음")
    
    # 설정 가이드
    st.subheader("📖 설정 가이드")
    
    with st.expander("환경 변수 설정 방법", expanded=False):
        st.markdown(EnvironmentValidator.get_setup_instructions())
    
    # .env 파일 생성 버튼
    if st.button("📝 .env 파일 생성", type="secondary"):
        if EnvironmentValidator.create_env_file():
            st.success("✅ .env 파일이 생성되었습니다. 실제 값으로 수정하세요.")
        else:
            st.error("❌ .env 파일 생성에 실패했습니다.")
    
    # 설정 요약 출력
    if st.button("📋 설정 요약 출력", type="secondary"):
        with st.expander("설정 요약", expanded=True):
            st.code(Config.print_config_summary.__doc__ or "설정 요약을 확인하세요.")


def state_info_interface():
    """상태 정보 인터페이스"""
    st.subheader("📊 세션 상태 정보")
    
    # 세션 상태 정보 표시
    session_info = StateManager.get_session_info()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("업로더 키", session_info["uploader_key"])
        st.metric("메시지 수", session_info["messages_count"])
        st.metric("웹검색 활성화", "예" if session_info["web_search_enabled"] else "아니오")
    
    with col2:
        st.metric("로그 표시", "예" if session_info["show_logs"] else "아니오")
        st.metric("그래프 유효성", "예" if session_info["agent_graph_valid"] else "아니오")
        st.metric("그래프 버전", session_info["agent_graph_version"] or "없음")
    
    # 상태 초기화 버튼
    if st.button("🔄 모든 상태 초기화", type="secondary"):
        StateManager.reset_all()
        st.success("모든 상태가 초기화되었습니다.")
        st.rerun()
    
    # 상세 상태 정보
    st.subheader("🔍 상세 상태 정보")
    
    with st.expander("전체 세션 정보", expanded=False):
        st.json(session_info)
    
    # 메시지 히스토리
    if session_info["messages_count"] > 0:
        st.subheader("💬 메시지 히스토리")
        messages = StateManager.get_messages()
        
        for i, message in enumerate(messages[-5:], 1):  # 최근 5개만 표시
            role = message.get("role", "unknown")
            content = message.get("content", "")[:100] + "..." if len(message.get("content", "")) > 100 else message.get("content", "")
            
            if role == "user":
                st.info(f"👤 사용자 {i}: {content}")
            elif role == "assistant":
                st.success(f"🤖 어시스턴트 {i}: {content}")
            else:
                st.warning(f"❓ 알 수 없음 {i}: {content}")


def feedback_stats_interface():
    """피드백 통계 인터페이스"""
    st.header("📊 피드백 통계")
    from core.feedback import get_feedback_stats
    stats = get_feedback_stats()
    if stats["total"] > 0:
        col1, col2, col3 = st.columns(3)
        col1.metric("전체", stats["total"])
        col2.metric("👍 긍정", stats["positive"])
        col3.metric("👎 부정", stats["negative"])
        ratio = stats["positive"] / stats["total"] * 100
        st.progress(ratio / 100, text=f"긍정률: {ratio:.0f}%")
    else:
        st.info("아직 수집된 피드백이 없습니다.")


if __name__ == "__main__":
    main() 
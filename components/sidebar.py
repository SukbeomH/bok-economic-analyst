"""
사이드바 컴포넌트 모듈
Streamlit 네이티브 컴포넌트 우선 사용으로 안정적이고 일관된 UI 제공
"""
import os
import glob
import time
import streamlit as st
from core.config import Config
from core.logger import logger
from core.state_manager import StateManager


def export_conversation():
    """대화를 파일로 내보냅니다."""
    messages = StateManager.get_messages()
    if len(messages) > 1:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"대화내역_{timestamp}.txt"
        
        export_content = f"AI 한국은행 경제 분석팀 - 대화 내역\n"
        export_content += f"생성일시: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        export_content += f"웹검색 활성화: {'예' if StateManager.get_web_search_enabled() else '아니오'}\n"
        export_content += "=" * 50 + "\n\n"
        
        for msg in messages:
            role = "사용자" if msg["role"] == "user" else "AI 분석팀"
            export_content += f"[{role}]\n{msg['content']}\n\n"
        
        st.download_button(
            label="📥 다운로드",
            data=export_content,
            file_name=filename,
            mime="text/plain",
            help="현재 대화를 텍스트 파일로 다운로드합니다"
        )
    else:
        st.warning("내보낼 대화가 없습니다.")


def render_sidebar():
    """사이드바를 렌더링합니다."""
    with st.sidebar:
        # 컨트롤 패널 (최상단, 펼친 상태)
        st.header("🎛️ 컨트롤 패널")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 초기화", help="현재 대화를 모두 지웁니다", type="secondary", use_container_width=True):
                StateManager.clear_messages()
                logger.clear_logs()
                st.rerun()
            
            # 로그 표시 토글
            log_button_text = "📊 로그 끄기" if StateManager.get_show_logs() else "📊 로그 켜기"
            log_button_type = "primary" if StateManager.get_show_logs() else "secondary"
            if st.button(log_button_text, help="실시간 분석 로그를 표시합니다", type=log_button_type, use_container_width=True):
                StateManager.toggle_show_logs()
                st.rerun()
        
        with col2:
            # 대화 내보내기 버튼
            if st.button("📥 내보내기", help="현재 대화를 파일로 내보냅니다", type="secondary", use_container_width=True):
                export_conversation()
            
            # 웹검색 토글
            web_search_enabled = st.toggle("\n🌐 웹검색", value=StateManager.get_web_search_enabled(), help="웹에서 최신 정보를 검색합니다")
            StateManager.set_web_search_enabled(web_search_enabled)
        
        # 그래프 재구성 버튼 (컨트롤 패널에 추가)
        def _rebuild_graph():
            StateManager.clear_agent_graph()
            st.cache_resource.clear()
            st.rerun()
        
        if st.button("🔄 그래프 재구성", help="에이전트 그래프를 재구성합니다", use_container_width=True):
            _rebuild_graph()
        
        st.divider()
        
        # 파일 업로드 영역
        st.header("📁 파일 업로드")
        uploaded_files = st.file_uploader(
            "분석에 참고할 PDF 파일을 업로드하세요.",
            type="pdf",
            accept_multiple_files=True,
            help="여러 PDF 파일을 선택하여 업로드할 수 있습니다.",
            key=f"uploader_{StateManager.get_uploader_key()}"
        )
        
        if uploaded_files:
            file_added = False
            for uploaded_file in uploaded_files:
                file_path = os.path.join(Config.DATA_DIR, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                file_added = True
            if file_added:
                st.success(f"✅ {len(uploaded_files)}개의 파일이 추가되었습니다.")
                st.info("RAG 파이프라인이 자동으로 업데이트됩니다.")
                # 업로더 위젯 상태를 초기화하기 위해 키를 변경 후 재실행
                StateManager.increment_uploader_key()
                st.cache_resource.clear()
                st.rerun()
        
        st.divider()
        
        # 현재 참고 자료 표시 (접힘 기능 없이, 스크롤 가능)
        st.header("📚 현재 참고 자료")
        pdf_files_in_data = glob.glob(os.path.join(Config.DATA_DIR, "*.pdf"))
        if pdf_files_in_data:
            with st.container():
                st.write(f"**총 {len(pdf_files_in_data)}개 파일:**")
                for f_path in pdf_files_in_data:
                    fname = os.path.basename(f_path)
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"• {fname}")
                    with col2:
                        if st.button("📖", key=f"sidebar_pdf_{fname}", help=f"{fname} 미리보기"):
                            from components.common import render_pdf_page
                            render_pdf_page(fname)
        else:
            st.info("업로드된 파일이 없습니다. 분석할 PDF를 먼저 추가하세요.")
        
        st.divider()
        
        # 간소화된 사용 팁
        st.caption("💡 **팁**: 파일 업로드 후 바로 질문하시면 됩니다.")
        
        return uploaded_files

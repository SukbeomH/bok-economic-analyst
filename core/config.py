"""
애플리케이션 설정 관리 모듈
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class Config:
    """애플리케이션 설정을 관리하는 클래스"""
    
    # 환경 변수 로드
    load_dotenv()
    
    # ==============================================================================
    # Azure OpenAI 설정
    # ==============================================================================
    AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-02-01")
    AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT")
    AOAI_API_KEY = os.getenv("AOAI_API_KEY")
    AOAI_DEPLOY_GPT4O = os.getenv("AOAI_DEPLOY_GPT4O", "gpt-4o")
    AOAI_DEPLOY_GPT4O_MINI = os.getenv("AOAI_DEPLOY_GPT4O_MINI", "gpt-4o-mini")
    AOAI_DEPLOY_EMBED_3_LARGE = os.getenv("AOAI_DEPLOY_EMBED_3_LARGE", "text-embedding-3-large")
    AOAI_DEPLOY_EMBED_3_SMALL = os.getenv("AOAI_DEPLOY_EMBED_3_SMALL", "text-embedding-3-small")
    AOAI_DEPLOY_EMBED_ADA = os.getenv("AOAI_DEPLOY_EMBED_ADA", "text-embedding-ada-002")
    
    # ==============================================================================
    # 애플리케이션 설정
    # ==============================================================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    DATA_DIR = os.getenv("DATA_DIR", "data")
    APP_GRAPH_VERSION = os.getenv("APP_GRAPH_VERSION", "4")
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "300"))
    MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))
    
    # ==============================================================================
    # RAG 설정
    # ==============================================================================
    RAG_SEARCH_STRATEGY = os.getenv("RAG_SEARCH_STRATEGY", "mmr")
    RAG_K = int(os.getenv("RAG_K", "5"))
    RAG_FETCH_K = int(os.getenv("RAG_FETCH_K", "20"))
    RAG_LAMBDA_MULT = float(os.getenv("RAG_LAMBDA_MULT", "0.7"))
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.7"))
    RAG_USE_COMPRESSION = os.getenv("RAG_USE_COMPRESSION", "false").lower() == "true"
    
    # ==============================================================================
    # KOSIS (통계청) 설정
    # ==============================================================================
    KOSIS_API_KEY = os.getenv("KOSIS_API_KEY", "")

    # ==============================================================================
    # 웹 검색 설정
    # ==============================================================================
    # 웹 검색 기능은 기본 검색 엔진을 사용합니다.
    
    # ==============================================================================
    # 개발/디버깅 설정
    # ==============================================================================
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
    USE_CACHE = os.getenv("USE_CACHE", "true").lower() == "true"
    CACHE_EXPIRY = int(os.getenv("CACHE_EXPIRY", "3600"))
    
    # ==============================================================================
    # 출력 형식
    # ==============================================================================
    CITATION_FORMAT = "📄 {source} (p.{page}) - 신뢰도: {confidence}%"
    RESEARCHER_OUTPUT_FORMAT = """
분석 요청: {query}

수집된 정보:
{content}

출처 정보:
{source_info}

신뢰도 평가: {reliability_score}/10
"""
    ANALYST_OUTPUT_FORMAT = """
분석 결과:
{analysis}

근거 및 출처:
{evidence}

결론:
{conclusion}
"""
    
    @classmethod
    def validate_required_settings(cls) -> Dict[str, str]:
        """필수 설정을 검증하고 누락된 항목을 반환합니다."""
        missing_settings = {}
        
        # Azure OpenAI 필수 설정
        if not cls.AOAI_ENDPOINT:
            missing_settings["AOAI_ENDPOINT"] = "Azure OpenAI 엔드포인트가 필요합니다."
        if not cls.AOAI_API_KEY:
            missing_settings["AOAI_API_KEY"] = "Azure OpenAI API 키가 필요합니다."
        if not cls.AOAI_DEPLOY_GPT4O:
            missing_settings["AOAI_DEPLOY_GPT4O"] = "GPT-4o 모델 배포명이 필요합니다."
        if not cls.AOAI_DEPLOY_EMBED_3_LARGE:
            missing_settings["AOAI_DEPLOY_EMBED_3_LARGE"] = "임베딩 모델 배포명이 필요합니다."
        
        return missing_settings
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """모든 설정을 딕셔너리로 반환"""
        return {
            # Azure OpenAI 설정
            "azure_api_version": cls.AZURE_API_VERSION,
            "aoai_endpoint": cls.AOAI_ENDPOINT,
            "aoai_deploy_gpt4o": cls.AOAI_DEPLOY_GPT4O,
            "aoai_deploy_gpt4o_mini": cls.AOAI_DEPLOY_GPT4O_MINI,
            "aoai_deploy_embed_3_large": cls.AOAI_DEPLOY_EMBED_3_LARGE,
            "aoai_deploy_embed_3_small": cls.AOAI_DEPLOY_EMBED_3_SMALL,
            "aoai_deploy_embed_ada": cls.AOAI_DEPLOY_EMBED_ADA,
            
            # 애플리케이션 설정
            "log_level": cls.LOG_LEVEL,
            "data_dir": cls.DATA_DIR,
            "app_graph_version": cls.APP_GRAPH_VERSION,
            "max_iterations": cls.MAX_ITERATIONS,
            "timeout_seconds": cls.TIMEOUT_SECONDS,
            
            # RAG 설정
            "rag_search_strategy": cls.RAG_SEARCH_STRATEGY,
            "rag_k": cls.RAG_K,
            "rag_fetch_k": cls.RAG_FETCH_K,
            "rag_lambda_mult": cls.RAG_LAMBDA_MULT,
            "rag_score_threshold": cls.RAG_SCORE_THRESHOLD,
            "rag_use_compression": cls.RAG_USE_COMPRESSION,
            
            # 웹 검색 설정
            "web_search": "기본 검색 엔진 사용",
            
            # 개발/디버깅 설정
            "debug_mode": cls.DEBUG_MODE,
            "use_cache": cls.USE_CACHE,
            "cache_expiry": cls.CACHE_EXPIRY,
        }
    
    @classmethod
    def get_environment_info(cls) -> Dict[str, Any]:
        """환경 정보를 반환합니다."""
        return {
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.sys.platform,
            "env_file_exists": os.path.exists(".env"),
            "env_example_exists": os.path.exists("env.example"),
            "data_dir_exists": os.path.exists(cls.DATA_DIR),
            "required_settings_valid": len(cls.validate_required_settings()) == 0,
        }
    
    @classmethod
    def print_config_summary(cls):
        """설정 요약을 출력합니다."""
        print("=" * 60)
        print("🔧 AI 한국은행 경제 분석팀 - 설정 요약")
        print("=" * 60)
        
        # 필수 설정 검증
        missing = cls.validate_required_settings()
        if missing:
            print("❌ 필수 설정 누락:")
            for key, message in missing.items():
                print(f"   - {key}: {message}")
            print()
        else:
            print("✅ 모든 필수 설정이 완료되었습니다.")
            print()
        
        # 주요 설정 표시
        settings = cls.get_all_settings()
        print("📋 주요 설정:")
        print(f"   - Azure API 버전: {settings['azure_api_version']}")
        print(f"   - 로그 레벨: {settings['log_level']}")
        print(f"   - 데이터 디렉토리: {settings['data_dir']}")
        print(f"   - RAG 검색 전략: {settings['rag_search_strategy']}")
        print(f"   - 웹검색: {settings['web_search']}")
        print(f"   - 디버그 모드: {settings['debug_mode']}")
        print()
        
        # 환경 정보
        env_info = cls.get_environment_info()
        print("🌍 환경 정보:")
        print(f"   - Python 버전: {env_info['python_version']}")
        print(f"   - 플랫폼: {env_info['platform']}")
        print(f"   - .env 파일: {'존재' if env_info['env_file_exists'] else '없음'}")
        print(f"   - 데이터 디렉토리: {'존재' if env_info['data_dir_exists'] else '없음'}")
        print("=" * 60)

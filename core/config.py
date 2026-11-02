"""
애플리케이션 설정 관리 모듈
"""
import os
import hashlib
import json
from urllib.parse import urlsplit
from typing import Dict, Any, Optional
from dotenv import load_dotenv


class Config:
    """애플리케이션 설정을 관리하는 클래스"""
    
    # 환경 변수 로드
    load_dotenv()
    
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip()
    EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "").strip()
    EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "").strip()
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "").strip()

    # ==============================================================================
    # 애플리케이션 설정
    # ==============================================================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    DATA_DIR = os.getenv("DATA_DIR", "data")
    APP_GRAPH_VERSION = os.getenv("APP_GRAPH_VERSION", "5")
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
        """Validate each provider's model, key, and endpoint without exposing secrets."""
        errors = {}
        for prefix, providers in (("LLM", ("openai", "claude", "openai_compatible")),
                                  ("EMBEDDING", ("openai", "openai_compatible"))):
            provider = getattr(cls, f"{prefix}_PROVIDER")
            if provider not in providers:
                errors[f"{prefix}_PROVIDER"] = f"{prefix}_PROVIDER는 {', '.join(providers)} 중 하나여야 합니다."
            for field in ("MODEL", "API_KEY"):
                name = f"{prefix}_{field}"
                if not getattr(cls, name):
                    errors[name] = f"{name} 설정이 필요합니다."
            url = getattr(cls, f"{prefix}_BASE_URL")
            if provider == "openai_compatible" and not url:
                errors[f"{prefix}_BASE_URL"] = f"{prefix}_BASE_URL 설정이 필요합니다."
            if url:
                try:
                    parsed = urlsplit(url)
                    valid = parsed.scheme in ("http", "https") and bool(parsed.hostname)
                    valid = valid and not any(character.isspace() for character in url)
                    valid = valid and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
                    parsed.port
                except ValueError:
                    valid = False
                if not valid:
                    errors[f"{prefix}_BASE_URL"] = f"{prefix}_BASE_URL에는 인증정보 없는 HTTP(S) API 주소를 입력하세요."
        return errors

    @classmethod
    def chat_base_url(cls) -> str:
        """Return the explicit chat endpoint instead of SDK environment fallbacks."""
        return cls.LLM_BASE_URL or ("https://api.anthropic.com" if cls.LLM_PROVIDER == "claude"
                                    else "https://api.openai.com/v1")

    @classmethod
    def embedding_base_url(cls) -> str:
        """Return the embedding endpoint independently from chat."""
        return cls.EMBEDDING_BASE_URL or "https://api.openai.com/v1"

    @classmethod
    def embedding_signature(cls) -> str:
        """Identify an embedding space without persisting its API key."""
        settings = (cls.EMBEDDING_PROVIDER, cls.EMBEDDING_MODEL, cls.embedding_base_url().rstrip("/"))
        return hashlib.sha256(json.dumps(settings).encode()).hexdigest()

    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """모든 설정을 딕셔너리로 반환"""
        errors = cls.validate_required_settings()
        return {
            "llm_provider": cls.LLM_PROVIDER,
            "llm_model": cls.LLM_MODEL,
            "llm_base_url": "설정 오류" if "LLM_BASE_URL" in errors else cls.chat_base_url(),
            "llm_api_key_set": bool(cls.LLM_API_KEY),
            "embedding_provider": cls.EMBEDDING_PROVIDER,
            "embedding_model": cls.EMBEDDING_MODEL,
            "embedding_base_url": "설정 오류" if "EMBEDDING_BASE_URL" in errors else cls.embedding_base_url(),
            "embedding_api_key_set": bool(cls.EMBEDDING_API_KEY),

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
        print(f"   - 채팅 제공자: {settings['llm_provider']}")
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

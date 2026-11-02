"""
환경 변수 검증 유틸리티 모듈
"""
import os
import sys
from typing import Dict, List, Tuple
from core.config import Config


class EnvironmentValidator:
    """환경 변수 및 설정 검증을 위한 클래스"""
    
    @staticmethod
    def validate_all() -> Tuple[bool, Dict[str, List[str]]]:
        """모든 환경 변수와 설정을 검증합니다."""
        results = {
            "errors": [],
            "warnings": [],
            "info": []
        }
        
        # 필수 설정 검증
        missing_settings = Config.validate_required_settings()
        if missing_settings:
            for key, message in missing_settings.items():
                results["errors"].append(f"{key}: {message}")
        else:
            results["info"].append("✅ 모든 필수 설정이 완료되었습니다.")
        
        # 환경 파일 검증
        if not os.path.exists(".env"):
            results["warnings"].append(".env 파일이 없습니다. env.example을 참고하여 생성하세요.")
        
        if not os.path.exists("env.example"):
            results["warnings"].append("env.example 파일이 없습니다.")
        
        # 데이터 디렉토리 검증
        if not os.path.exists(Config.DATA_DIR):
            results["warnings"].append(f"데이터 디렉토리 '{Config.DATA_DIR}'가 없습니다.")
        
        # RAG 설정 검증
        if Config.RAG_K <= 0:
            results["errors"].append("RAG_K는 1 이상이어야 합니다.")
        
        if Config.RAG_FETCH_K <= 0:
            results["errors"].append("RAG_FETCH_K는 1 이상이어야 합니다.")
        
        if not 0.0 <= Config.RAG_LAMBDA_MULT <= 1.0:
            results["warnings"].append("RAG_LAMBDA_MULT는 0.0 ~ 1.0 사이여야 합니다.")
        
        if not 0.0 <= Config.RAG_SCORE_THRESHOLD <= 1.0:
            results["warnings"].append("RAG_SCORE_THRESHOLD는 0.0 ~ 1.0 사이여야 합니다.")
        
        # 타임아웃 설정 검증
        if Config.TIMEOUT_SECONDS <= 0:
            results["errors"].append("TIMEOUT_SECONDS는 1 이상이어야 합니다.")
        
        if Config.MAX_ITERATIONS <= 0:
            results["errors"].append("MAX_ITERATIONS는 1 이상이어야 합니다.")
        
        # 웹 검색 설정 검증
        # 웹 검색 기능은 기본 검색 엔진을 사용합니다.
        
        # 로그 레벨 검증
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if Config.LOG_LEVEL.upper() not in valid_log_levels:
            results["warnings"].append(f"로그 레벨 '{Config.LOG_LEVEL}'이 유효하지 않습니다. 유효한 값: {', '.join(valid_log_levels)}")
        
        # 성공 여부 판단
        is_valid = len(results["errors"]) == 0
        
        return is_valid, results
    
    @staticmethod
    def print_validation_report():
        """검증 결과를 출력합니다."""
        is_valid, results = EnvironmentValidator.validate_all()
        
        print("=" * 60)
        print("🔍 환경 변수 및 설정 검증 결과")
        print("=" * 60)
        
        if results["errors"]:
            print("❌ 오류:")
            for error in results["errors"]:
                print(f"   - {error}")
            print()
        
        if results["warnings"]:
            print("⚠️ 경고:")
            for warning in results["warnings"]:
                print(f"   - {warning}")
            print()
        
        if results["info"]:
            print("ℹ️ 정보:")
            for info in results["info"]:
                print(f"   - {info}")
            print()
        
        if is_valid:
            print("✅ 환경 설정이 유효합니다!")
        else:
            print("❌ 환경 설정에 문제가 있습니다. 위의 오류를 수정하세요.")
        
        print("=" * 60)
        
        return is_valid
    
    @staticmethod
    def create_env_file():
        """env.example을 기반으로 .env 파일을 생성합니다."""
        if os.path.exists("env.example"):
            try:
                with open("env.example", "r", encoding="utf-8") as f:
                    example_content = f.read()
                
                # 주석과 설명 제거
                env_content = ""
                for line in example_content.split("\n"):
                    if line.strip() and not line.strip().startswith("#") and "=" in line:
                        key = line.split("=")[0].strip()
                        if key:
                            env_content += f"{key}=\n"
                
                with open(".env", "w", encoding="utf-8") as f:
                    f.write(env_content)
                
                print("✅ .env 파일이 생성되었습니다.")
                print("📝 실제 값으로 수정하세요.")
                return True
            except Exception as e:
                print(f"❌ .env 파일 생성 실패: {e}")
                return False
        else:
            print("❌ env.example 파일이 없습니다.")
            return False
    
    @staticmethod
    def get_setup_instructions() -> str:
        """설정 가이드를 반환합니다."""
        return """
🔧 AI 한국은행 경제 분석팀 - 설정 가이드

1. 환경 변수 설정:
   - env.example 파일을 .env로 복사: cp env.example .env
   - .env 파일을 열고 실제 값으로 수정

2. 필수 설정:
   - LLM_PROVIDER: openai, claude, openai_compatible 중 선택
   - LLM_MODEL, LLM_API_KEY: 채팅 모델과 직접 설정한 키
   - EMBEDDING_PROVIDER: openai 또는 openai_compatible
   - EMBEDDING_MODEL, EMBEDDING_API_KEY: 임베딩 모델과 직접 설정한 키
   - 호환 API는 각 그룹의 BASE_URL도 지정

3. 선택 설정:
   - LOG_LEVEL: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - RAG_*: RAG 관련 설정들

4. 검증:
   - python -c "from utils.env_validator import EnvironmentValidator; EnvironmentValidator.print_validation_report()"

5. 실행:
   - streamlit run app.py
"""


def main():
    """메인 함수 - 검증 실행"""
    if len(sys.argv) > 1 and sys.argv[1] == "create":
        EnvironmentValidator.create_env_file()
    elif len(sys.argv) > 1 and sys.argv[1] == "help":
        print(EnvironmentValidator.get_setup_instructions())
    else:
        EnvironmentValidator.print_validation_report()


if __name__ == "__main__":
    main() 
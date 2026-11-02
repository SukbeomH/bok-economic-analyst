"""
유틸리티 함수 모듈
"""
import os
import re
from typing import Dict, List
from dotenv import load_dotenv
from core.logger import logger
from core.config import Config


def setup_environment():
    """환경 변수를 로드하고 필수 변수가 설정되었는지 확인합니다."""
    load_dotenv()
    logger.info("[env] .env 로드 완료, 필수 환경변수 검증 시작")
    missing = Config.validate_required_settings()
    if missing:
        raise ValueError("모델 설정 오류: " + "; ".join(missing.values()))
    logger.info("[env] 필수 환경변수 검증 완료")


def extract_source_info(content: str) -> Dict[str, str]:
    """텍스트에서 출처 정보를 추출합니다."""
    
    source_info = {
        "source_name": "알 수 없음",
        "page_info": "",
        "evidence_text": content[:200] + "..." if len(content) > 200 else content,
        "confidence_score": "중간"
    }
    
    # PDF 파일명 추출 시도
    if "PDF" in content or ".pdf" in content.lower():
        pdf_match = re.search(r'([^/\\]+\.pdf)', content, re.IGNORECASE)
        if pdf_match:
            source_info["source_name"] = pdf_match.group(1)
    
    # 페이지 정보 추출 시도
    page_match = re.search(r'페이지\s*(\d+)', content)
    if page_match:
        source_info["page_info"] = f"페이지 {page_match.group(1)}"
    
    # URL 추출 시도
    url_match = re.search(r'https?://[^\s]+', content)
    if url_match:
        source_info["source_name"] = url_match.group(0)
        source_info["page_info"] = "웹 페이지"
    
    return source_info


def format_citations(sources: List[Dict[str, str]]) -> str:
    """출처 목록을 포맷팅된 인용 문자열로 변환합니다."""
    if not sources:
        return "출처 정보 없음"
    
    citations = []
    for i, source in enumerate(sources, 1):
        citation = f"📄 {source.get('source_name', '알 수 없음')} (p.{source.get('page_info', '')}) - 신뢰도: {source.get('confidence_score', '중간')}%"
        citations.append(f"{i}. {citation.strip()}")
    
    return "\n".join(citations)


def evaluate_evidence_quality(content: str, sources: List[Dict[str, str]]) -> Dict[str, int]:
    """근거의 품질을 평가합니다."""
    quality_score = 5  # 기본값
    reliability_score = 5
    recency_score = 5
    
    # 출처 수에 따른 품질 점수 조정
    if len(sources) >= 3:
        quality_score += 2
    elif len(sources) >= 1:
        quality_score += 1
    
    # 내용 길이에 따른 품질 점수 조정
    if len(content) > 500:
        quality_score += 1
    
    # 출처 신뢰성 평가
    for source in sources:
        source_name = source.get("source_name", "").lower()
        if "한국은행" in source_name or "bok" in source_name:
            reliability_score += 2
        elif "gov" in source_name or "정부" in source_name:
            reliability_score += 1
    
    # 점수 범위 제한
    quality_score = min(10, max(1, quality_score))
    reliability_score = min(10, max(1, reliability_score))
    recency_score = min(10, max(1, recency_score))
    
    return {
        "quality_score": quality_score,
        "reliability_score": reliability_score,
        "recency_score": recency_score
    }


def extract_preview_sources(content: str) -> List[Dict[str, str]]:
    """응답 내용에서 출처 정보를 구조화하여 추출한다."""
    sources = []

    # [문서 N] filename.pdf (p.X) 패턴 매칭
    doc_pattern = r'\[문서\s*\d+\]\s*([^\n(]+?)(?:\s*\(p\.(\d+)\))?\s*\n'
    for match in re.finditer(doc_pattern, content):
        source_name = match.group(1).strip()
        page = match.group(2)
        sources.append({
            "type": "pdf",
            "name": source_name,
            "page": page,
        })

    # URL 패턴 매칭
    url_pattern = r'URL:\s*(https?://[^\s]+)'
    for match in re.finditer(url_pattern, content):
        sources.append({
            "type": "web",
            "name": match.group(1),
            "page": None,
        })

    # 기존 출처 패턴 폴백
    if not sources:
        fallback_patterns = [
            r'출처:\s*\[([^\]]+)\]\s*([^\n]+)',
            r'근거:\s*([^\n]+)',
        ]
        for pattern in fallback_patterns:
            for match in re.findall(pattern, content, re.IGNORECASE):
                text = ' '.join(match).strip() if isinstance(match, tuple) else match.strip()
                if text and len(text) > 10:
                    sources.append({"type": "text", "name": text[:100], "page": None})

    # 중복 제거
    seen = set()
    unique = []
    for s in sources:
        key = (s["name"], s.get("page"))
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique[:5]
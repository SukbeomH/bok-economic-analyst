"""
RAG (Retrieval-Augmented Generation) 파이프라인 모듈
"""
import os
from pathlib import Path
import streamlit as st
from typing import Optional
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from bok_documents import load_pdf_pages
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from core.config import Config
from core.logger import logger
from core.model_factory import AzureModelFactory


class RAGPipeline:
    """RAG (Retrieval-Augmented Generation) 파이프라인을 관리하는 클래스"""
    
    def __init__(self, model_factory: AzureModelFactory):
        self.model_factory = model_factory
        self.vectorstore = None
        self.retriever = None
        self.index_path = "faiss_index"
        self.invalidation_file = "invalidation.txt"
    
    def save_faiss_index(self, vectorstore, index_path: str) -> bool:
        """FAISS 인덱스를 파일로 저장합니다."""
        try:
            vectorstore.save_local(index_path)
            logger.info("[rag] FAISS 인덱스 저장 완료: %s", index_path)
            return True
        except Exception as e:
            logger.exception("[rag] FAISS 인덱스 저장 실패: %s", e)
            return False

    def load_faiss_index(self, index_path: str, embeddings) -> Optional[FAISS]:
        """저장된 FAISS 인덱스를 로드합니다."""
        try:
            if os.path.exists(index_path):
                vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
                logger.info("[rag] FAISS 인덱스 로드 완료: %s", index_path)
                return vectorstore
            else:
                logger.warning("[rag] FAISS 인덱스 파일이 존재하지 않음: %s", index_path)
                return None
        except Exception as e:
            logger.exception("[rag] FAISS 인덱스 로드 실패: %s", e)
            return None

    def create_mmr_retriever(self, vectorstore, k=5, fetch_k=20, lambda_mult=0.7):
        """MMR (Maximum Marginal Relevance) 검색을 사용하는 리트리버를 생성합니다."""
        return vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": k,
                "fetch_k": fetch_k,
                "lambda_mult": lambda_mult
            }
        )

    def create_similarity_retriever(self, vectorstore, k=5, score_threshold=0.7):
        """유사도 기반 검색을 사용하는 리트리버를 생성합니다."""
        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": k,
                "score_threshold": score_threshold
            }
        )
    
    def create_relaxed_similarity_retriever(self, vectorstore, k=10, score_threshold=0.3):
        """완화된 유사도 기반 검색을 사용하는 리트리버를 생성합니다."""
        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": k,
                "score_threshold": score_threshold
            }
        )

    def create_compressed_retriever(self, base_retriever, llm):
        """컨텍스트 압축을 사용하는 리트리버를 생성합니다."""
        try:
            compressor = LLMChainExtractor.from_llm(llm)
            compressed_retriever = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=base_retriever
            )
            logger.info("[rag] ContextualCompressionRetriever 생성 완료")
            return compressed_retriever
        except Exception as e:
            logger.warning("[rag] ContextualCompressionRetriever 생성 실패, 기본 리트리버 사용: %s", e)
            return base_retriever
    
    def build_pipeline(self, cache_key: str):
        """
        'data' 폴더 내의 모든 PDF를 동적으로 로드하여 RAG 파이프라인을 구축합니다.
        FAISS 인덱스 영속화, MMR 검색, 컨텍스트 압축을 포함합니다.
        """
        logger.info("[rag] 파이프라인 빌드 시작 (cache_key=%s)", cache_key)
        
        # FAISS 인덱스 저장 경로
        index_path = os.path.join(Config.DATA_DIR, "faiss_index")
        
        data_dir = Path(Config.DATA_DIR)
        if not data_dir.is_dir():
            raise ValueError("PDF 문서 폴더가 없습니다.")
        pdf_files = sorted(path for path in data_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
        if not pdf_files:
            raise ValueError("PDF 문서가 없습니다. 분석할 PDF를 먼저 추가하세요.")
        embeddings = self.model_factory.get_embedding_model()
        current_pdf_mtime = max([os.path.getmtime(f) for f in pdf_files]) if pdf_files else 0
        
        # 인덱스 무효화 파일 확인
        invalidation_file = os.path.join(index_path, "invalidation.txt")
        index_needs_rebuild = True
        
        if os.path.exists(invalidation_file):
            try:
                with open(invalidation_file, 'r') as f:
                    stored_mtime = float(f.read().strip())
                if stored_mtime >= current_pdf_mtime:
                    index_needs_rebuild = False
                    logger.info("[rag] PDF 파일 변경 없음, 기존 인덱스 사용 가능")
            except Exception as e:
                logger.warning("[rag] 무효화 파일 읽기 실패: %s", e)
        
        # 저장된 인덱스 로드 시도
        vectorstore = None
        if not index_needs_rebuild:
            vectorstore = self.load_faiss_index(index_path, embeddings)
        
        if vectorstore is None:
            # 새로 빌드
            vectorstore = self._build_new_index(pdf_files, embeddings, index_path, current_pdf_mtime, invalidation_file)
        else:
            logger.info("[rag] 기존 FAISS 인덱스 사용")

        # LLM 초기화
        llm = self.model_factory.get_chat_model()
        
        # 검색 전략 선택
        if Config.RAG_SEARCH_STRATEGY == "mmr":
            base_retriever = self.create_mmr_retriever(
                vectorstore, 
                k=Config.RAG_K, 
                fetch_k=Config.RAG_FETCH_K, 
                lambda_mult=Config.RAG_LAMBDA_MULT
            )
        elif Config.RAG_SEARCH_STRATEGY == "similarity":
            base_retriever = self.create_similarity_retriever(
                vectorstore, 
                k=Config.RAG_K, 
                score_threshold=Config.RAG_SCORE_THRESHOLD
            )
        else:
            base_retriever = vectorstore.as_retriever(search_kwargs={"k": Config.RAG_K})
        
        # 컨텍스트 압축 적용
        if Config.RAG_USE_COMPRESSION:
            retriever = self.create_compressed_retriever(base_retriever, llm)
        else:
            retriever = base_retriever
        
        self.vectorstore = vectorstore
        self.retriever = retriever
        
        logger.info("[rag] 파이프라인 빌드 완료")
        return retriever
    
    def create_relaxed_retriever(self):
        """완화된 검색 조건으로 리트리버를 생성합니다."""
        if self.vectorstore is None:
            logger.error("[rag] 벡터스토어가 초기화되지 않음")
            return None
        
        llm = self.model_factory.get_chat_model()
        
        # 완화된 검색 전략
        if Config.RAG_SEARCH_STRATEGY == "mmr":
            base_retriever = self.create_mmr_retriever(
                self.vectorstore, 
                k=Config.RAG_K * 2,  # 더 많은 결과
                fetch_k=Config.RAG_FETCH_K * 2, 
                lambda_mult=0.5  # 더 낮은 다양성
            )
        elif Config.RAG_SEARCH_STRATEGY == "similarity":
            base_retriever = self.create_relaxed_similarity_retriever(
                self.vectorstore, 
                k=Config.RAG_K * 2,  # 더 많은 결과
                score_threshold=0.3  # 더 낮은 임계값
            )
        else:
            base_retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": Config.RAG_K * 2}
            )
        
        # 컨텍스트 압축 적용
        if Config.RAG_USE_COMPRESSION:
            retriever = self.create_compressed_retriever(base_retriever, llm)
        else:
            retriever = base_retriever
        
        logger.info("[rag] 완화된 리트리버 생성 완료")
        return retriever
    
    def _build_new_index(self, pdf_files, embeddings, index_path, current_pdf_mtime, invalidation_file):
        """새로운 FAISS 인덱스를 빌드합니다."""
        logger.info("[rag] 새 인덱스 빌드 시작")
        logger.info("[rag] PDF 파일 수: %d", len(pdf_files))
        
        all_docs = [
            Document(page_content=page.text, metadata={
                "source": str(Path(Config.DATA_DIR) / page.source),
                "source_filename": page.source,
                "page": page.page - 1,
                "page_number": page.page,
            })
            for page in load_pdf_pages(Path(Config.DATA_DIR))
        ]

        if not all_docs:
            logger.error("[rag] 문서 로드 실패: all_docs=0")
            raise ValueError("RAG를 위한 문서를 로드할 수 없습니다.")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        split_docs = text_splitter.split_documents(all_docs)
        if not split_docs:
            raise ValueError("PDF에서 검색할 텍스트를 찾지 못했습니다.")
        logger.info("[rag] 텍스트 분할 완료: chunks=%d", len(split_docs))

        vectorstore = FAISS.from_documents(documents=split_docs, embedding=embeddings)
        logger.info("[rag] FAISS 벡터스토어 생성 완료")
        
        # 인덱스 저장
        if self.save_faiss_index(vectorstore, index_path):
            # 무효화 파일 저장
            try:
                os.makedirs(index_path, exist_ok=True)
                with open(invalidation_file, 'w') as f:
                    f.write(str(current_pdf_mtime))
                logger.info("[rag] 무효화 파일 저장 완료: %s", current_pdf_mtime)
            except Exception as e:
                logger.warning("[rag] 무효화 파일 저장 실패: %s", e)
        
        return vectorstore


# 전역 RAG 파이프라인 인스턴스 (나중에 초기화)
rag_pipeline = None


@st.cache_resource
def build_rag_pipeline(cache_key: str):
    """
    RAG 파이프라인을 구축합니다. 클래스 기반 구조로 변경되었습니다.
    """
    global rag_pipeline
    if rag_pipeline is None:
        model_factory = AzureModelFactory()
        rag_pipeline = RAGPipeline(model_factory)
    
    return rag_pipeline.build_pipeline(cache_key)

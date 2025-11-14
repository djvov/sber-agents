import json
import logging
from pathlib import Path
from typing import Dict, Tuple

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import config

logger = logging.getLogger(__name__)

def load_pdf_documents(data_dir: str) -> list:
    """Загрузка всех PDF документов из директории"""
    pages = []
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.warning(f"Directory {data_dir} does not exist")
        return pages
    
    pdf_files = list(data_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files in {data_dir}")
    
    for pdf_file in pdf_files:
        loader = PyPDFLoader(str(pdf_file))
        pages.extend(loader.load())
        logger.info(f"Loaded {pdf_file.name}")
    
    return pages

def split_documents(pages: list) -> list:
    """Разбиение документов на чанки"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=150
    )
    chunks = text_splitter.split_documents(pages)
    logger.info(f"Split into {len(chunks)} chunks")
    return chunks

def create_vector_store(chunks: list):
    """Создание векторного хранилища"""
    embeddings = OllamaEmbeddings(
        model=config.EMBEDDING_MODEL
    )
    vector_store = InMemoryVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings
    )
    logger.info(f"Created vector store with {len(chunks)} chunks")
    return vector_store

def _normalize_question(question: str) -> str:
    """Нормализация вопроса для лексического поиска"""
    return question.strip().lower()

async def reindex_all() -> Tuple[InMemoryVectorStore | None, Dict[str, Document]]:
    """Полная переиндексация всех документов (PDF + JSON)

    Returns:
        tuple[vector_store, lexical_index]
    """
    logger.info("Starting full reindexing...")
    
    try:
        # 1. Загружаем и обрабатываем PDF документы
        pdf_pages = load_pdf_documents(config.DATA_DIR)
        if not pdf_pages:
            logger.warning("No PDF documents found to index")
        
        pdf_chunks = split_documents(pdf_pages) if pdf_pages else []
        
        # 2. Загружаем JSON с вопросами-ответами
        json_file = f"{config.DATA_DIR}/sberbank_help_documents.json"
        json_chunks = load_json_documents(json_file)
        lexical_index: Dict[str, Document] = {}
        for chunk in json_chunks:
            question = chunk.metadata.get("question")
            if not question:
                continue
            lexical_index[_normalize_question(question)] = chunk
        
        # 3. Объединяем все чанки
        all_chunks = pdf_chunks + json_chunks
        
        if not all_chunks:
            logger.warning("No documents found to index")
            return None, {}
        
        logger.info(f"Total chunks to index: {len(all_chunks)} (PDF: {len(pdf_chunks)}, JSON: {len(json_chunks)})")
            
        # 4. Создаём векторное хранилище
        vector_store = create_vector_store(all_chunks)
        logger.info("Reindexing completed successfully")
        return vector_store, lexical_index
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return None, {}
    except Exception as e:
        logger.error(f"Error during reindexing: {e}", exc_info=True)
        return None, {}

def load_json_documents(json_file_path: str) -> list:
    """
    Загрузка документов из JSON файла с вопросами-ответами
    Каждая пара Q&A становится отдельным чанком
    """
    json_path = Path(json_file_path)
    if not json_path.exists():
        logger.warning(f"JSON file {json_file_path} does not exist")
        return []

    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse JSON file {json_file_path}: {exc}")
        return []

    documents: list[Document] = []
    for item in data:
        full_text = item.get("full_text")
        if not full_text:
            continue

        metadata = {
            key: item.get(key)
            for key in ("url", "question", "answer", "category", "type")
            if item.get(key)
        }

        documents.append(Document(page_content=full_text, metadata=metadata))

    logger.info(f"Loaded {len(documents)} Q&A pairs from JSON")
    return documents
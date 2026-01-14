# Nepali Legal Intelligence System
It is a production-grade legal RAG (Retrieval-Augmented Generation) system designed to index and query over 300+ Acts from the Nepal Law Commission. It provides high-precision legal answers with citations down to the specific Khanda (clause) and Dapha (section) levels.

## Key Features
Hierarchical Parsing: Deep extraction logic that maintains the relationship between Act -> Part -> Chapter -> Section -> Clause.
Bilingual Support: Handles queries in both Nepali and English, retrieving context from native Nepali legal texts.
Production-Ready Scraper: Robust Playwright-based engine to automate data collection from the Law Commission portal.
Hybrid OCR/Digital Extraction: Intelligent detection of scanned vs. digital PDFs for optimal text recovery.

## System Architecture
The project is designed with a modular architecture to ensure scalability and maintainability.

1. Data Ingestion Layer
raw_pdf.py: Automated scraper for lawcommission.gov.np.
extract_text.py: Handles OCR and digital text extraction using pytesseract and pymupdf.
parse_to_json.py: Implements regex-based hierarchical structuring to convert raw text into a structured legal schema.

2. Storage & Retrieval Layer
db.py: Vector database configuration using ChromaDB.
ingestion.py: Orchestrates the movement of structured JSON data into the vector store.
retriever.py: Multilingual embedding search using paraphrase-multilingual-MiniLM-L12-v2.

3. Reasoning Layer (RAG)
generator.py: Core RAG logic using LangChain and Groq (Llama 3.1) to generate cited legal responses.
rag_controller.py: FastAPI endpoints for seamless integration with frontend interfaces.

## Tech Stack
* Language: Python 3.13 
* LLM Framework: LangChain / Groq
* Vector Database: ChromaDB
* Embeddings: HuggingFace Multilingual MiniLM
* API: FastAPI & Uvicorn
* Data Processing: Playwright (Scraping), Tesseract (OCR), PyMuPDF (Extraction)


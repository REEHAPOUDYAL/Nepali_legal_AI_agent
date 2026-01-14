import json
import os
import shutil  
from langchain_core.documents import Document
from store.db import get_chroma_connection 

DATA_PATH = r"C:\Users\poudy\Downloads\license_RAG\data\parsed_json\vidhi_rag_enhanced.json"
CHROMA_PATH = "chroma_storage"

def run_ingestion():
    if os.path.exists(CHROMA_PATH):
        print(f"Clearing existing database at {CHROMA_PATH}...")
        shutil.rmtree(CHROMA_PATH)

    if not os.path.exists(DATA_PATH):
        print(f"Error: JSON file not found at {DATA_PATH}")
        return

    print("Loading parsed legal data")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        legal_chunks = json.load(f)
    
    langchain_docs = []
    print(f"Preparing {len(legal_chunks)} chunks for vectorization...")
    
    for item in legal_chunks:
        page_content = item.get("content_with_context") or item.get("content") or "Empty Content"        
        raw_metadata = item.get("metadata", {})
        cleaned_metadata = {}

        for key, value in raw_metadata.items():
            if isinstance(value, list):
                cleaned_metadata[key] = ", ".join(map(str, value)) if value else ""
            elif value is None:
                cleaned_metadata[key] = ""
            else:
                cleaned_metadata[key] = value

        cleaned_metadata["chunk_id"] = item.get("chunk_id", "unknown")

        doc = Document(
            page_content=page_content,
            metadata=cleaned_metadata
        )
        langchain_docs.append(doc)

    print("Connecting to Vector Store and loading Local Embedding Model...")
    vector_store = get_chroma_connection()
    
    batch_size = 500 
    total_docs = len(langchain_docs)
    print(f"Starting ingestion of {total_docs} docs...")
    
    for i in range(0, total_docs, batch_size):
        batch = langchain_docs[i:i + batch_size]
        try:
            vector_store.add_documents(batch)
            percent = (min(i + batch_size, total_docs) / total_docs) * 100
            print(f"Progress: {percent:.2f}% | Indexed: {min(i + batch_size, total_docs)}/{total_docs}")
        except Exception as e:
            print(f"Error in batch starting at index {i}: {e}")

    print("\nIngestion complete. Vidhi-AI production database is ready.")

if __name__ == "__main__":
    run_ingestion()
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

def get_chroma_connection(collection_name: str = "vidhi_legal_acts"):
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={'device': 'cpu'} 
    )
    
    persist_directory = os.path.join(os.getcwd(), "chroma_storage")
    
    vector_db = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory
    )
    return vector_db
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
PERSIST_DIR = os.path.join(os.getcwd(), "chroma_storage")
COLLECTION_NAME = "vidhi_legal_acts"

def get_vector_store():
    embeddings = HuggingFaceEmbeddings(model_name=MODEL_NAME, model_kwargs={"device": "cpu"})
    vector_store = Chroma(collection_name=COLLECTION_NAME, embedding_function=embeddings, persist_directory=PERSIST_DIR)
    return vector_store

class Retriever:
    def __init__(self, top_k=5):
        self.vector_store = get_vector_store()
        self.top_k = top_k

    def retrieve(self, query):
        return self.vector_store.similarity_search(query, k=self.top_k)

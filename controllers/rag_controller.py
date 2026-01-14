from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from rag.generator import NepalLegalRAG
from dotenv import load_dotenv
import os

load_dotenv() 

router = APIRouter(prefix="/api/legal", tags=["Legal RAG"])
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable not set")

rag_instance = NepalLegalRAG(groq_api_key=GROQ_API_KEY)
class QuestionRequest(BaseModel):
    question: str = Field(..., description="Legal question in Nepali or English")
    act_name: Optional[str] = Field(None, description="Specific act name to filter results")
    top_k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "दफा ५ सम्बन्धी नियमहरू",
                "act_name": None,
                "top_k": 5
            }
        }

class DocumentMetadata(BaseModel):
    act_name: Optional[str] = None
    dapha_no: Optional[str] = None
    part: Optional[str] = None
    chapter: Optional[str] = None
    page_no: Optional[str] = None
    citation: Optional[str] = None

class RetrievedDocument(BaseModel):
    content: str
    metadata: DocumentMetadata

class AnswerResponse(BaseModel):
    question: str
    answer: str
    retrieved_documents: List[RetrievedDocument]
    total_documents: int

class RetrieveResponse(BaseModel):
    query: str
    documents: List[RetrievedDocument]
    total_documents: int

class ActsListResponse(BaseModel):
    acts: List[str]
    total: int

def cast_metadata_to_str(metadata: dict) -> DocumentMetadata:
    return DocumentMetadata(
        act_name=str(metadata.get("act_name")) if metadata.get("act_name") is not None else None,
        dapha_no=str(metadata.get("dapha_no")) if metadata.get("dapha_no") is not None else None,
        part=str(metadata.get("part")) if metadata.get("part") is not None else None,
        chapter=str(metadata.get("chapter")) if metadata.get("chapter") is not None else None,
        page_no=str(metadata.get("page_no")) if metadata.get("page_no") is not None else None,
        citation=str(metadata.get("citation")) if metadata.get("citation") is not None else None,
    )

@router.post("/ask", response_model=AnswerResponse)
async def ask_legal_question(request: QuestionRequest):
    try:
        if request.top_k != rag_instance.retriever.top_k:
            rag_instance.retriever.top_k = request.top_k
        
        retrieved_docs = rag_instance.retrieve_context(
            request.question,
            act_name=request.act_name
        )
        
        if not retrieved_docs:
            raise HTTPException(
                status_code=404,
                detail="No relevant legal documents found for your question"
            )
        
        context = rag_instance.format_context(retrieved_docs)
        answer_text = ""
        for chunk in rag_instance.chain.stream(
            {"context": context, "question": request.question}
        ):
            answer_text += chunk
        
        if "दफा" not in answer_text and "Section" not in answer_text:
            answer_text += "\n\n⚠️ Note: Insufficient legal context available in the retrieved documents."
        
        formatted_docs = [
            RetrievedDocument(
                content=doc["content"],
                metadata=cast_metadata_to_str(doc["metadata"])
            )
            for doc in retrieved_docs
        ]
        
        return AnswerResponse(
            question=request.question,
            answer=answer_text,
            retrieved_documents=formatted_docs,
            total_documents=len(formatted_docs)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating answer: {str(e)}")

@router.get("/retrieve", response_model=RetrieveResponse)
async def retrieve_documents(
    query: str = Query(..., description="Search query"),
    act_name: Optional[str] = Query(None, description="Filter by specific act"),
    top_k: int = Query(5, ge=1, le=20, description="Number of documents to retrieve")
):
    try:
        original_top_k = rag_instance.retriever.top_k
        rag_instance.retriever.top_k = top_k
        
        retrieved_docs = rag_instance.retrieve_context(query, act_name=act_name)
        rag_instance.retriever.top_k = original_top_k
        
        if not retrieved_docs:
            raise HTTPException(status_code=404, detail="No relevant documents found")
        
        formatted_docs = [
            RetrievedDocument(
                content=doc["content"],
                metadata=cast_metadata_to_str(doc["metadata"])
            )
            for doc in retrieved_docs
        ]
        
        return RetrieveResponse(
            query=query,
            documents=formatted_docs,
            total_documents=len(formatted_docs)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving documents: {str(e)}")

@router.get("/acts", response_model=ActsListResponse)
async def list_available_acts(query: Optional[str] = Query(None, description="Optional search query to find relevant acts")):
    try:
        if query:
            retrieved_docs = rag_instance.retrieve_context(query)
        else:
            retrieved_docs = rag_instance.retrieve_context("कानून")
        
        acts = sorted(set(
            doc["metadata"].get("act_name", "")
            for doc in retrieved_docs
            if doc["metadata"].get("act_name")
        ))
        
        return ActsListResponse(
            acts=acts,
            total=len(acts)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing acts: {str(e)}")

@router.get("/health")
async def health_check():
    try:
        test_docs = rag_instance.retrieve_context("test")
        return {
            "status": "healthy",
            "message": "Nepal Legal RAG system is operational",
            "retriever_active": True,
            "llm_active": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": str(e),
            "retriever_active": False,
            "llm_active": False
        }

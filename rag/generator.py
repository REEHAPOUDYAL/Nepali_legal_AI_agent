import os
from rag.retriever import Retriever
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from typing import List, Dict, Optional

class NepalLegalRAG:
    def __init__(self, groq_api_key: str, top_k: int = 5, temperature: float = 0.1):
        self.retriever = Retriever(top_k=top_k)
        self.llm = ChatGroq(
            model_name="llama-3.1-8b-instant",
            groq_api_key=groq_api_key,
            temperature=temperature,
            max_tokens=2048
        )
        self.prompt_template = self._create_prompt_template()
        self.chain = self.prompt_template | self.llm | StrOutputParser()
        
    def _create_prompt_template(self) -> PromptTemplate:
        template = """
You are Vidhi-AI, a professional Nepali legal intelligence system.

STRICT RULES:
1. Answer ONLY using the provided legal documents.
2. Every legal statement MUST have a citation:
   [Act Name, दफा X]
3. Do NOT guess or invent sections.
4. If the context is insufficient, say so clearly.
5. Do NOT provide general legal advice.

Context Documents:
{context}

Question:
{question}

Answer format:

Answer:
<precise legal explanation>

Citations:
- [Act Name, दफा X]
"""
        return PromptTemplate.from_template(template)

    def retrieve_context(
        self,
        query: str,
        act_name: Optional[str] = None
    ) -> List[Dict]:
        results = self.retriever.retrieve(query)
        
        docs = [
            {"content": d.page_content, "metadata": d.metadata}
            for d in results
        ]

        if act_name:
            docs = [d for d in docs if d["metadata"].get("act_name") == act_name]

        return docs
        
    def format_context(self, retrieved_docs: List[Dict]) -> str:
        blocks = []
        for i, doc in enumerate(retrieved_docs, 1):
            m = doc["metadata"]
            blocks.append(
                f"""
[DOCUMENT {i}]
Act: {m.get("act_name")}
Section (दफा): {m.get("dapha_no")}
Part: {m.get("part")}
Chapter: {m.get("chapter")}
Page: {m.get("page_no")}
Citation: {m.get("citation")}

Legal Text:
{doc["content"]}
"""
            )
        return "\n".join(blocks)

    def generate_answer(self, question: str):
        retrieved_docs = self.retrieve_context(question)

        if not retrieved_docs:
            print("Insufficient legal context available in the retrieved documents.")
            return

        if "दफा" in question or "Section" in question:
            acts = sorted({
                d["metadata"].get("act_name")
                for d in retrieved_docs
                if d["metadata"].get("act_name")
            })

            if len(acts) > 1:
                print("\nThe requested section exists in multiple Acts:\n")
                for idx, act in enumerate(acts, 1):
                    print(f"{idx}. {act}")

                selected = input(
                    "\nPlease specify the Act name (exact or number): "
                ).strip()

                if selected.isdigit():
                    index = int(selected) - 1
                    if 0 <= index < len(acts):
                        selected_act = acts[index]
                    else:
                        print("Invalid selection.")
                        return
                else:
                    selected_act = selected

                retrieved_docs = self.retrieve_context(
                    question,
                    act_name=selected_act
                )

                if not retrieved_docs:
                    print(f"No relevant sections found for Act: {selected_act}")
                    return

        context = self.format_context(retrieved_docs)
        answer_text = ""
        try:
            for chunk in self.chain.stream(
                {"context": context, "question": question}
            ):
                print(chunk, end="", flush=True)
                answer_text += chunk
        except Exception as e:
            print(f"\nError during generation: {e}")
            return

        if "दफा" not in answer_text and "Section" not in answer_text:
            print("\n Insufficient legal context available in the retrieved documents.")

if __name__ == "__main__":
    GROQ_API_KEY = "gsk_..." 
    
    rag = NepalLegalRAG(groq_api_key=GROQ_API_KEY)
    test_questions = [
        "दफा ५ सम्बन्धी नियमहरू",
        "Rules regarding Section 5",
    ]
    for q in test_questions:
        print(f"\nQuestion: {q}\n")
        rag.generate_answer(q)
import groq
import json
from backend.config import settings
from backend.models.schemas import RagRequest, RagResponse
from backend.rag.vector_store import VectorStore

class RagAgent:
    def __init__(self):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.vector_store = VectorStore()
        
        if self.vector_store.is_empty():
            self.vector_store.index_documents()

    def answer_question(self, request: RagRequest) -> RagResponse:
        retrieved_docs = self.vector_store.search(request.query)
        
        context_str = ""
        sources = set()
        debug_context = []
        
        for doc in retrieved_docs:
            source = doc["metadata"]["source"]
            chunk_idx = doc["metadata"].get("chunk_index", 0)
            symbol_name = doc["metadata"].get("symbol_name", "N/A")
            file_type = doc["metadata"].get("file_type", "text")
            
            sources.add(source)
            debug_context.append({
                "source": source,
                "chunk_index": chunk_idx,
                "symbol_name": symbol_name,
                "content": doc["content"]
            })
            
            context_str += f"\n--- File: {source} | Chunk: {chunk_idx} | Symbol: {symbol_name} | Type: {file_type} ---\n{doc['content']}\n"
            
        system_prompt = f"""You are the strictly grounded RAG Documentation Assistant for CodePilot.
Your ONLY job is to answer user questions using ONLY the explicitly provided text in the retrieved context.

CRITICAL RULES:
1. You may ONLY use facts explicitly present in the retrieved context.
2. DO NOT infer filenames, dependencies, implementations, or architecture from import statements unless the context explicitly describes them.
3. Every factual claim you make must be supported by the retrieved context.
4. Every source you list must be one of the explicitly retrieved files. DO NOT invent filenames.
5. If the retrieved context does not contain enough information to answer the question, you MUST return exactly this answer: "Not found in the retrieved context."

Here is the JSON schema you must adhere to:
{RagResponse.model_json_schema()}
"""
        
        try:
            completion = self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {request.query}"}
                ],
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            parsed = RagResponse.model_validate_json(content)
            
            # Ensure sources only contain actually retrieved sources
            valid_sources = []
            for s in parsed.sources:
                if s in sources:
                    valid_sources.append(s)
            
            parsed.sources = list(sources) # Force to exact retrieved sources
            parsed.retrieved_context = debug_context
            return parsed
            
        except Exception as e:
            raise RuntimeError(f"Failed to answer question from LLM: {str(e)}")

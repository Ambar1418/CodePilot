import os
import chromadb
from .document_loader import DocumentLoader

class VectorStore:
    def __init__(self, persist_directory: str = ".chroma", root_dir: str = "."):
        self.persist_directory = persist_directory
        self.root_dir = root_dir
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection_name = "codepilot_docs"
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def is_empty(self) -> bool:
        return self.collection.count() == 0

    def index_documents(self):
        print("Indexing documents...")
        loader = DocumentLoader(self.root_dir)
        all_chunks, all_metadatas, all_ids = loader.load_and_chunk_documents()
        
        if not all_chunks:
            print("No documents found.")
            return

        # Clear existing collection and recreate to avoid duplicate IDs
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(name=self.collection_name)

        # Batch add to chroma
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            self.collection.add(
                documents=all_chunks[i:i+batch_size],
                metadatas=all_metadatas[i:i+batch_size],
                ids=all_ids[i:i+batch_size]
            )
        print(f"Indexed {len(all_chunks)} chunks.")

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        # Semantic search
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        retrieved_ids = set()
        retrieved = []
        
        if results and results["documents"] and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            for doc, meta, doc_id in zip(docs, metas, ids):
                if doc_id not in retrieved_ids:
                    retrieved.append({
                        "content": doc,
                        "metadata": meta
                    })
                    retrieved_ids.add(doc_id)

        # Keyword matching for filenames
        all_docs = self.collection.get(include=["metadatas"])
        if all_docs and all_docs["metadatas"]:
            unique_sources = set()
            for meta in all_docs["metadatas"]:
                if meta and "source" in meta:
                    unique_sources.add(meta["source"])
            
            # Find sources mentioned in query or through common mappings
            matched_sources = []
            query_lower = query.lower()
            
            common_mappings = {
                "dependencies": "requirements.txt",
                "packages": "requirements.txt",
                "api routes": "backend/main.py",
                "endpoints": "backend/main.py",
                "vectorstore": "backend/rag/vector_store.py",
                "rag pipeline": "backend/rag/document_loader.py"
            }
            
            for source in unique_sources:
                if source in query:
                    matched_sources.append(source)
                    
            for term, mapped_source in common_mappings.items():
                if term in query_lower and mapped_source in unique_sources:
                    if mapped_source not in matched_sources:
                        matched_sources.append(mapped_source)
                    
            if matched_sources:
                # Fetch all chunks for matched sources
                keyword_results = self.collection.get(
                    where={"source": {"$in": matched_sources}},
                    include=["documents", "metadatas"]
                )
                
                if keyword_results and keyword_results["documents"]:
                    docs = keyword_results["documents"]
                    metas = keyword_results["metadatas"]
                    ids = keyword_results["ids"]
                    for doc, meta, doc_id in zip(docs, metas, ids):
                        if doc_id not in retrieved_ids:
                            retrieved.insert(0, {
                                "content": doc,
                                "metadata": meta
                            })
                            retrieved_ids.add(doc_id)
        
        return retrieved

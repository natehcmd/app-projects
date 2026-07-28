class LocalVectorDB:
    """
    A safe, local mock of a Vector Database for a RAG pipeline.
    Does not connect to external third-party DBs without explicit consent.
    """
    def __init__(self):
        self.documents = []

    def insert(self, text, embedding):
        self.documents.append({"text": text, "embedding": embedding})

    def search(self, query_embedding, top_k=3):
        # Mock search returning top_k results
        return self.documents[:top_k]

class SafeRAGPipeline:
    def __init__(self):
        self.db = LocalVectorDB()
        
    def generate_embedding(self, text):
        # Use a local embedding model here (e.g. HuggingFace sentence-transformers)
        # For demonstration, returns a mock vector.
        return [0.1, 0.2, 0.3]

    def add_document(self, text):
        vector = self.generate_embedding(text)
        self.db.insert(text, vector)
        print(f"Document added safely to local DB: {text[:20]}...")

    def query(self, user_prompt):
        vector = self.generate_embedding(user_prompt)
        results = self.db.search(vector)
        print(f"RAG retrieved {len(results)} contexts.")
        # Proceed to send to local LLM or approved API...
        return results

if __name__ == "__main__":
    rag = SafeRAGPipeline()
    rag.add_document("Safe local setup instructions.")
    rag.query("How to setup locally?")

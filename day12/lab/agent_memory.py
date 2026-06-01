"""
==============================================================================
SIGMA INTELLIGENCE PLATFORM — RAG MEMORY LAYER
==============================================================================
Shared ChromaDB memory used by ALL agents.

Each agent:
  1. RETRIEVES past similar incidents before acting (context for LLM)
  2. SAVES its findings after acting (improves future runs)

Collections:
  - schema_drift   : past schema drift incidents + remediation
  - pii_findings   : past PII column discoveries
  - quality_issues : past quality check results

This is RAG applied to operational intelligence — agents learn from history.

First run: no memory → generic LLM responses
Second run: memory has context → specific, historically-informed responses
That contrast IS the lesson.
==============================================================================
"""

import json, os
from datetime import datetime

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

MEMORY_DIR = os.getenv("PLATFORM_DIR",
             os.path.dirname(__file__)) + "/agent_memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

COLLECTIONS = ["schema_drift", "pii_findings", "quality_issues"]

class AgentMemory:
    """
    ChromaDB-backed persistent memory shared across all agents.
    Uses default embedding function (all-MiniLM-L6-v2 via sentence-transformers).
    """

    def __init__(self, persist_dir: str = MEMORY_DIR):
        self.available = CHROMADB_AVAILABLE
        if not self.available:
            print("[AgentMemory] WARNING: chromadb not installed. "
                  "Run: pip install chromadb sentence-transformers")
            return

        self.client = chromadb.PersistentClient(path=persist_dir)
        self.ef     = embedding_functions.DefaultEmbeddingFunction()
        self.cols   = {}
        for name in COLLECTIONS:
            self.cols[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.ef,
                metadata={"hnsw:space": "cosine"},
            )

    def save(self, collection: str, doc_id: str,
             content: str, metadata: dict = None) -> bool:
        """
        Save a document to memory.
        Uses upsert — safe to call multiple times with same doc_id.
        """
        if not self.available or collection not in self.cols:
            return False
        try:
            self.cols[collection].upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[{
                    **(metadata or {}),
                    "saved_at": datetime.now().isoformat(),
                }],
            )
            return True
        except Exception as e:
            print(f"[AgentMemory] Save failed: {e}")
            return False

    def retrieve(self, collection: str, query: str,
                 n_results: int = 3) -> list[str]:
        """
        Retrieve semantically similar past documents.
        Returns list of document strings for inclusion in LLM prompt.
        Returns empty list if memory is empty (first run).
        """
        if not self.available or collection not in self.cols:
            return []
        try:
            count = self.cols[collection].count()
            if count == 0:
                return []
            results = self.cols[collection].query(
                query_texts=[query],
                n_results=min(n_results, count),
            )
            return results["documents"][0] if results["documents"] else []
        except Exception as e:
            print(f"[AgentMemory] Retrieve failed: {e}")
            return []

    def count(self, collection: str) -> int:
        """Return number of documents in a collection."""
        if not self.available or collection not in self.cols:
            return 0
        return self.cols[collection].count()

    def summary(self) -> dict:
        """Return document counts per collection — for health check."""
        if not self.available:
            return {"status": "unavailable", "reason": "chromadb not installed"}
        return {
            "status": "ok",
            "persist_dir": MEMORY_DIR,
            "collections": {name: self.cols[name].count() for name in COLLECTIONS},
        }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing AgentMemory...")
    mem = AgentMemory()

    if not mem.available:
        print("ChromaDB not installed. pip install chromadb sentence-transformers")
        exit(1)

    # Save a test incident
    mem.save("schema_drift",
             "test_001",
             "Schema drift: merchant_name renamed to merchant_nm. "
             "Added upi_ref_id column. Fix: coalesce both column names in Silver transform.",
             {"risk": "medium"})

    mem.save("pii_findings",
             "test_001",
             "PII found: cust_ph (phone), acct_no (account). "
             "LLM detection was needed — regex missed abbreviated names. "
             "Masked before Silver load.",
             {"tier": "Confidential"})

    # Retrieve
    results = mem.retrieve("schema_drift", "column renamed merchant")
    print(f"\nSchema drift memory ({len(results)} results):")
    for r in results:
        print(f"  → {r}")

    results = mem.retrieve("pii_findings", "abbreviated PII column phone")
    print(f"\nPII memory ({len(results)} results):")
    for r in results:
        print(f"  → {r}")

    print(f"\nSummary: {mem.summary()}")
    print("\nAgentMemory test PASSED")

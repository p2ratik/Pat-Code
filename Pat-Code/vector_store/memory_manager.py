import faiss
import numpy as np
import sqlite3
import os
import json
from datetime import datetime
from config.loader import get_config_dir
from vector_store.embeddings import EmbeddingManager

STORAGE_PATH = get_config_dir()

class FaissMemoryStore:

    def __init__(self, vector_dim = 384, storage_path=STORAGE_PATH):
        self.vector_dim = vector_dim
        self.storage_path = storage_path

        self.index_path = os.path.join(storage_path, "memory.index")
        self.db_path = os.path.join(storage_path, "metadata.db")

        os.makedirs(storage_path, exist_ok=True)
        self.embedding_manager = EmbeddingManager()
        self._init_faiss()
        self._init_metadata_db()

    def _init_faiss(self):

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)

        else:
            base_index = faiss.IndexFlatL2(self.vector_dim)
            self.index = faiss.IndexIDMap(base_index)
            self._save_index()            
        
    def _init_metadata_db(self):

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            faiss_id INTEGER PRIMARY KEY,
            content TEXT,
            memory TEXT,
            timestamp TEXT,
            metadata TEXT
        )
        """)

        self.conn.commit()

    def _save_index(self):

        faiss.write_index(self.index, self.index_path)


    def add_memory(self, content : str , metadata : dict, memory:str = 'episodic'):


        metadata = metadata or {}
        faiss_id = int(datetime.utcnow().timestamp() * 1000)

        vector = np.array(self.embedding_manager.get_embeddings(content)).astype("float32")
        ids = np.array([faiss_id])

        vector = vector.reshape(1, -1).astype("float32")
        self.index.add_with_ids(vector, ids)      

        self.cursor.execute("""
        INSERT INTO memories (
            faiss_id,
            content,
            memory,
            timestamp,
            metadata
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            faiss_id,
            content,
            memory,
            datetime.utcnow().isoformat(),
            json.dumps(metadata)
        ))

        self.conn.commit()
        self._save_index()



    def search(self, query:str, top_k:int=5):

        vector = self.embedding_manager.get_embeddings(query).astype("float32")
        vector = vector.reshape(1, -1).astype("float32")

        distances, ids = self.index.search(vector, top_k)

        results = []

        for faiss_id in ids[0]:

            if faiss_id == -1:
                continue

            self.cursor.execute("""
            SELECT content, memory_type, metadata
            FROM memories
            WHERE faiss_id = ?
            """, (int(faiss_id),))

            row = self.cursor.fetchone()

            if row:

                results.append({
                    "faiss_id": int(faiss_id),
                    "content": row[0],
                    "memory_type": row[1],
                    "metadata": json.loads(row[2])
                })

        return results

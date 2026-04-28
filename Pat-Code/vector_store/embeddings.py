from fastembed import TextEmbedding
from typing import List

class EmbeddingManager():
    def __init__(self):
        self.model = TextEmbedding()

    def get_embeddings(self, content:str)->List:
        return list(self.model.embed([content]))[0]



from langchain_community.document_loaders import PyPDFium2Loader, Docx2txtLoader
import os
import tempfile
import re
import numpy as np

def pdf_loader(f_name: str, fi_bytes, *args):
    """Load PDF or DOCX files asynchronously"""
    
    temp_path = None
    
    suffix = os.path.splitext(f_name)[1] or '.pdf'
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(fi_bytes)
        fi = temp.name
    try:
        if f_name.endswith(".pdf"):
            print("#### The Document Loading has Started. ####")
            loader = PyPDFium2Loader(fi)
            docs = loader.load()
            text = docs[0].page_content if docs else None

        elif f_name.endswith((".docx", ".doc")):
            loader = Docx2txtLoader(fi)
            docs = loader.load()
            text = docs[0].page_content if docs else None
        else:
            return None

    except Exception as e:
        print(f"Error loading document: {e}")
        return None

    if text:
        # Clean up white-space
        text = re.sub(r"\n{2,}", "\n", text)
        text = re.sub(r"\t{2,}", "\t", text)
        return fi, text

    return None
    

#mock embedding

def embed(text: str, dim: int = 384) -> np.ndarray:
    import hashlib
    
    m = hashlib.sha256(text.encode('utf-8'))
    
    seed_int = int(m.hexdigest(), 16) % (2**32 -1)
    np.random.seed(seed_int)
    
    embedding = np.random.rand(dim)
    
    return embedding
    
#Qdrant client upsertion
from qdrant_client import QdrantClient, models

class Qdrant:
    
    
    def __init__(self, url, api_key, *args):
        self.client = QdrantClient(url = url, api_key = api_key)
        
    def upsert(self, embedding: np.ndarray, user_id: int, *args) -> bool:
        
        if not self.client.retrieve(collection_name = "test0", ids=[user_id]):
            upsert =self.client.upsert(collection_name = "test0", points=[models.PointStruct(id=user_id, payload={"user_id": user_id}, vector=embedding,),])
            return True
        else:
            return False
        

        

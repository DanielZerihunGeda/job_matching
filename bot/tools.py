from langchain_community.document_loaders import PyPDFium2Loader, Docx2txtLoader
import os
import tempfile
import re


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
        return text

    return None

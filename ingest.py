import os, pathlib
from llama_index.core import VectorStoreIndex, Settings, StorageContext, load_index_from_storage
from llama_index.readers.file import PDFReader
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

def build_or_load_index(docs_dir: str = "docs", storage_dir: str = "storage", model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> VectorStoreIndex:
    pathlib.Path(storage_dir).mkdir(parents=True, exist_ok=True)
    # try load
    try:
        storage_context = StorageContext.from_defaults(persist_dir=storage_dir)
        return load_index_from_storage(storage_context)
    except Exception:
        pass
    # build from PDFs
    reader = PDFReader()
    documents = []
    for p in pathlib.Path(docs_dir).glob("*.pdf"):
        documents.extend(reader.load_data(file=p))

    if not documents:
        raise RuntimeError("No PDFs found in 'docs/'. Add at least one SOP PDF.")

    Settings.embed_model = HuggingFaceEmbedding(model_name=model_name)
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=storage_dir)
    return index

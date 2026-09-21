import chromadb

from backend.rag import load_documents, chunk_documents_with_sources
from backend.embedding import create_embedding


# Create ChromaDB client
chroma_client = chromadb.PersistentClient(
    path="backend/chroma_db"
)


# Create or get collection
collection = chroma_client.get_or_create_collection(
    name="employees"
)


def build_vector_store():
    documents = load_documents()
    chunks = chunk_documents_with_sources(documents)

    # Delete old collection
    try:
        chroma_client.delete_collection(name="employees")
    except Exception:
        pass

    # Create a fresh collection
    global collection
    collection = chroma_client.get_or_create_collection(
        name="employees"
    )

    for index, chunk in enumerate(chunks):
        vector = create_embedding(chunk["text"])

        collection.upsert(
            ids=[f"chunk_{index}"],
            documents=[chunk["text"]],
            embeddings=[vector],
            metadatas=[
                {
                    "source": chunk["source"]
                }
            ]
        )

    print("VECTOR STORE BUILT SUCCESSFULLY")
    print("NUMBER OF DOCUMENTS:", len(documents))
    print("NUMBER OF CHUNKS:", len(chunks))
    print("NUMBER OF STORED CHUNKS:", collection.count())


if __name__ == "__main__":
    build_vector_store()
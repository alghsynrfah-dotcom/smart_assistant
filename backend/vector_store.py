import chromadb

from backend.rag import load_document, chunk_document
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
    document = load_document()
    chunks = chunk_document(document)

    for index, chunk in enumerate(chunks):
        vector = create_embedding(chunk)

        collection.upsert(
            ids=[f"chunk_{index}"],
            documents=[chunk],
            embeddings=[vector]
        )

    print("VECTOR STORE BUILT SUCCESSFULLY")
    print("NUMBER OF CHUNKS:", collection.count())


if __name__ == "__main__":
    build_vector_store()
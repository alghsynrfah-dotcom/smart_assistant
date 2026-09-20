from backend.vector_store import collection
from backend.embedding import create_embedding


def retrieve_documents(question, top_k=3):
    question_vector = create_embedding(question)

    results = collection.query(
        query_embeddings=[question_vector],
        n_results=top_k
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    retrieved_documents = []

    for document, metadata in zip(documents, metadatas):
        retrieved_documents.append({
            "text": document,
            "source": metadata["source"]
        })

    return retrieved_documents


if __name__ == "__main__":
    question = "DEPARTMENT COLLABORATION"

    documents = retrieve_documents(question)

    print("RETRIEVED DOCUMENTS:")

    for index, document in enumerate(documents):
        print(f"\nRESULT {index + 1}")
        print(document)

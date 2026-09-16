from backend.vector_store import collection
from backend.embedding import create_embedding


def retrieve_documents(question, top_k=3):
    question_vector = create_embedding(question)

    results = collection.query(
        query_embeddings=[question_vector],
        n_results=top_k
    )

    return results["documents"][0]


if __name__ == "__main__":
    question = "Who works in the IT department?"

    documents = retrieve_documents(question)

    print("RETRIEVED DOCUMENTS:")

    for index, document in enumerate(documents):
        print(f"\nRESULT {index + 1}")
        print(document)

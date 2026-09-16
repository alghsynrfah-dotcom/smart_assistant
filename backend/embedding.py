import os
print("EMBEDDING FILE IS RUNNING")
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv("backend/.env")

client = OpenAI(
    base_url=os.getenv("EMBEDDING_API_URL"),
    api_key=os.getenv("EMBEDDING_API_KEY")
)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")


def create_embedding(text):
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    return response.data[0].embedding
if __name__ == "__main__":
    from backend.rag import load_document, chunk_document

    document = load_document()
    chunks = chunk_document(document)

    print("NUMBER OF CHUNKS:", len(chunks))

    for index, chunk in enumerate(chunks):
        vector = create_embedding(chunk)

        print(f"\nCHUNK {index + 1}")
        print("TEXT:", chunk[:100])
        print("VECTOR LENGTH:", len(vector))
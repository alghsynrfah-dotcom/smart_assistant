import os

from dotenv import load_dotenv
from openai import OpenAI

from backend.retrieval import retrieve_documents


load_dotenv("backend/.env")


client = OpenAI(
    base_url=os.getenv("VLLM_API_URL"),
    api_key=os.getenv("VLLM_API_KEY")
)

MODEL_NAME = os.getenv("MODEL_NAME")


def generate_rag_answer(question, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    # 1. Retrieve relevant chunks
    documents = retrieve_documents(question, top_k=3)

    # 2. Combine retrieved chunks into context
    context = "\n\n".join(documents)

    # 3. Convert conversation history to text
    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in conversation_history
    )

    # 4. Build prompt
    prompt = f"""
Use the document context and the conversation history to answer the user's question.

Document Context:
{context}

Conversation History:
{history_text}

Current User Question:
{question}

If the answer is not available in the document context, say that the information is not available in the document.
"""

    # 5. Send the prompt to the LLM
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    # 6. Return the answer
    return response.choices[0].message.content


if __name__ == "__main__":
    conversation_history = [
        {
            "role": "user",
            "content": "Who works in the IT department?"
        },
        {
            "role": "assistant",
            "content": "Ahmad and Omar work in the IT department."
        }
    ]

    question = "What are their salaries?"

    answer = generate_rag_answer(
        question,
        conversation_history
    )

    print("RAG ANSWER:")
    print(answer)
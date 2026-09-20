
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


def build_retrieval_question(question, conversation_history):
    if not conversation_history:
        return question

    recent_history = conversation_history[-4:]

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_history
    )

    return f"""
Previous conversation:
{history_text}

Current question:
{question}
"""


def retrieve_rag_documents(question, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    retrieval_question = build_retrieval_question(
        question,
        conversation_history
    )

    documents = retrieve_documents(
        retrieval_question,
        top_k=3
    )

    return documents


def get_rag_sources(question, conversation_history=None):
    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    sources = list(
        dict.fromkeys(
            document["source"]
            for document in documents
        )
    )

    return sources


def generate_rag_answer(question, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    # 1. Retrieve relevant chunks
    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    # 2. Combine retrieved chunks into context
    context = "\n\n".join(
        document["text"]
        for document in documents
    )

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


def generate_rag_answer_stream(question, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    # 1. Retrieve relevant chunks
    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    # 2. Combine retrieved chunks into context
    context = "\n\n".join(
        document["text"]
        for document in documents
    )

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

    # 5. Send the prompt to the LLM with streaming
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )

    # 6. Return the answer gradually
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


if __name__ == "__main__":
    question = "How do departments collaborate?"

    print("STREAMING TEST:")

    for text in generate_rag_answer_stream(question):
        print(text, end="", flush=True)

    print()
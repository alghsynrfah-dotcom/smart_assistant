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


def get_recent_history(conversation_history):
    if not conversation_history:
        return []

    return conversation_history[-4:]


def build_retrieval_question(question, conversation_history):
    recent_history = get_recent_history(conversation_history)

    if not recent_history:
        return question

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

    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    context = "\n\n".join(
        document["text"]
        for document in documents
    )

    recent_history = get_recent_history(
        conversation_history
    )

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_history
    )

    prompt = f"""
Use the document context and the conversation history to answer the user's question.

Document Context:
{context}

Recent Conversation Context:
{history_text}

Current User Question:
{question}

If the answer is not available in the document context, say that the information is not available in the document.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content


def generate_rag_answer_stream(question, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    context = "\n\n".join(
        document["text"]
        for document in documents
    )

    recent_history = get_recent_history(
        conversation_history
    )

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_history
    )

    prompt = f"""
Use the document context and the conversation history to answer the user's question.

Document Context:
{context}

Recent Conversation Context:
{history_text}

Current User Question:
{question}

If the answer is not available in the document context, say that the information is not available in the document.
"""

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

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


if __name__ == "__main__":
    question = "How do departments collaborate?"

    print("STREAMING TEST:")

    for text in generate_rag_answer_stream(question):
        print(text, end="", flush=True)

    print()
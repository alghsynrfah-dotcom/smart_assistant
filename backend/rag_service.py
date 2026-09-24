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


# ==================================================
# Conversational History
# ==================================================

def get_recent_history(conversation_history):

    if not conversation_history:
        return []

    return conversation_history[-2:]


# ==================================================
# Build Retrieval Question
# ==================================================

def build_retrieval_question(
    question,
    conversation_history
):

    recent_history = get_recent_history(
        conversation_history
    )

    if not recent_history:
        return question

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_history
    )

    return (
        "Previous conversation:\n"
        + history_text
        + "\nCurrent question:\n"
        + question
    )


# ==================================================
# Retrieve RAG Documents
# ==================================================

def retrieve_rag_documents(
    question,
    conversation_history=None
):

    if conversation_history is None:
        conversation_history = []

    retrieval_question = build_retrieval_question(
        question,
        conversation_history
    )

    documents = retrieve_documents(
        retrieval_question,
        top_k=2
    )

    return documents


# ==================================================
# RAG Sources
# ==================================================

def get_rag_sources(
    question,
    conversation_history=None
):

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


# ==================================================
# Build RAG Prompt
# ==================================================

def build_rag_prompt(
    question,
    conversation_history,
    documents
):

    # Keep only a small amount of document context
    # because the model supports only 512 tokens.

    context_parts = []

    for document in documents:

        text = document["text"]

        # Limit each document chunk.
        text = text[:1200]

        context_parts.append(text)

    context = "\n\n".join(
        context_parts
    )

    recent_history = get_recent_history(
        conversation_history
    )

    history_text = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_history
    )

    prompt = f"""
Answer the user's question using the employee documents.

Documents:
{context}

Previous conversation:
{history_text}

Question:
{question}

If the answer is not in the documents, say:
"The information is not available in the document."
"""

    return prompt


# ==================================================
# Generate RAG Answer
# ==================================================

def generate_rag_answer(
    question,
    conversation_history=None
):

    if conversation_history is None:
        conversation_history = []

    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    prompt = build_rag_prompt(
        question,
        conversation_history,
        documents
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=150
    )

    return response.choices[0].message.content


# ==================================================
# Generate Streaming RAG Answer
# ==================================================

def generate_rag_answer_stream(
    question,
    conversation_history=None
):

    if conversation_history is None:
        conversation_history = []

    documents = retrieve_rag_documents(
        question,
        conversation_history
    )

    prompt = build_rag_prompt(
        question,
        conversation_history,
        documents
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=150,
        stream=True
    )

    for chunk in response:

        if (
            chunk.choices
            and chunk.choices[0].delta.content
        ):

            yield chunk.choices[0].delta.content


# ==================================================
# Test
# ==================================================

if __name__ == "__main__":

    question = "How do departments collaborate?"

    print("STREAMING TEST:")

    for text in generate_rag_answer_stream(
        question
    ):

        print(
            text,
            end="",
            flush=True
        )

    print()
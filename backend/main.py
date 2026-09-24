from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import psycopg

from backend.router import route_question

from backend.rag_service import (
    generate_rag_answer,
    generate_rag_answer_stream,
    get_rag_sources
)

from backend.tools.calculator import calculate
from backend.tools.cv_extractor import extract_cv_text

from pydantic import BaseModel
from typing import List

import os
from pathlib import Path
import json
import re

from dotenv import load_dotenv
from openai import OpenAI


app = FastAPI()


# ==================================================
# CORS
# ==================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Route", "X-Source"]
)


# ==================================================
# Environment variables
# ==================================================

load_dotenv("backend/.env")


client = OpenAI(
    base_url=os.getenv("VLLM_API_URL"),
    api_key=os.getenv("VLLM_API_KEY")
)

MODEL_NAME = os.getenv("MODEL_NAME")


# ==================================================
# Session Memory
# ==================================================
#
# Conversational History:
#   stores previous messages.
#
# Session Memory:
#   stores important information extracted from
#   the conversation.
#
# Example:
#
# SESSION_MEMORY = {
#     "default": {
#         "important_facts": [
#             "User is interested in front-end development",
#             "User has Java and C++ experience"
#         ]
#     }
# }
#

SESSION_MEMORY = {}


# ==================================================
# System Prompt
# ==================================================

SYSTEM_PROMPT = """
You are a Smart Assistant.

The application has several routes and tools:

1. Calculator:
   Calculation questions are handled by the Calculator tool.
   Do not calculate mathematical expressions yourself.

2. CV Extraction:
   Questions about an uploaded CV are handled by the CV Extraction tool.
   Use only the extracted CV information when answering CV questions.
   If the requested information is not available in the CV, say so.

3. RAG:
   Questions about employee documents, employee skills,
   responsibilities, departments, company information, and document-based
   information are handled by the RAG system.

4. PostgreSQL:
   Employee salary and direct database information are handled by PostgreSQL.

5. General LLM:
   General questions that do not require application data or tools
   can be answered normally.

Always follow the route selected by the application.
Do not invent information.
Do not provide employee or CV information unless it comes from the
appropriate tool or retrieved context.
"""


# ==================================================
# Models
# ==================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    conversation_history: List[Message] = []
    session_id: str = "default"


class RecommendationRequest(BaseModel):
    conversation: List[Message]


class ChatResponse(BaseModel):
    answer: str
    route: str
    source: str


# ==================================================
# Database
# ==================================================

def get_db_connection():
    return psycopg.connect(
        "dbname=smart_assistant user=rafah"
    )


def init_chat_history_table():
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                route TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    conn.commit()
    conn.close()


def save_chat_history(question, answer, route, source):
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO chat_history
            (question, answer, route, source)
            VALUES (%s, %s, %s, %s);
        """, (question, answer, route, source))

    conn.commit()
    conn.close()


def get_chat_history():
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT question, answer, route, source
            FROM chat_history
            ORDER BY id DESC
            LIMIT 4;
        """)

        rows = cursor.fetchall()

    conn.close()

    rows.reverse()

    return [
        {
            "question": row[0],
            "answer": row[1],
            "route": row[2],
            "source": row[3]
        }
        for row in rows
    ]


# ==================================================
# Session Memory Functions
# ==================================================

def get_session_memory(session_id):
    """
    Return the important information stored for a session.
    """

    if session_id not in SESSION_MEMORY:
        SESSION_MEMORY[session_id] = {
            "important_facts": []
        }

    return SESSION_MEMORY[session_id]


def update_session_memory(
    session_id,
    question,
    answer
):
    """
    Extract important information from the current
    conversation turn and store it in Session Memory.

    Session Memory is different from Conversational History.

    Conversational History:
        Previous messages.

    Session Memory:
        Important facts that may be useful later
        in the same session.

    This function uses one LLM call only.
    It is not an agent loop.
    """

    memory = get_session_memory(session_id)

    current_facts = memory.get(
        "important_facts",
        []
    )

    memory_prompt = f"""
You maintain Session Memory for a Smart Assistant.

Session Memory is NOT conversational history.

Store only important information that can be useful later
in the SAME conversation.

Do NOT store:
- greetings
- small talk
- temporary wording
- unnecessary details
- the full conversation
- mathematical calculations unless they are important context

Useful information can include:
- user's name
- user's interests
- user's preferences
- user's goals
- facts explicitly stated by the user
- important context needed for follow-up questions
- important entities discussed in the conversation

Current Session Memory:
{json.dumps(current_facts, ensure_ascii=False)}

New user message:
{question}

Assistant answer:
{answer}

Return the COMPLETE updated Session Memory.

Keep all useful existing facts and add only NEW important facts.

Do not invent information.

Return ONLY valid JSON in exactly this format:

{{
    "important_facts": [
        "fact 1",
        "fact 2"
    ]
}}
"""

    try:

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": memory_prompt
                }
            ]
        )

        content = response.choices[0].message.content

        if not content:
            return

        content = content.strip()

        # Remove markdown code fences if Qwen adds them.
        content = re.sub(
            r"^```json\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            r"^```\s*",
            "",
            content
        )

        content = re.sub(
            r"\s*```$",
            "",
            content
        )

        # Try to extract JSON object if extra text exists.
        json_match = re.search(
            r"\{.*\}",
            content,
            re.DOTALL
        )

        if json_match:
            content = json_match.group(0)

        data = json.loads(content)

        new_facts = data.get(
            "important_facts",
            []
        )

        if not isinstance(new_facts, list):
            return

        # --------------------------------------------------
        # Merge old + new facts
        # --------------------------------------------------

        merged_facts = []

        for fact in current_facts + new_facts:

            if not isinstance(fact, str):
                continue

            fact = fact.strip()

            if not fact:
                continue

            if fact not in merged_facts:
                merged_facts.append(fact)

        memory["important_facts"] = merged_facts

        print(
            "SESSION MEMORY UPDATED:",
            memory["important_facts"]
        )

    except Exception as e:

        print(
            "SESSION MEMORY ERROR:",
            e
        )


# ==================================================
# Basic endpoints
# ==================================================

@app.get("/")
def root():
    return {
        "message": "Smart Assistant Backend is working!"
    }


@app.get("/employees")
def get_employees():

    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM employees;"
        )

        employees = cursor.fetchall()

    conn.close()

    return {
        "employees": employees
    }


@app.get("/route")
def test_route(question: str):

    route = route_question(question)

    return {
        "question": question,
        "route": route
    }


@app.get("/history")
def history():

    return {
        "history": get_chat_history()
    }


# ==================================================
# Session Memory endpoint
# ==================================================

@app.get("/session-memory/{session_id}")
def session_memory_endpoint(session_id: str):

    memory = get_session_memory(session_id)

    return {
        "session_id": session_id,
        "memory": memory
    }


# ==================================================
# Clear Session Memory
# ==================================================

@app.delete("/session-memory/{session_id}")
def clear_session_memory(session_id: str):

    SESSION_MEMORY.pop(
        session_id,
        None
    )

    return {
        "message": "Session memory cleared.",
        "session_id": session_id
    }


# ==================================================
# CV Upload
# ==================================================

@app.post("/cv/upload")
async def upload_cv(
    file: UploadFile = File(...)
):

    if file.content_type != "application/pdf":

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    cv_path = (
        Path(__file__).parent
        / "data"
        / "rafah_cv.pdf"
    )

    try:

        file_content = await file.read()

        with open(
            cv_path,
            "wb"
        ) as output_file:

            output_file.write(
                file_content
            )

        return {
            "message": "CV uploaded successfully.",
            "filename": file.filename
        }

    except Exception as e:

        print(
            "CV UPLOAD ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail="Could not save the CV."
        )


# ==================================================
# Recommendation
# ==================================================

def generate_recommendation(conversation):

    conversation_text = " ".join(
        message.content.lower()
        for message in conversation
        if message.role == "user"
    )

    if any(
        word in conversation_text
        for word in [
            "department",
            "departments",
            "it department",
            "hr department",
            "finance department",
            "collaboration",
        ]
    ):

        return (
            "You may also want to ask about department responsibilities."
        )

    if any(
        word in conversation_text
        for word in [
            "ahmad",
            "omar",
            "sara",
            "lina",
            "employee",
            "employees",
        ]
    ):

        return (
            "You may also want to ask about employee skills and responsibilities."
        )

    if any(
        word in conversation_text
        for word in [
            "salary",
            "salaries",
            "راتب",
            "رواتب",
        ]
    ):

        return (
            "You may also want to ask about employee departments and positions."
        )

    if any(
        word in conversation_text
        for word in [
            "software",
            "programming",
            "backend",
            "developer",
        ]
    ):

        return (
            "You may also want to ask about technical responsibilities."
        )

    if any(
        word in conversation_text
        for word in [
            "recruitment",
            "hr",
            "human resources",
        ]
    ):

        return (
            "You may also want to ask about HR responsibilities."
        )

    if any(
        word in conversation_text
        for word in [
            "finance",
            "accounting",
        ]
    ):

        return (
            "You may also want to ask about Finance responsibilities."
        )

    return (
        "You may also want to ask about another employee or department."
    )


@app.post("/recommendation")
def recommendation(
    request: RecommendationRequest
):

    return {
        "recommendation": generate_recommendation(
            request.conversation
        )
    }


# ==================================================
# Employee database
# ==================================================

def get_employee_data(
    employee_name=None
):

    conn = get_db_connection()

    with conn.cursor() as cursor:

        if employee_name:

            cursor.execute(
                """
                SELECT id, name, department, position, salary
                FROM employees
                WHERE LOWER(name) = LOWER(%s);
                """,
                (employee_name,)
            )

        else:

            cursor.execute(
                """
                SELECT id, name, department, position, salary
                FROM employees;
                """
            )

        rows = cursor.fetchall()

    conn.close()

    return rows


# ==================================================
# Chat endpoint
# ==================================================

@app.post("/chat")
def chat(request: ChatRequest):

    # ==================================================
    # Conversational History
    # ==================================================

    history = [
        {
            "role": message.role,
            "content": message.content
        }
        for message in request.conversation_history
    ]

    # ==================================================
    # Session Memory
    # ==================================================

    session_memory = get_session_memory(
        request.session_id
    )

    # ==================================================
    # Check uploaded CV
    # ==================================================

    cv_path = (
        Path(__file__).parent
        / "data"
        / "rafah_cv.pdf"
    )

    cv_uploaded = cv_path.exists()

    # ==================================================
    # Router
    # ==================================================

    route = route_question(
        request.question,
        history,
        cv_uploaded
    )

    # ==================================================
    # Calculator
    # ==================================================

    if route == "calculator":

        try:

            answer = calculate(
                request.question
            )

            if answer is None:

                answer = (
                    "Could not calculate the expression."
                )

            else:

                answer = str(answer)

            save_chat_history(
                request.question,
                answer,
                "calculator",
                "calculator"
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": "calculator",
                "source": "calculator"
            }

        except Exception as e:

            print(
                "CALCULATOR ERROR:",
                e
            )

            answer = (
                "Could not calculate the expression."
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": "calculator",
                "source": "calculator"
            }

    # ==================================================
    # CV Extraction
    # ==================================================

    if route == "cv_extraction":

        cv_path = (
            Path(__file__).parent
            / "data"
            / "rafah_cv.pdf"
        )

        try:

            cv_text = extract_cv_text(
                cv_path
            )

            if not cv_text:

                answer = (
                    "Could not extract text from the CV."
                )

                save_chat_history(
                    request.question,
                    answer,
                    "cv_extraction",
                    "CV"
                )

                update_session_memory(
                    request.session_id,
                    request.question,
                    answer
                )

                return {
                    "answer": answer,
                    "route": "cv_extraction",
                    "source": "CV"
                }

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer the user's question using only "
                            "the CV content below. "
                            "If the answer is not in the CV, say "
                            "that the information is not available "
                            "in the CV."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"CV CONTENT:\n{cv_text}\n\n"
                            f"QUESTION:\n{request.question}"
                        )
                    }
                ]
            )

            answer = (
                response.choices[0].message.content
            )

            save_chat_history(
                request.question,
                answer,
                "cv_extraction",
                "CV"
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": "cv_extraction",
                "source": "CV"
            }

        except Exception as e:

            print(
                "CV EXTRACTION ERROR:",
                e
            )

            answer = (
                "Could not process the CV."
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": "cv_extraction",
                "source": "CV"
            }

    # ==================================================
    # RAG
    # ==================================================

    if route == "rag":

        # Keep Conversational History separate
        # from Session Memory.

        rag_history = (
            history[-6:]
            if history
            else []
        )

        try:

            sources = get_rag_sources(
                request.question,
                rag_history
            )

            if sources:

                source = ", ".join(
                    sources
                )

            else:

                source = (
                    "employee documents"
                )

        except Exception as e:

            print(
                "RAG SOURCE ERROR:",
                e
            )

            source = (
                "employee documents"
            )

        def rag_generator():

            answer_parts = []

            try:

                for text in generate_rag_answer_stream(
                    request.question,
                    rag_history
                ):

                    answer_parts.append(
                        text
                    )

                    yield text

                full_answer = "".join(
                    answer_parts
                )

                save_chat_history(
                    request.question,
                    full_answer,
                    "rag",
                    source
                )

                # Extract important information
                # only after the complete answer exists.

                update_session_memory(
                    request.session_id,
                    request.question,
                    full_answer
                )

            except Exception as e:

                print(
                    "RAG STREAM ERROR:",
                    e
                )

                error_answer = (
                    "\n\nThe RAG service is currently unavailable."
                )

                update_session_memory(
                    request.session_id,
                    request.question,
                    error_answer
                )

                yield error_answer

        return StreamingResponse(
            rag_generator(),
            media_type="text/plain",
            headers={
                "X-Route": "rag",
                "X-Source": source
            }
        )

    # ==================================================
    # Database
    # ==================================================

    if route == "db_direct":

        try:

            question_lower = (
                request.question.lower()
            )

            employee_name = None

            if "ahmad" in question_lower:

                employee_name = "Ahmad"

            elif "sara" in question_lower:

                employee_name = "Sara"

            elif "omar" in question_lower:

                employee_name = "Omar"

            elif "lina" in question_lower:

                employee_name = "Lina"

            employees = get_employee_data(
                employee_name
            )

            if not employees:

                answer = (
                    "No employee data found."
                )

                save_chat_history(
                    request.question,
                    answer,
                    route,
                    "PostgreSQL"
                )

                update_session_memory(
                    request.session_id,
                    request.question,
                    answer
                )

                return {
                    "answer": answer,
                    "route": route,
                    "source": "PostgreSQL"
                }

            answer = "\n".join(
                f"ID: {row[0]}, Name: {row[1]}, "
                f"Department: {row[2]}, Position: {row[3]}, "
                f"Salary: {row[4]}"
                for row in employees
            )

            save_chat_history(
                request.question,
                answer,
                route,
                "PostgreSQL"
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

        except Exception as e:

            print(
                "DATABASE ERROR:",
                e
            )

            answer = (
                "Could not retrieve employee data from PostgreSQL."
            )

            update_session_memory(
                request.session_id,
                request.question,
                answer
            )

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

    # ==================================================
    # General LLM
    # ==================================================

    try:

        # --------------------------------------------------
        # Conversational History
        # --------------------------------------------------

        history_messages = history[-6:]

        # --------------------------------------------------
        # Session Memory
        # --------------------------------------------------

        important_facts = session_memory.get(
            "important_facts",
            []
        )

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        # Add Session Memory
        if important_facts:

            messages.append({
                "role": "system",
                "content": (
                    "Important information remembered "
                    "from this session:\n"
                    + "\n".join(
                        f"- {fact}"
                        for fact in important_facts
                    )
                )
            })

        # Add Conversational History
        messages.extend(
            history_messages
        )

        # Add current question
        messages.append({
            "role": "user",
            "content": request.question
        })

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )

        answer = (
            response.choices[0].message.content
        )

        save_chat_history(
            request.question,
            answer,
            "llm",
            "Qwen"
        )

        # Update Session Memory
        update_session_memory(
            request.session_id,
            request.question,
            answer
        )

        return {
            "answer": answer,
            "route": "llm",
            "source": "Qwen"
        }

    except Exception as e:

        print(
            "LLM ERROR:",
            e
        )

        answer = (
            "The LLM service is currently unavailable. "
            "Please try again later."
        )

        update_session_memory(
            request.session_id,
            request.question,
            answer
        )

        return {
            "answer": answer,
            "route": "llm",
            "source": "Qwen"
        }


# ==================================================
# Initialize database table
# ==================================================

init_chat_history_table()
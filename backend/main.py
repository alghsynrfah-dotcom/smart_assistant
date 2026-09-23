
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

SESSION_MEMORY = {}


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
        cursor.execute("SELECT * FROM employees;")
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
# CV Upload
# ==================================================

@app.post("/cv/upload")
async def upload_cv(file: UploadFile = File(...)):

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

        with open(cv_path, "wb") as output_file:
            output_file.write(file_content)

        return {
            "message": "CV uploaded successfully.",
            "filename": file.filename
        }

    except Exception as e:
        print("CV UPLOAD ERROR:", e)

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

    if any(word in conversation_text for word in [
        "department",
        "departments",
        "it department",
        "hr department",
        "finance department",
        "collaboration",
    ]):
        return (
            "You may also want to ask about department responsibilities."
        )

    if any(word in conversation_text for word in [
        "ahmad",
        "omar",
        "sara",
        "lina",
        "employee",
        "employees",
    ]):
        return (
            "You may also want to ask about employee skills and responsibilities."
        )

    if any(word in conversation_text for word in [
        "salary",
        "salaries",
        "راتب",
        "رواتب",
    ]):
        return (
            "You may also want to ask about employee departments and positions."
        )

    if any(word in conversation_text for word in [
        "software",
        "programming",
        "backend",
        "developer",
    ]):
        return (
            "You may also want to ask about technical responsibilities."
        )

    if any(word in conversation_text for word in [
        "recruitment",
        "hr",
        "human resources",
    ]):
        return (
            "You may also want to ask about HR responsibilities."
        )

    if any(word in conversation_text for word in [
        "finance",
        "accounting",
    ]):
        return (
            "You may also want to ask about Finance responsibilities."
        )

    return (
        "You may also want to ask about another employee or department."
    )


@app.post("/recommendation")
def recommendation(request: RecommendationRequest):

    return {
        "recommendation": generate_recommendation(
            request.conversation
        )
    }


# ==================================================
# Employee database
# ==================================================

def get_employee_data(employee_name=None):

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

    if request.session_id not in SESSION_MEMORY:
        SESSION_MEMORY[request.session_id] = []

    session_memory = SESSION_MEMORY[request.session_id]

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
            answer = calculate(request.question)

            if answer is None:
                answer = "Could not calculate the expression."

            else:
                answer = str(answer)

            save_chat_history(
                request.question,
                answer,
                "calculator",
                "calculator"
            )

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "route": "calculator",
                "source": "calculator"
            }

        except Exception as e:

            print("CALCULATOR ERROR:", e)

            answer = "Could not calculate the expression."

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

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

            cv_text = extract_cv_text(cv_path)

            if not cv_text:

                answer = "Could not extract text from the CV."

                save_chat_history(
                    request.question,
                    answer,
                    "cv_extraction",
                    "CV"
                )

                session_memory.append({
                    "role": "user",
                    "content": request.question
                })

                session_memory.append({
                    "role": "assistant",
                    "content": answer
                })

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

            answer = response.choices[0].message.content

            save_chat_history(
                request.question,
                answer,
                "cv_extraction",
                "CV"
            )

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "route": "cv_extraction",
                "source": "CV"
            }

        except Exception as e:

            print("CV EXTRACTION ERROR:", e)

            answer = "Could not process the CV."

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "route": "cv_extraction",
                "source": "CV"
            }

    # ==================================================
    # RAG
    # ==================================================

    if route == "rag":

        rag_history = (
            session_memory[-6:]
            if session_memory
            else history
        )

        try:

            sources = get_rag_sources(
                request.question,
                rag_history
            )

            if sources:
                source = ", ".join(sources)
            else:
                source = "employee documents"

        except Exception as e:

            print("RAG SOURCE ERROR:", e)

            source = "employee documents"

        def rag_generator():

            answer_parts = []

            try:

                for text in generate_rag_answer_stream(
                    request.question,
                    rag_history
                ):

                    answer_parts.append(text)

                    yield text

                full_answer = "".join(answer_parts)

                save_chat_history(
                    request.question,
                    full_answer,
                    "rag",
                    source
                )

                session_memory.append({
                    "role": "user",
                    "content": request.question
                })

                session_memory.append({
                    "role": "assistant",
                    "content": full_answer
                })

            except Exception as e:

                print("RAG STREAM ERROR:", e)

                error_answer = (
                    "\n\nThe RAG service is currently unavailable."
                )

                session_memory.append({
                    "role": "user",
                    "content": request.question
                })

                session_memory.append({
                    "role": "assistant",
                    "content": error_answer
                })

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

            question_lower = request.question.lower()

            employee_name = None

            if "ahmad" in question_lower:
                employee_name = "Ahmad"

            elif "sara" in question_lower:
                employee_name = "Sara"

            elif "omar" in question_lower:
                employee_name = "Omar"

            elif "lina" in question_lower:
                employee_name = "Lina"

            employees = get_employee_data(employee_name)

            if not employees:

                answer = "No employee data found."

                save_chat_history(
                    request.question,
                    answer,
                    route,
                    "PostgreSQL"
                )

                session_memory.append({
                    "role": "user",
                    "content": request.question
                })

                session_memory.append({
                    "role": "assistant",
                    "content": answer
                })

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

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

        except Exception as e:

            print("DATABASE ERROR:", e)

            answer = (
                "Could not retrieve employee data from PostgreSQL."
            )

            session_memory.append({
                "role": "user",
                "content": request.question
            })

            session_memory.append({
                "role": "assistant",
                "content": answer
            })

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

    # ==================================================
    # General LLM
    # ==================================================

    try:

        memory_messages = session_memory[-6:]

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

        messages.extend(memory_messages)

        messages.append({
            "role": "user",
            "content": request.question
        })

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )

        answer = response.choices[0].message.content

        save_chat_history(
            request.question,
            answer,
            "llm",
            "Qwen"
        )

        session_memory.append({
            "role": "user",
            "content": request.question
        })

        session_memory.append({
            "role": "assistant",
            "content": answer
        })

        return {
            "answer": answer,
            "route": "llm",
            "source": "Qwen"
        }

    except Exception as e:

        print("LLM ERROR:", e)

        answer = (
            "The LLM service is currently unavailable. "
            "Please try again later."
        )

        session_memory.append({
            "role": "user",
            "content": request.question
        })

        session_memory.append({
            "role": "assistant",
            "content": answer
        })

        return {
            "answer": answer,
            "route": "llm",
            "source": "Qwen"
        }


# ==================================================
# Initialize database table
# ==================================================

init_chat_history_table()

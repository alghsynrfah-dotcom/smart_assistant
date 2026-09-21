from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from backend.router import route_question
from backend.rag_service import (
    generate_rag_answer,
    generate_rag_answer_stream,
    get_rag_sources
)
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
from openai import OpenAI


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Route", "X-Source"]
)


load_dotenv("backend/.env")


client = OpenAI(
    base_url=os.getenv("VLLM_API_URL"),
    api_key=os.getenv("VLLM_API_KEY")
)

MODEL_NAME = os.getenv("MODEL_NAME")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    conversation_history: List[Message] = []


class RecommendationRequest(BaseModel):
    conversation: List[Message]

class ChatResponse(BaseModel):
    answer: str
    route: str
    source: str


def get_db_connection():
    return psycopg.connect(
        "dbname=smart_assistant user=rafah"
    )


def init_chat_history_table():
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                route TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    conn.commit()
    conn.close()


def save_chat_history(question, answer, route, source):
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_history
            (question, answer, route, source)
            VALUES (%s, %s, %s, %s);
            """,
            (question, answer, route, source)
        )

    conn.commit()
    conn.close()


def get_chat_history():
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT question, answer, route, source
            FROM chat_history
            ORDER BY id DESC
            LIMIT 4;
            """
        )

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
        return "You may also want to ask about department responsibilities."

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
        return "You may also want to ask about employee skills and responsibilities."

    if any(
        word in conversation_text
        for word in [
            "salary",
            "salaries",
            "راتب",
            "رواتب",
        ]
    ):
        return "You may also want to ask about employee departments and positions."

    if any(
        word in conversation_text
        for word in [
            "software",
            "programming",
            "backend",
            "developer",
        ]
    ):
        return "You may also want to ask about technical responsibilities."

    if any(
        word in conversation_text
        for word in [
            "recruitment",
            "hr",
            "human resources",
        ]
    ):
        return "You may also want to ask about HR responsibilities."

    if any(
        word in conversation_text
        for word in [
            "finance",
            "accounting",
        ]
    ):
        return "You may also want to ask about Finance responsibilities."

    return "You may also want to ask about another employee or department."


@app.post("/recommendation")
def recommendation(request: RecommendationRequest):
    return {
        "recommendation": generate_recommendation(
            request.conversation
        )
    }


def get_employee_data():
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, department, position, salary FROM employees;"
        )
        rows = cursor.fetchall()

    conn.close()

    return rows


@app.post("/chat")
def chat(request: ChatRequest):

    history = [
        {
            "role": message.role,
            "content": message.content
        }
        for message in request.conversation_history
    ]

    route = route_question(
        request.question,
        history
    )

    # =========================
    # RAG
    # =========================
    if route == "rag":

        try:
            sources = get_rag_sources(
                request.question,
                history
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
                    history
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

            except Exception as e:
                print("RAG STREAM ERROR:", e)
                yield "\n\nThe RAG service is currently unavailable."

        return StreamingResponse(
            rag_generator(),
            media_type="text/plain",
            headers={
                "X-Route": "rag",
                "X-Source": source
            }
        )

    # =========================
    # Database
    # =========================
    if route == "db_direct":
        try:
            employees = get_employee_data()

            if not employees:
                answer = "No employee data found."

                save_chat_history(
                    request.question,
                    answer,
                    route,
                    "PostgreSQL"
                )

                return {
                    "answer": answer,
                    "route": route,
                    "source": "PostgreSQL"
                }

            answer = "\n".join(
                f"ID: {row[0]}, Name: {row[1]}, Department: {row[2]}, "
                f"Position: {row[3]}, Salary: {row[4]}"
                for row in employees
            )

            save_chat_history(
                request.question,
                answer,
                route,
                "PostgreSQL"
            )

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

        except Exception as e:
            print("DATABASE ERROR:", e)

            answer = "Could not retrieve employee data from PostgreSQL."

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

    # =========================
    # LLM
    # =========================
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": request.question
                }
            ]
        )

        answer = response.choices[0].message.content

        save_chat_history(
            request.question,
            answer,
            "llm",
            "Qwen"
        )

        return {
            "answer": answer,
            "route": "llm",
            "source": "Qwen"
        }

    except Exception as e:
        print("LLM ERROR:", e)

        return {
            "answer": "The LLM service is currently unavailable. Please try again later.",
            "route": "llm",
            "source": "Qwen"
        }


init_chat_history_table()
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg
from backend.router import route_question
from backend.rag_service import (generate_rag_answer,generate_rag_answer_stream)
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


class ChatResponse(BaseModel):
    answer: str
    route: str
    source: str


def get_db_connection():
    return psycopg.connect(
        "dbname=smart_assistant user=rafah"
    )


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

    route = route_question(
        request.question,
        [
            {
                "role": message.role,
                "content": message.content
            }
            for message in request.conversation_history
        ]
    )

    # =========================
    # RAG
    # =========================
    if route == "rag":

        history = [
            {
                "role": message.role,
                "content": message.content
            }
            for message in request.conversation_history
        ]

        def rag_generator():
            try:
                for text in generate_rag_answer_stream(
                    request.question,
                    history
                ):
                    yield text

            except Exception as e:
                print("RAG STREAM ERROR:", e)
                yield "\n\nThe RAG service is currently unavailable."

        return StreamingResponse(
            rag_generator(),
            media_type="text/plain",
            headers={
                "X-Route": "rag",
                "X-Source": "employees.txt"
            }
        )

    # =========================
    # Database
    # =========================
    if route == "db_direct":
        try:
            employees = get_employee_data()

            if not employees:
                return {
                    "answer": "No employee data found.",
                    "route": route,
                    "source": "PostgreSQL"
                }

            answer = "\n".join(
                f"ID: {row[0]}, Name: {row[1]}, Department: {row[2]}, "
                f"Position: {row[3]}, Salary: {row[4]}"
                for row in employees
            )

            return {
                "answer": answer,
                "route": route,
                "source": "PostgreSQL"
            }

        except Exception as e:
            print("DATABASE ERROR:", e)

            return {
                "answer": "Could not retrieve employee data from PostgreSQL.",
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
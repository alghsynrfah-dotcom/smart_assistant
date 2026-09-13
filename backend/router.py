def route_question(question: str) -> str:
    question = question.lower()

    db_keywords = [
        "employee",
        "employees",
        "موظف",
        "موظفين",
        "الموظفين",
        "department",
        "قسم",
        "salary",
        "راتب",
    ]

    for keyword in db_keywords:
        if keyword in question:
            return "db_direct"

    return "llm"
def route_question(question: str, conversation_history=None) -> str:
    question = question.lower().strip()

    # --------------------------------------------------
    # Follow-up questions
    # --------------------------------------------------
    if conversation_history:
        history_text = " ".join(
            message["content"].lower()
            for message in conversation_history
        )

        follow_up_words = [
            "their",
            "them",
            "they",
            "he",
            "she",
            "his",
            "her",
            "about",
            "it",
            "هم",
            "هن",
            "له",
            "لها",
            "رواتبهم",
            "مهاراتهم",
        ]

        for word in follow_up_words:
            if word in question.split():
                if any(
                    context_word in history_text
                    for context_word in [
                        "it department",
                        "software development",
                        "skills",
                        "responsibilities",
                        "ahmad",
                        "omar",
                        "sara",
                        "lina",
                        "employee",
                        "department",
                    ]
                ):
                    return "rag"

    # --------------------------------------------------
    # Direct database questions
    # --------------------------------------------------
    db_keywords = [
        "salary",
        "salaries",
        "راتب",
        "رواتب",
    ]

    for keyword in db_keywords:
        if keyword in question:
            return "db_direct"

    # --------------------------------------------------
    # RAG questions
    # --------------------------------------------------
    rag_phrases = [
        # Employees
        "ahmad",
        "omar",
        "sara",
        "lina",
        "employee information",
        "employee details",
        "employee skills",
        "employee responsibilities",
        "employee department",
        "employee position",
        "employee role",

        # Skills
        "skills",
        "skill",
        "what are their skills",
        "what are his skills",
        "what are her skills",
        "what skills",

        # Responsibilities
        "responsibilities",
        "responsibility",
        "what does",
        "what do they do",
        "what does he do",
        "what does she do",

        # Departments
        "it department",
        "hr department",
        "finance department",
        "department responsibilities",
        "department collaboration",
        "how do departments collaborate",
        "how departments collaborate",
        "departments collaborate",
        "department information",

        # Contact information
        "phone number",
        "phone",
        "email",
        "address",
        "contact information",

        # Technical information
        "software development",
        "backend development",
        "backend",
        "programming",
        "server-side programming",
        "database-related tasks",
        "problem solving",
        "communication",
        "recruitment",
        "employee management",
        "accounting",

        # Company / document
        "company information",
        "company",
        "office",
        "opening date",
        "working hours",
        "office information",
    ]

    for phrase in rag_phrases:
        if phrase in question:
            return "rag"

    # --------------------------------------------------
    # Other employee questions
    # --------------------------------------------------
    employee_keywords = [
        "employee",
        "employees",
        "موظف",
        "موظفين",
        "الموظفين",
    ]

    for keyword in employee_keywords:
        if keyword in question:
            return "db_direct"

    # --------------------------------------------------
    # General LLM questions
    # --------------------------------------------------
    return "llm"
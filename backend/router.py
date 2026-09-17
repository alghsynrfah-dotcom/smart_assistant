def route_question(question: str, conversation_history=None) -> str:
    question = question.lower().strip()

    if conversation_history:
        history_text = " ".join(
            message["content"].lower()
            for message in conversation_history
        )

        # Follow-up questions related to a previous RAG conversation
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
                    word in history_text
                    for word in [
                        "it department",
                        "software development",
                        "skills",
                        "responsibilities",
                        "ahmad",
                        "omar",
                        "sara",
                        "lina",
                    ]
                ):
                    return "rag"

    # Questions that clearly need the RAG document
    rag_phrases = [
        "who works in it",
        "phone number",
        "phone",
        "email",
        "address",
        "what does",
        "what are their skills",
        "what are their responsibilities",
        "works as",
        "software development",
        "backend development",
        "recruitment",
        "accounting",
    ]

    for phrase in rag_phrases:
        if phrase in question:
            return "rag"
    # Questions related to the company/document
    document_context_phrases = [
        "company",
        "office",
        "opening date",
        "working hours",
        "employees",
        "employee information",
        "department information",
        "contact information",
        "company information",
        "office information",
    ]

    for phrase in document_context_phrases:
        if phrase in question:
            return "rag"
    # Direct database questions
    db_keywords = [
        "employee",
        "employees",
        "موظف",
        "موظفين",
        "الموظفين",
        "salary",
        "راتب",
    ]

    for keyword in db_keywords:
        if keyword in question:
            return "db_direct"

    return "llm"
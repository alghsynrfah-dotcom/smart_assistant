from pathlib import Path


DATA_PATH = Path(__file__).parent / "data"


def load_documents():
    documents = []

    files = sorted(
        file_path
        for file_path in DATA_PATH.iterdir()
        if file_path.is_file()
    )

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as file:
            documents.append({
                "source": file_path.name,
                "text": file.read()
            })

    return documents


def chunk_documents_with_sources(documents):
    chunks = []

    for document in documents:
        source = document["source"]
        text = document["text"]

        if "DEPARTMENT COLLABORATION" in text:
            headings = [
                "EMPLOYEE WORK INFORMATION",
                "IT EMPLOYEES",
                "HR EMPLOYEES",
                "FINANCE EMPLOYEES",
                "DEPARTMENT COLLABORATION"
            ]

            current_chunk = ""

            for line in text.splitlines():
                line = line.strip()

                if not line:
                    continue

                if line in headings:
                    if current_chunk:
                        chunks.append({
                            "text": current_chunk.strip(),
                            "source": source
                        })

                    current_chunk = line

                else:
                    current_chunk += "\n" + line

            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "source": source
                })

        else:
            sections = text.split("EMPLOYEE:")

            for section in sections:
                section = section.strip()

                if not section:
                    continue

                chunks.append({
                    "text": section,
                    "source": source
                })

    return chunks


if __name__ == "__main__":
    documents = load_documents()

    print("NUMBER OF DOCUMENTS:", len(documents))

    chunks = chunk_documents_with_sources(documents)

    print("NUMBER OF CHUNKS:", len(chunks))

    for index, chunk in enumerate(chunks):
        print(f"\n--- CHUNK {index + 1} ---")
        print("SOURCE:", chunk["source"])
        print("TEXT:")
        print(chunk["text"])
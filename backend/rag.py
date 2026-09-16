from pathlib import Path


DOCUMENT_PATH = Path(__file__).parent / "data" / "employees.txt"


def load_document():
    with open(DOCUMENT_PATH, "r", encoding="utf-8") as file:
        return file.read()


def chunk_document(text):
    sections = text.split("EMPLOYEE:")

    chunks = []

    for section in sections:
        section = section.strip()

        if not section:
            continue

        chunks.append(section)

    return chunks


if __name__ == "__main__":
    document = load_document()

    print("DOCUMENT LOADED:")
    print(document)

    chunks = chunk_document(document)

    print("\nNUMBER OF CHUNKS:", len(chunks))

    for index, chunk in enumerate(chunks):
        print(f"\n--- CHUNK {index + 1} ---")
        print(chunk)

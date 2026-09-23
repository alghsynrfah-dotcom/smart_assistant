from pypdf import PdfReader


def extract_cv_text(file_path: str):
    try:
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        if not text.strip():
            return None

        return text.strip()

    except Exception as e:
        print("ERROR:", e)
        return None


if __name__ == "__main__":
    text = extract_cv_text("backend/data/rafah_cv.pdf")

    if text:
        print("CV TEXT:")
        print(text)
    else:
        print("Could not extract CV text")
import glob
import os
import asyncio


async def analyze_letters(directory: str) -> dict:
    """Analyze the letters in the directory, understand the format and strictly adhere to it."""

    def _sync_analyze():
        files = glob.glob(os.path.join(directory, "**"), recursive=True)
        allowed_extensions = {".txt", ".md"}
        context = ""

        for file in files:
            if not os.path.isfile(file):
                continue

            _, ext = os.path.splitext(file)
            if ext.lower() not in allowed_extensions:
                continue

            try:
                with open(file, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file, encoding="latin-1") as f:
                    content = f.read()

            context += f"\n--- LETTER: {file} ---\n"
            context += content.strip() + "\n"
        return context

    context = await asyncio.to_thread(_sync_analyze)
    return {"letter_context": context}


def save_letter_to_file(letter: str, filename: str) -> str:
    """
    Saves the letter text to a file.
    This agent handles the physical saving of the letter and terminates the session.
    """
    with open(filename, "w", encoding="utf-8") as f:
        f.write(letter)
    return f"Successfully saved letter to {filename}."

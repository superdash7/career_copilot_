


from openai import OpenAI
from pypdf import PdfReader
import json
from config import Config

class ResumeParser:
    def __init__(self):
        self._api_key = Config.OPENAI_API_KEY
        self.client = OpenAI(api_key=self._api_key) if self._api_key else None

    def extract_text(self, pdf_path):
        if pdf_path is None:
            return ""
        # Gradio может передать путь (str) или объект с атрибутом name
        path = getattr(pdf_path, "name", pdf_path)
        if isinstance(path, bytes):
            path = path.decode("utf-8")
        text = ""
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        max_len = getattr(Config, "RESUME_TEXT_MAX_CHARS", 14000)
        if len(text) > max_len:
            text = text[:max_len] + "\n\n[Текст обрезан. Извлеки навыки из приведённой части.]"
        return text

    def parse_skills(self, resume_text, allowed_skills):
        if not self.client:
            raise ValueError(
                "OPENAI_API_KEY не задан. Добавьте ключ в .env для распознавания навыков из PDF."
            )
        model = getattr(Config, "RESUME_PARSER_MODEL", "gpt-4o")
        skills_str = ", ".join(allowed_skills)

        system_prompt = f"""
Ты HR-аналитик. Извлеки навыки из резюме, сопоставь со списком: [{skills_str}].
Оцени уровень 1-3 (1-Junior, 2-Middle, 3-Senior).
Верни только JSON без комментариев: {{"skills": [{{"name": "название навыка", "level": число}}]}}
"""

        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": resume_text}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                raw = response.choices[0].message.content
                data = json.loads(raw)
                if not isinstance(data, dict) or "skills" not in data:
                    data = {"skills": []}
                if not isinstance(data["skills"], list):
                    data["skills"] = []
                return data
            except json.JSONDecodeError:
                if attempt == 0:
                    system_prompt = "Верни строго JSON: {\"skills\": [{\"name\": \"навык\", \"level\": 1}]}. Без markdown и текста вокруг."
                    continue
                return {"skills": []}
            except Exception:
                if attempt == 1:
                    raise
                import time
                time.sleep(1)
        return {"skills": []}

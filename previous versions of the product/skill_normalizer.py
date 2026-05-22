
"""NLP: лемматизация (pymorphy3 для русского, простой стемминг для английского)
и слой синонимов для маппинга навыков"""

import json
import re
from pathlib import Path
from typing import Optional, Set, Dict

_morph = None
_stemmer_en = None
_synonym_map: Optional[Dict[str, str]] = None


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яёА-ЯЁ]", text))


def _get_analyzers():
    """Ленивая загрузка pymorphy3 (русский) и NLTK Snowball (английский)."""
    global _morph, _stemmer_en
    if _morph is None:
        try:
            import pymorphy3
            _morph = pymorphy3.MorphAnalyzer()
        except Exception as e:
            raise RuntimeError(
                f"Для лемматизации нужен pymorphy3: pip install pymorphy3. Ошибка: {e}"
            )
    if _stemmer_en is None:
        try:
            from nltk.stem.snowball import SnowballStemmer
            _stemmer_en = SnowballStemmer("english")
        except Exception:
            _stemmer_en = None
    return _morph, _stemmer_en


def _lemmatize_word(word: str, morph, stemmer_en) -> str:
    """Лемматизация одного слова: pymorphy3 для русского, Snowball для английского."""
    w = word.strip()
    if not w:
        return w
    if _has_cyrillic(w):
        parsed = morph.parse(w.lower())
        if parsed:
            return parsed[0].normal_form
        return w.lower()
    if stemmer_en:
        return stemmer_en.stem(w.lower())
    return w.lower()


def normalize_for_search(text: str) -> str:
    """
    Нормализация текста для поиска: lower, trim, схлопывание пробелов,
    замена опечаток, лемматизация по словам (русский/английский).
    """
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = " ".join(t.split())
    typo_map = {
        "питон": "python",
        "пайтон": "python",
        "дата саенс": "data science",
        "машин лернинг": "machine learning",
    }
    for wrong, right in typo_map.items():
        if wrong in t and right not in t:
            t = t.replace(wrong, right)
    try:
        morph, stemmer_en = _get_analyzers()
        words = t.split()
        lemmatized = [_lemmatize_word(w, morph, stemmer_en) for w in words]
        return " ".join(lemmatized)
    except Exception:
        return t


def _load_synonym_map() -> Dict[str, str]:
    """Загружает словарь синонимов из data/skill_synonyms.json."""
    global _synonym_map
    if _synonym_map is not None:
        return _synonym_map
    path = Path(__file__).resolve().parent / "data" / "skill_synonyms.json"
    _synonym_map = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                if k and v:
                    key = k.strip().lower()
                    _synonym_map[key] = v.strip()
                    try:
                        norm_key = normalize_for_search(k)
                        if norm_key and norm_key != key:
                            _synonym_map[norm_key] = v.strip()
                    except Exception:
                        pass
        except Exception:
            pass
    return _synonym_map


def resolve_to_canonical(user_input: str, canonical_set: Optional[Set[str]] = None) -> Optional[str]:
    """
    Сопоставление ввода пользователя с каноническим названием навыка.
    Сначала проверяется словарь синонимов (точное и нормализованное совпадение),
    затем по нормализованному (лемма) виду ключей словаря.
    Если canonical_set задан, возвращаемое значение должно входить в этот набор.
    """
    if not user_input or not str(user_input).strip():
        return None
    raw = str(user_input).strip()
    low = raw.lower()
    syn_map = _load_synonym_map()
    if low in syn_map:
        cand = syn_map[low]
        if canonical_set is None or cand in canonical_set:
            return cand
    try:
        norm = normalize_for_search(raw)
        if norm and norm in syn_map:
            cand = syn_map[norm]
            if canonical_set is None or cand in canonical_set:
                return cand
    except Exception:
        pass
    try:
        norm_input = normalize_for_search(raw)
        for key, canonical in syn_map.items():
            if normalize_for_search(key) == norm_input:
                if canonical_set is None or canonical in canonical_set:
                    return canonical
    except Exception:
        pass
    return None


def get_canonical_skills_set():
    """Возвращает множество канонических названий навыков из DataLoader (ленивый импорт)."""
    try:
        from config import Config
        path = Path(Config.SKILLS_FILE)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        with open(path, "r", encoding="utf-8") as f:
            skills = json.load(f)
        names = set()
        for s in skills:
            n = s.get("Навык") or s.get("name")
            if n:
                names.add(str(n).strip())
        return names
    except Exception:
        return set()

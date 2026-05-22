
"""RAG и NLP: индексация навыков/атласа, поиск, подсказки навыков, семантическое ранжирование."""

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from config import Config

# Ленивая загрузка тяжёлых зависимостей
_sentence_transformer = None

# --- Qdrant через REST API ---


def _qdrant_rest_config():
    
    url = (Config.QDRANT_URL or "").strip()
    key = (Config.QDRANT_API_KEY or "").strip()
    if not url or not key:
        return None, None
    base = url.rstrip("/")
    headers = {"Content-Type": "application/json", "api-key": key}
    return base, headers


def _qdrant_rest_req(method: str, path: str, body: Optional[dict] = None) -> Optional[dict]:
    """Выполняет HTTP-запрос к Qdrant REST API. Возвращает JSON-ответ или None при ошибке."""
    base, headers = _qdrant_rest_config()
    if not base:
        return None
    full_url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        print(f"⚠️ Qdrant HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"⚠️ Qdrant недоступен: {e}")
        return None


def _qdrant_rest_get_collections() -> List[str]:
    """Список имён коллекций."""
    out = _qdrant_rest_req("GET", "/collections")
    if not out or "result" not in out:
        return []
    return [c.get("name", "") for c in out.get("result", {}).get("collections", [])]


def _qdrant_rest_delete_collection(name: str) -> bool:
    """Удаляет коллекцию."""
    return _qdrant_rest_req("DELETE", f"/collections/{name}") is not None


def _qdrant_rest_create_collection(name: str, vector_size: int) -> bool:
    """Создаёт коллекцию с косинусной метрикой."""
    body = {"vectors": {"size": vector_size, "distance": "Cosine"}}
    return _qdrant_rest_req("PUT", f"/collections/{name}", body) is not None


def _qdrant_rest_upsert(collection: str, points: List[Dict]) -> bool:
    """Загружает точки. points: [{"id": int, "vector": [...], "payload": {...}}, ...]."""
    body = {"points": points}
    return _qdrant_rest_req("PUT", f"/collections/{collection}/points?wait=true", body) is not None


def _qdrant_rest_search(
    collection: str, vector: List[float], limit: int, score_threshold: float
) -> List[Dict]:
    """Поиск. Возвращает [{"score": float, "payload": {...}}, ...]."""
    body = {
        "vector": vector,
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
        "score_threshold": score_threshold,
    }
    out = _qdrant_rest_req("POST", f"/collections/{collection}/points/search", body)
    if not out or "result" not in out:
        return []
    return [
        {"score": h.get("score", 0.0), "payload": h.get("payload") or {}}
        for h in out.get("result", [])
    ]


def normalize_user_input(text: str) -> str:
    """
    Нормализация пользовательского ввода перед эмбеддингом: lower, strip, схлопывание пробелов.
    Опционально — простые замены частых опечаток.
    """
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = " ".join(t.split())
    # Простые замены опечаток (рус/лат и типичные ошибки)
    _typo_map = {
        "питон": "python",
        "пайтон": "python",
        "дата саенс": "data science",
        "машин лернинг": "machine learning",
    }
    for wrong, right in _typo_map.items():
        if wrong in t and right not in t:
            t = t.replace(wrong, right)
    return t


def _get_embedder():
    global _sentence_transformer
    if _sentence_transformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sentence_transformer = SentenceTransformer(Config.EMBED_MODEL_NAME)
        except Exception as e:
            raise RuntimeError(f"Не удалось загрузить модель эмбеддингов {Config.EMBED_MODEL_NAME}: {e}")
    return _sentence_transformer


def _load_skills_and_atlas() -> Tuple[List[Dict], List[Dict]]:
    """Загружает clean_skills.json и atlas_params_clean.json."""
    skills_path = Path(Config.SKILLS_FILE)
    atlas_path = Path(Config.ATLAS_FILE)
    if not skills_path.is_absolute():
        skills_path = Path(__file__).resolve().parent / skills_path
    if not atlas_path.is_absolute():
        atlas_path = Path(__file__).resolve().parent / atlas_path
    with open(skills_path, "r", encoding="utf-8") as f:
        skills = json.load(f)
    with open(atlas_path, "r", encoding="utf-8") as f:
        atlas = json.load(f)
    return skills, atlas


def _skill_to_text(s: Dict) -> str:
    """Один документ на навык: название + уровни + примеры задач (длина чанка ограничена)."""
    name = s.get("Навык") or s.get("name") or ""
    parts = [f"Навык: {name}."]
    max_example_len = 450
    for key in s:
        if "Skill level" in key or "Индикатор" in key:
            parts.append(f"{key}: {s[key]}")
        if "Пример задач" in key:
            parts.append(str(s[key])[:max_example_len])
    return " ".join(parts)


def _atlas_to_text(a: Dict) -> str:
    """Один документ на параметр атласа."""
    name = a.get("Параметр") or a.get("Parameter") or ""
    desc = a.get("Описание") or a.get("Description") or ""
    parts = [f"Параметр атласа: {name}. {desc}"]
    for grade in ["Младший", "Специалист", "Старший", "Ведущий", "Эксперт"]:
        if grade in a and a[grade]:
            parts.append(f"{grade}: {a[grade]}")
    return " ".join(parts)


def build_documents(
    skills: List[Dict],
    atlas: List[Dict],
    skill_cluster_map: Optional[Dict[str, int]] = None,
    cluster_labels: Optional[Dict[str, str]] = None,
) -> List[Tuple[str, Dict]]:
    """
    Возвращает список (text, payload).
    payload: type, name, profession (для skill); для skill при наличии — cluster_id, cluster_label.
    """
    skill_cluster_map = skill_cluster_map or {}
    cluster_labels = cluster_labels or {}
    docs = []
    for s in skills:
        name = s.get("Навык") or s.get("name") or ""
        if not name:
            continue
        text = _skill_to_text(s)
        prof = s.get("Профессия (лист)") or s.get("Профессия") or s.get("Привязка к профессии") or ""
        if isinstance(prof, list):
            prof = prof[0] if prof else ""
        payload = {"type": "skill", "name": name, "profession": prof}
        cid = skill_cluster_map.get(name)
        if cid is not None:
            payload["cluster_id"] = cid
            payload["cluster_label"] = cluster_labels.get(str(cid), f"Трек {cid}")
        docs.append((text, payload))
    for a in atlas:
        name = a.get("Параметр") or a.get("Parameter") or ""
        if not name:
            continue
        text = _atlas_to_text(a)
        docs.append((text, {"type": "atlas", "name": name}))
    return docs


def _load_or_build_skill_clusters(skills: List[Dict]) -> Tuple[Dict[str, int], Dict[str, str]]:
    """
    Загружает skill_clusters.json или строит кластеры по эмбеддингам навыков и сохраняет файл.
    Возвращает (skill_name -> cluster_id, cluster_id -> label).
    """
    skills_path = Path(Config.SKILLS_FILE)
    if not skills_path.is_absolute():
        skills_path = Path(__file__).resolve().parent / skills_path
    clusters_path = skills_path.parent / "skill_clusters.json"
    if clusters_path.exists():
        try:
            with open(clusters_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            skills_map = data.get("skills") or {}
            labels = {str(k): v for k, v in (data.get("labels") or {}).items()}
            return skills_map, labels
        except Exception:
            pass
    # Построить кластеры
    try:
        from sklearn.cluster import KMeans
    except ImportError:
        return {}, {}
    names = []
    texts = []
    for s in skills:
        name = s.get("Навык") or s.get("name") or ""
        if not name:
            continue
        names.append(name)
        texts.append(_skill_to_text(s))
    if len(names) < 3:
        return {}, {}
    embedder = _get_embedder()
    vectors = embedder.encode(texts, normalize_embeddings=True)
    n_clusters = min(25, max(2, len(names) // 5))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels_arr = kmeans.fit_predict(vectors)
    skill_to_id = {names[i]: int(labels_arr[i]) for i in range(len(names))}
    id_to_label = {}
    for cid in range(n_clusters):
        in_c = [names[i] for i in range(len(names)) if labels_arr[i] == cid]
        id_to_label[cid] = in_c[0] if in_c else f"Трек {cid}"
    to_save = {"skills": skill_to_id, "labels": {str(k): v for k, v in id_to_label.items()}}
    try:
        with open(clusters_path, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=0)
    except Exception:
        pass
    return skill_to_id, {str(k): v for k, v in id_to_label.items()}


def build_index(force_recreate: bool = False) -> Optional[int]:
    """
    Строит индекс RAG из skills + atlas, загружает в Qdrant через REST.
    Возвращает число загруженных точек или None при ошибке.
    """
    if not _qdrant_rest_config()[0]:
        return None
    embedder = _get_embedder()
    skills, atlas = _load_skills_and_atlas()
    skill_cluster_map, cluster_labels = _load_or_build_skill_clusters(skills)
    docs = build_documents(skills, atlas, skill_cluster_map, cluster_labels)
    texts = [t for t, _ in docs]
    payloads = [p for _, p in docs]
    vectors = embedder.encode(texts, normalize_embeddings=True)
    vector_size = int(vectors.shape[1])
    collection = Config.RAG_COLLECTION_NAME
    try:
        existing = _qdrant_rest_get_collections()
        if collection in existing:
            if force_recreate:
                _qdrant_rest_delete_collection(collection)
                existing = _qdrant_rest_get_collections()
        if collection not in existing:
            if not _qdrant_rest_create_collection(collection, vector_size):
                return None
        points = [
            {
                "id": idx,
                "vector": vectors[idx].tolist(),
                "payload": {"text": texts[idx], **payloads[idx]},
            }
            for idx in range(len(texts))
        ]
        if not _qdrant_rest_upsert(collection, points):
            return None
        return len(points)
    except Exception as e:
        print(f"⚠️ Ошибка построения индекса RAG: {e}")
        return None


def retrieve(query: str, top_k: Optional[int] = None, score_threshold: Optional[float] = None) -> List[Dict]:
    """
    Векторный поиск по индексу RAG (через REST).
    Возвращает список { "score": float, "payload": { "text", "type", "name", ... } }.
    """
    query = normalize_user_input(query or "")
    top_k = top_k if top_k is not None else Config.RAG_TOP_K
    score_threshold = score_threshold if score_threshold is not None else Config.RAG_SCORE_THRESHOLD
    if not _qdrant_rest_config()[0]:
        return []
    embedder = _get_embedder()
    qvec = embedder.encode([query], normalize_embeddings=True)[0].tolist()
    try:
        return _qdrant_rest_search(
            Config.RAG_COLLECTION_NAME, qvec, limit=top_k, score_threshold=score_threshold
        )
    except Exception as e:
        print(f"⚠️ Ошибка поиска RAG: {e}")
        return []


def get_rag_context_for_plan(step1_summary: str, target_name: str, top_k: Optional[int] = None) -> str:
    """
    Формирует контекст для LLM из RAG по диагностике и цели.
    """
    query = f"Разрывы и цели: {step1_summary[:1500]}. Целевая роль: {target_name}."
    hits = retrieve(query, top_k=top_k or Config.RAG_TOP_K)
    if not hits:
        return ""
    parts = []
    for h in hits:
        p = h.get("payload") or {}
        text = p.get("text", "")
        name = p.get("name", "")
        typ = p.get("type", "")
        if text:
            parts.append(f"[{typ}: {name}]\n{text[:600]}")
    return "\n\n---\n\n".join(parts[:15])


def suggest_skills(user_input: str, top_k: Optional[int] = None) -> List[str]:
    """
    Подсказки «возможно, вы имели в виду» по вводу пользователя.
    Возвращает только те подсказки, у которых score >= SUGGESTIONS_MIN_SCORE.
    """
    normalized = normalize_user_input(user_input or "")
    if not normalized:
        return []
    top_k = top_k or Config.SKILL_SUGGESTIONS_TOP_K
    min_score = getattr(Config, "SUGGESTIONS_MIN_SCORE", 0.35)
    hits = retrieve(normalized, top_k=top_k * 2, score_threshold=min_score)
    seen = set()
    result = []
    for h in hits:
        if (h.get("score") or 0) < min_score:
            continue
        p = h.get("payload") or {}
        if p.get("type") != "skill":
            continue
        name = p.get("name", "").strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
            if len(result) >= top_k:
                break
    return result


def _clean_skill_snippet(text: str, name: str, max_len: int = 100) -> str:
    """Убирает из текста чанка служебные поля (Skill level \\ Индикатор...) и оставляет короткое описание."""
    import re
    if not text:
        return ""
    # Убираем начало "Навык: Name."
    t = re.sub(r"^Навык:\s*[^.]*\.\s*", "", text, flags=re.IGNORECASE)
    # Убираем блоки "Skill level \ Индикатор - Basic: ..." и оставляем только описание после двоеточия
    t = re.sub(r"Skill level\s*\\+\s*Индикатор\s*-\s*(?:Basic|Proficiency|Advanced)\s*:\s*", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"Параметр атласа:\s*[^.]*\.\s*", "", t, flags=re.IGNORECASE)
    t = " ".join(t.split()).strip()
    if len(t) > max_len:
        t = t[: max_len].rsplit(" ", 1)[0] + "…"
    return t or name


def get_rag_explanation_for_gap(name: str, is_skill: bool = True) -> str:
 
    if not (name and str(name).strip()):
        return ""
    if not _qdrant_rest_config()[0]:
        return ""
    queries = [
        f"{name} развитие компетенции" if is_skill else f"параметр {name} развитие ожидания",
        name.strip(),
    ]
    best_desc = ""
    best_score = 0.0
    for query in queries:
        hits = retrieve(query, top_k=2, score_threshold=0.25)
        for h in hits:
            score = h.get("score") or 0
            if score < best_score:
                continue
            p = h.get("payload") or {}
            raw = (p.get("text") or "").strip()
            if not raw:
                continue
            desc = _clean_skill_snippet(raw, name, max_len=120)
            if desc and score > best_score:
                best_score = score
                best_desc = desc
    return best_desc


def get_rag_why_role(user_skills: Dict[str, int], role_display: str, top_k: int = 4) -> str:
    """
    Для сценария «Исследование»: запрос к RAG по навыкам пользователя и роли.
    Возвращает короткий текст «почему подходит» — только названия навыков и краткие описания без служебных полей.
    """
    if not _qdrant_rest_config()[0]:
        return ""
    skills_text = ", ".join(user_skills.keys()) if user_skills else "не указаны"
    # Роль без грейда для запроса
    role_name = role_display.split(" (")[0] if " (" in role_display else role_display
    query = f"Навыки пользователя: {skills_text}. Профессия: {role_name}. Какие навыки из базы релевантны?"
    hits = retrieve(query, top_k=top_k, score_threshold=0.3)
    if not hits:
        return ""
    parts = []
    seen_names = set()
    for h in hits:
        p = h.get("payload") or {}
        name = (p.get("name") or "").strip()
        typ = p.get("type", "")
        raw = (p.get("text") or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        desc = _clean_skill_snippet(raw, name, max_len=100)
        parts.append(f"• {name}: {desc}" if desc else f"• {name}")
        if len(parts) >= 3:
            break
    return " Релевантные навыки из базы: " + " ".join(parts) if parts else ""


def get_rag_why_role_bullets(user_skills: Dict[str, int], role_display: str, top_k: int = 5) -> List[str]:
    """Возвращает 3–5 коротких пунктов «почему подходит» для карточки Explore."""
    if not _qdrant_rest_config()[0]:
        return []
    skills_text = ", ".join(user_skills.keys()) if user_skills else "не указаны"
    role_name = role_display.split(" (")[0] if " (" in role_display else role_display
    query = f"Навыки пользователя: {skills_text}. Профессия: {role_name}. Какие навыки из базы релевантны?"
    hits = retrieve(query, top_k=top_k, score_threshold=0.3)
    if not hits:
        return []
    bullets = []
    seen_names = set()
    for h in hits:
        p = h.get("payload") or {}
        name = (p.get("name") or "").strip()
        raw = (p.get("text") or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        desc = _clean_skill_snippet(raw, name, max_len=80)
        bullets.append(f"{name}: {desc}" if desc else name)
        if len(bullets) >= 5:
            break
    return bullets


def map_to_canonical_skill(user_input: str) -> Optional[str]:
    """
    Маппинг ввода на канонический навык только при высокой семантической близости (синонимы).
    Иначе возвращает None — оставляем «свой навык» как есть.
    """
    normalized = normalize_user_input(user_input or "")
    if not normalized:
        return None
    threshold = Config.SKILL_MAP_SIMILARITY_THRESHOLD
    hits = retrieve(normalized, top_k=1, score_threshold=threshold)
    if not hits:
        return None
    p = hits[0].get("payload") or {}
    if p.get("type") != "skill":
        return None
    return (p.get("name") or "").strip() or None


def rank_opportunities(
    user_skills: Dict[str, int],
    opportunities: List[Dict],
    data_loader: Any,
) -> List[Dict]:
    """
    Семантическое ранжирование списка возможностей (Исследование).
    user_skills: { skill_name: level }; opportunities: список с полями role, match, internal_role.
    Добавляет/обновляет поле semantic_score и сортирует по нему (при равном — по match).
    """
    if not opportunities:
        return []
    try:
        embedder = _get_embedder()
    except Exception:
        return opportunities
    # Текст профиля пользователя
    profile_parts = [f"{name} (уровень {lvl})" for name, lvl in user_skills.items()]
    profile_text = " ".join(profile_parts) or "Нет навыков"
    try:
        profile_vec = embedder.encode([profile_text], normalize_embeddings=True)[0]
    except Exception:
        return opportunities
    # Для каждой возможности: текст требований роли
    role_texts = []
    for opp in opportunities:
        internal = opp.get("internal_role")
        role_display = opp.get("role", "")
        grade = "Middle"
        if "(" in role_display and ")" in role_display:
            grade = role_display.split("(")[-1].replace(")", "").strip()
        reqs = data_loader.get_role_requirements(internal, grade) if internal else {}
        req_text = " ".join(reqs.keys()) if reqs else role_display
        role_texts.append(req_text)
    if not role_texts:
        return opportunities
    try:
        role_vecs = embedder.encode(role_texts, normalize_embeddings=True)
    except Exception:
        return opportunities
    import numpy as np
    scores = np.dot(role_vecs, profile_vec)
    for i, opp in enumerate(opportunities):
        opp["semantic_score"] = float(scores[i]) if i < len(scores) else 0.0
    opportunities.sort(key=lambda x: (-x.get("semantic_score", 0), -x.get("match", 0)))
    return opportunities


def get_embedder():
    """Доступ к эмбеддеру для внешних модулей."""
    return _get_embedder()


# --- Semantic skill matching ---

_skill_embeddings_cache: Optional[Dict[str, Any]] = None


def _get_skill_embeddings(skill_names: List[str]) -> Dict[str, Any]:
    """Кеширует эмбеддинги для списка навыков."""
    global _skill_embeddings_cache
    if _skill_embeddings_cache is not None:
        return _skill_embeddings_cache
    try:
        embedder = _get_embedder()
        import numpy as np
        names = list(skill_names)
        vecs = embedder.encode(names, normalize_embeddings=True, show_progress_bar=False)
        _skill_embeddings_cache = {name: vec for name, vec in zip(names, vecs)}
        return _skill_embeddings_cache
    except Exception:
        return {}


def semantic_match_skills(
    user_skill_names: List[str],
    required_skill_names: List[str],
    threshold: Optional[float] = None,
) -> Dict[str, str]:
    """Для каждого user-навыка находит ближайший required-навык по embedding similarity.
    Возвращает {user_name: matched_required_name} для пар с score >= threshold.
    Пары выбираются жадно: один required-навык может быть сопоставлен только одному user-навыку."""
    threshold = threshold or Config.SKILL_MATCH_THRESHOLD
    if not user_skill_names or not required_skill_names:
        return {}
    try:
        embedder = _get_embedder()
        import numpy as np
    except Exception:
        return {}
    try:
        user_vecs = embedder.encode(user_skill_names, normalize_embeddings=True, show_progress_bar=False)
        req_vecs = embedder.encode(required_skill_names, normalize_embeddings=True, show_progress_bar=False)
        sim_matrix = np.dot(user_vecs, req_vecs.T)

        result = {}
        used_req = set()
        pairs = []
        for i in range(len(user_skill_names)):
            for j in range(len(required_skill_names)):
                if sim_matrix[i, j] >= threshold:
                    pairs.append((sim_matrix[i, j], i, j))
        pairs.sort(key=lambda x: -x[0])

        for score, i, j in pairs:
            u_name = user_skill_names[i]
            r_name = required_skill_names[j]
            if u_name in result or r_name in used_req:
                continue
            result[u_name] = r_name
            used_req.add(r_name)

        return result
    except Exception:
        return {}


def compute_profile_similarity(user_skill_names: List[str], role_skill_names: List[str]) -> float:
    """Cosine similarity между средним эмбеддингом профиля пользователя и профиля роли."""
    if not user_skill_names or not role_skill_names:
        return 0.0
    try:
        embedder = _get_embedder()
        import numpy as np
        u_vecs = embedder.encode(user_skill_names, normalize_embeddings=True, show_progress_bar=False)
        r_vecs = embedder.encode(role_skill_names, normalize_embeddings=True, show_progress_bar=False)
        u_mean = np.mean(u_vecs, axis=0)
        r_mean = np.mean(r_vecs, axis=0)
        u_mean = u_mean / (np.linalg.norm(u_mean) + 1e-9)
        r_mean = r_mean / (np.linalg.norm(r_mean) + 1e-9)
        return float(np.dot(u_mean, r_mean))
    except Exception:
        return 0.0

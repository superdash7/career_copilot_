
"""RAG и NLP: индексация навыков/атласа, поиск, подсказки навыков, семантическое ранжирование."""

import json
import threading
import urllib.request
import urllib.error
from collections import OrderedDict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, AbstractSet

from config import Config

# Ленивая загрузка тяжёлых зависимостей (отдельно по model_name)
_sentence_transformers: Dict[str, Any] = {}
_cross_encoder = None

# SentenceTransformer.encode is not reliably thread-safe; explore uses a thread pool.
_encode_lock = threading.Lock()

# (internal_role, grade) -> (tuple of skill names in encode order, passage embeddings matrix)
_role_requirement_emb_cache: "OrderedDict[Tuple[str, str], Tuple[Tuple[str, ...], Any]]" = OrderedDict()
_role_req_emb_lock = threading.Lock()
_ROLE_REQ_EMB_CACHE_MAX = 512

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


def _tokenize_for_lexical(text: str) -> List[str]:
    """Простая токенизация для lexical scoring (без внешних зависимостей)."""
    import re

    normalized = normalize_user_input(text or "")
    if not normalized:
        return []
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9+#]+", normalized, flags=re.UNICODE)
    return [t for t in tokens if len(t) >= 2]


def _lexical_jaccard(query: str, candidate: str) -> float:
    """Hybrid lexical: rapidfuzz token_sort_ratio + Jaccard on tokens."""
    from rapidfuzz import fuzz as _rfuzz

    nq = normalize_user_input(query or "")
    nc = normalize_user_input(candidate or "")
    if not nq or not nc:
        return 0.0

    token_sort = _rfuzz.token_sort_ratio(nq, nc) / 100.0

    q_tok = set(_tokenize_for_lexical(query))
    c_tok = set(_tokenize_for_lexical(candidate))
    if q_tok and c_tok:
        jaccard = len(q_tok & c_tok) / len(q_tok | c_tok)
    else:
        jaccard = 0.0

    return 0.6 * token_sort + 0.4 * jaccard


def _rrf_rank_fusion(dense_rank: int, lexical_rank: int, rrf_k: float) -> float:
    """
    Reciprocal Rank Fusion:
    score = 1/(k+rank_dense) + 1/(k+rank_lexical)
    """
    return (1.0 / (rrf_k + dense_rank)) + (1.0 / (rrf_k + lexical_rank))


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is not None:
        return _cross_encoder
    model_name = (getattr(Config, "SKILLS_CROSS_ENCODER_MODEL", "") or "").strip()
    if not model_name:
        return None
    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(model_name)
        return _cross_encoder
    except Exception:
        return None


def _cross_encoder_rerank(query: str, candidates: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    ce = _get_cross_encoder()
    if ce is None or not candidates:
        return candidates[:top_n]
    try:
        pairs = [(query, c.get("name", "")) for c in candidates]
        ce_scores = ce.predict(pairs)
        enriched = []
        for c, score in zip(candidates, ce_scores):
            row = dict(c)
            row["cross_encoder_score"] = float(score)
            row["score"] = 0.6 * float(row.get("score", 0.0)) + 0.4 * float(score)
            row["retrieval_mode"] = "hybrid_cross_encoder"
            enriched.append(row)
        enriched.sort(key=lambda x: -float(x.get("score", 0.0)))
        return enriched[:top_n]
    except Exception:
        return candidates[:top_n]


def _prepare_skills_cache() -> List[Dict[str, str]]:
    """
    Лёгкий кэш канонических навыков для lexical re-rank/fallback.
    Формат: [{"name": "...", "profession": "..."}]
    """
    skills, _ = _load_skills_and_atlas()
    out: List[Dict[str, str]] = []
    seen = set()
    for s in skills:
        name = (s.get("Навык") or s.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        profession = s.get("Профессия (лист)") or s.get("Профессия") or s.get("Привязка к профессии") or ""
        if isinstance(profession, list):
            profession = profession[0] if profession else ""
        out.append({"name": name, "profession": str(profession or "")})
    return out


_skills_cache: Optional[List[Dict[str, str]]] = None


def _get_skills_cache() -> List[Dict[str, str]]:
    global _skills_cache
    if _skills_cache is not None:
        return _skills_cache
    _skills_cache = _prepare_skills_cache()
    return _skills_cache


def _lexical_skill_candidates(
    user_input: str,
    top_k: int,
    min_score: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Возвращает lexical-кандидаты с payload-like структурой:
    [{"score": float, "payload": {"name": "...", "profession": "...", "type": "skill"}}]
    """
    query = normalize_user_input(user_input or "")
    if not query:
        return []
    rows = _get_skills_cache()
    scored: List[Tuple[float, Dict[str, str]]] = []
    for row in rows:
        name = row.get("name", "")
        score = _lexical_jaccard(query, name)
        if score < min_score:
            continue
        scored.append((score, row))
    scored.sort(key=lambda x: -x[0])
    out: List[Dict[str, Any]] = []
    for score, row in scored[: max(top_k, 1)]:
        out.append(
            {
                "score": float(score),
                "payload": {
                    "type": "skill",
                    "name": row.get("name", ""),
                    "profession": row.get("profession", ""),
                },
            }
        )
    return out


def _dense_skill_candidates(
    user_input: str,
    top_k: int,
    score_threshold: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Dense-кандидаты из skills_v2 в payload-like формате."""
    hits = search_skills_v2(user_input, top_k=top_k, score_threshold=score_threshold)
    out: List[Dict[str, Any]] = []
    for h in hits:
        payload = h.get("payload") or {}
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "score": float(h.get("score") or 0.0),
                "payload": {
                    "type": "skill",
                    "name": name,
                    "profession": payload.get("profession", ""),
                },
            }
        )
    return out


def _get_embedder(model_name: Optional[str] = None):
    model = model_name or Config.EMBED_MODEL_NAME
    if model in _sentence_transformers:
        return _sentence_transformers[model]
    try:
        from sentence_transformers import SentenceTransformer
        _sentence_transformers[model] = SentenceTransformer(model)
    except Exception as e:
        raise RuntimeError(f"Не удалось загрузить модель эмбеддингов {model}: {e}")
    return _sentence_transformers[model]


def _encode_texts(
    texts: List[str],
    model_name: Optional[str] = None,
    normalize: bool = True,
    show_progress_bar: bool = False,
):
    embedder = _get_embedder(model_name=model_name)
    with _encode_lock:
        return embedder.encode(texts, normalize_embeddings=normalize, show_progress_bar=show_progress_bar)


def _cached_role_passage_embeddings(
    role_key: Tuple[str, str],
    required_skill_names: List[str],
    explore_fast: bool = False,
) -> Any:
    """Passage-side embeddings for one role×grade; reused by semantic_match + profile_sim in explore."""
    names_t = tuple(required_skill_names)
    cache_key = (role_key[0], role_key[1], explore_fast)
    with _role_req_emb_lock:
        hit = _role_requirement_emb_cache.get(cache_key)
        if hit is not None and hit[0] == names_t:
            _role_requirement_emb_cache.move_to_end(cache_key)
            return hit[1]
    req_vecs = _encode_for_matching(
        list(required_skill_names), is_query=False, explore_fast=explore_fast
    )
    with _role_req_emb_lock:
        _role_requirement_emb_cache[cache_key] = (names_t, req_vecs)
        _role_requirement_emb_cache.move_to_end(cache_key)
        while len(_role_requirement_emb_cache) > _ROLE_REQ_EMB_CACHE_MAX:
            _role_requirement_emb_cache.popitem(last=False)
    return req_vecs


def _e5_query_text(raw_skill: str) -> str:
    return (
        "Instruct: Retrieve the canonical skill name matching this resume phrase\n"
        f"Query: {raw_skill}"
    )


def _e5_passage_text(canonical_name: str) -> str:
    return f"passage: {canonical_name}"


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
    embedder = _get_embedder(model_name=Config.EMBED_MODEL_NAME)
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
    embedder = _get_embedder(model_name=Config.EMBED_MODEL_NAME)
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


def build_skills_v2_index(force_recreate: bool = False) -> Optional[int]:
    """
    Строит индекс только канонических названий навыков для E5-инференса.
    Коллекция: Config.SKILLS_V2_COLLECTION_NAME.
    """
    if not _qdrant_rest_config()[0]:
        return None
    try:
        skills, _ = _load_skills_and_atlas()
        names = []
        payloads = []
        for s in skills:
            name = (s.get("Навык") or s.get("name") or "").strip()
            if not name:
                continue
            profession = s.get("Профессия (лист)") or s.get("Профессия") or s.get("Привязка к профессии") or ""
            if isinstance(profession, list):
                profession = profession[0] if profession else ""
            names.append(name)
            payloads.append({"type": "skill", "name": name, "profession": profession})

        if not names:
            return 0

        texts = [_e5_passage_text(n) for n in names]
        vectors = _encode_texts(texts, model_name=Config.EMBED_MODEL_NAME_V2, normalize=True)
        vector_size = int(vectors.shape[1])
        collection = Config.SKILLS_V2_COLLECTION_NAME

        existing = _qdrant_rest_get_collections()
        if collection in existing and force_recreate:
            _qdrant_rest_delete_collection(collection)
            existing = _qdrant_rest_get_collections()
        if collection not in existing:
            if not _qdrant_rest_create_collection(collection, vector_size):
                return None

        points = []
        for idx, name in enumerate(names):
            points.append(
                {
                    "id": idx,
                    "vector": vectors[idx].tolist(),
                    "payload": payloads[idx],
                }
            )
        if not _qdrant_rest_upsert(collection, points):
            return None
        return len(points)
    except Exception as e:
        print(f"⚠️ Ошибка построения индекса skills_v2: {e}")
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
    embedder = _get_embedder(model_name=Config.EMBED_MODEL_NAME)
    qvec = embedder.encode([query], normalize_embeddings=True)[0].tolist()
    try:
        return _qdrant_rest_search(
            Config.RAG_COLLECTION_NAME, qvec, limit=top_k, score_threshold=score_threshold
        )
    except Exception as e:
        print(f"⚠️ Ошибка поиска RAG: {e}")
        return []


def search_skills_v2(
    user_input: str,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
) -> List[Dict]:
    """
    Поиск канонических навыков в E5-коллекции skills_v2.
    Возвращает [{"score": float, "payload": {...}}, ...].
    """
    normalized = normalize_user_input(user_input or "")
    if not normalized:
        return []
    if not _qdrant_rest_config()[0]:
        return []
    query = _e5_query_text(normalized)
    top_k = top_k if top_k is not None else Config.SKILLS_V2_TOP_K
    threshold = (
        score_threshold
        if score_threshold is not None
        else Config.SKILLS_V2_SCORE_THRESHOLD
    )
    try:
        qvec = _encode_texts([query], model_name=Config.EMBED_MODEL_NAME_V2, normalize=True)[0].tolist()
        return _qdrant_rest_search(
            Config.SKILLS_V2_COLLECTION_NAME,
            qvec,
            limit=top_k,
            score_threshold=threshold,
        )
    except Exception as e:
        print(f"⚠️ Ошибка поиска skills_v2: {e}")
        return []


def get_skills_v2_candidates(
    user_input: str,
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
    retrieval_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval для навыков:
    - dense: E5/Qdrant
    - lexical: Jaccard по токенам имени навыка
    - fusion: RRF + weighted blend
    """
    mode = (retrieval_mode or Config.SKILLS_RETRIEVAL_MODE or "hybrid_rerank").strip().lower()
    requested_top_k = top_k or Config.SKILLS_V2_TOP_K
    dense_fetch_k = max(requested_top_k * 4, requested_top_k + 5)
    dense_hits = _dense_skill_candidates(user_input, top_k=dense_fetch_k, score_threshold=score_threshold)
    lexical_hits = _lexical_skill_candidates(user_input, top_k=dense_fetch_k)

    if mode == "dense_only":
        return [
            {
                "name": (h.get("payload") or {}).get("name", ""),
                "score": float(h.get("score") or 0.0),
                "dense_score": float(h.get("score") or 0.0),
                "lexical_score": 0.0,
                "retrieval_mode": "dense_only",
            }
            for h in dense_hits[:requested_top_k]
            if (h.get("payload") or {}).get("name")
        ]
    if mode == "lexical_only":
        return [
            {
                "name": (h.get("payload") or {}).get("name", ""),
                "score": float(h.get("score") or 0.0),
                "dense_score": 0.0,
                "lexical_score": float(h.get("score") or 0.0),
                "retrieval_mode": "lexical_only",
            }
            for h in lexical_hits[:requested_top_k]
            if (h.get("payload") or {}).get("name")
        ]

    by_name: Dict[str, Dict[str, Any]] = {}
    dense_rank = 1
    for h in dense_hits:
        payload = h.get("payload") or {}
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        row = by_name.setdefault(
            name,
            {
                "name": name,
                "dense_score": 0.0,
                "lexical_score": 0.0,
                "dense_rank": dense_fetch_k + 1,
                "lexical_rank": dense_fetch_k + 1,
            },
        )
        row["dense_score"] = max(float(h.get("score") or 0.0), row["dense_score"])
        row["dense_rank"] = min(int(row["dense_rank"]), dense_rank)
        dense_rank += 1

    lexical_rank = 1
    for h in lexical_hits:
        payload = h.get("payload") or {}
        name = (payload.get("name") or "").strip()
        if not name:
            continue
        row = by_name.setdefault(
            name,
            {
                "name": name,
                "dense_score": 0.0,
                "lexical_score": 0.0,
                "dense_rank": dense_fetch_k + 1,
                "lexical_rank": dense_fetch_k + 1,
            },
        )
        row["lexical_score"] = max(float(h.get("score") or 0.0), row["lexical_score"])
        row["lexical_rank"] = min(int(row["lexical_rank"]), lexical_rank)
        lexical_rank += 1

    if not by_name:
        return []

    dense_weight = float(getattr(Config, "SKILLS_HYBRID_DENSE_WEIGHT", 0.7))
    lexical_weight = float(getattr(Config, "SKILLS_HYBRID_LEXICAL_WEIGHT", 0.3))
    rrf_k = float(getattr(Config, "SKILLS_HYBRID_RRF_K", 60.0))
    cross_encoder_model = (getattr(Config, "SKILLS_CROSS_ENCODER_MODEL", "") or "").strip()
    min_score = float(getattr(Config, "SKILLS_HYBRID_MIN_SCORE", 0.3))

    fused_rows: List[Dict[str, Any]] = []
    for row in by_name.values():
        dense_score = float(row.get("dense_score", 0.0))
        lexical_score = float(row.get("lexical_score", 0.0))
        d_rank = int(row.get("dense_rank", dense_fetch_k + 1))
        l_rank = int(row.get("lexical_rank", dense_fetch_k + 1))
        rrf = _rrf_rank_fusion(d_rank, l_rank, rrf_k=rrf_k)
        hybrid_score = (
            dense_weight * dense_score
            + lexical_weight * lexical_score
            + 0.15 * rrf
        )
        fused_rows.append(
            {
                "name": row["name"],
                "score": float(hybrid_score),
                "dense_score": dense_score,
                "lexical_score": lexical_score,
                "retrieval_mode": "hybrid_rerank",
                "retrieval_components": {
                    "dense_rank": d_rank,
                    "lexical_rank": l_rank,
                    "rrf": float(rrf),
                },
            }
        )

    fused_rows.sort(
        key=lambda x: (
            -float(x.get("score", 0.0)),
            -float(x.get("dense_score", 0.0)),
            -float(x.get("lexical_score", 0.0)),
        )
    )
    if cross_encoder_model and fused_rows:
        try:
            rerank_n = max(1, min(len(fused_rows), int(getattr(Config, "SKILLS_HYBRID_RERANK_TOP_N", 20))))
            reranked = _cross_encoder_rerank(
                query=user_input,
                candidates=fused_rows[:rerank_n],
                top_n=rerank_n,
            )
            tail = fused_rows[rerank_n:]
            fused_rows = reranked + tail
        except Exception:
            pass
    filtered = [x for x in fused_rows if float(x.get("score", 0.0)) >= min_score]
    if not filtered:
        filtered = fused_rows
    return filtered[:requested_top_k]


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
    # Приоритет: новая коллекция skills_v2 (E5), fallback: legacy RAG.
    hits = search_skills_v2(normalized, top_k=top_k * 2, score_threshold=min_score)
    if not hits:
        hits = retrieve(normalized, top_k=top_k * 2, score_threshold=min_score)
    seen = set()
    result = []
    for h in hits:
        if (h.get("score") or 0) < min_score:
            continue
        p = h.get("payload") or {}
        if p.get("type") not in ("skill", "", None):
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


def get_rag_why_role_bullets(
    user_skills: Dict[str, int],
    role_display: str,
    top_k: int = 5,
    atlas_keys: Optional[AbstractSet[str]] = None,
) -> List[str]:
    """Возвращает 3–5 коротких пунктов «почему подходит» для карточки Explore."""
    if not _qdrant_rest_config()[0]:
        return []
    if user_skills:
        if atlas_keys is None:
            names = list(user_skills.keys())
        else:
            names = [k for k in user_skills if k not in atlas_keys]
        skills_text = ", ".join(names[:40]) if names else "не указаны"
    else:
        skills_text = "не указаны"
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

    # 1) Пытаемся через новую E5-коллекцию skills_v2.
    hits = search_skills_v2(normalized, top_k=1, score_threshold=threshold)
    if hits:
        p = hits[0].get("payload") or {}
        name = (p.get("name") or "").strip()
        if name:
            return name

    # 2) Fallback: старая коллекция MiniLM.
    hits = retrieve(normalized, top_k=1, score_threshold=threshold)
    if hits:
        p = hits[0].get("payload") or {}
        if p.get("type") == "skill":
            return (p.get("name") or "").strip() or None
    return None


def map_to_canonical_skill_v2(
    user_input: str,
    openai_client: Any = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Top-K retrieval + LLM reranking.
    Returns: {canonical_name, confidence, source} or {canonical_name: None}.
    Falls back to map_to_canonical_skill if LLM is unavailable.
    """
    normalized = normalize_user_input(user_input or "")
    if not normalized:
        return {"canonical_name": None, "confidence": 0.0, "source": "empty_input"}

    # Step 1: exact synonym match (fast path)
    try:
        from skill_normalizer import resolve_to_canonical
        exact = resolve_to_canonical(normalized)
        if exact:
            return {"canonical_name": exact, "confidence": 1.0, "source": "exact_match"}
    except Exception:
        pass

    # Step 2: Top-K from Qdrant (no threshold cutoff)
    hits = search_skills_v2(normalized, top_k=top_k, score_threshold=0.2)
    if not hits:
        hits_legacy = retrieve(normalized, top_k=top_k, score_threshold=0.2)
        hits = [h for h in hits_legacy if (h.get("payload") or {}).get("type") == "skill"]

    if not hits:
        return {"canonical_name": None, "confidence": 0.0, "source": "not_found"}

    # High confidence — skip LLM
    best = hits[0]
    best_name = (best.get("payload") or {}).get("name", "").strip()
    best_score = float(best.get("score", 0))
    if best_score > 0.92 and best_name:
        return {"canonical_name": best_name, "confidence": best_score, "source": "high_confidence_vector"}

    # Step 3: LLM reranker for ambiguous cases
    if not openai_client:
        if best_score >= Config.SKILL_MAP_SIMILARITY_THRESHOLD and best_name:
            return {"canonical_name": best_name, "confidence": best_score, "source": "vector_threshold"}
        return {"canonical_name": None, "confidence": best_score, "source": "below_threshold_no_llm"}

    candidates = []
    for i, h in enumerate(hits[:top_k]):
        p = h.get("payload") or {}
        name = (p.get("name") or "").strip()
        score = float(h.get("score", 0))
        if name:
            candidates.append((name, score))

    if not candidates:
        return {"canonical_name": None, "confidence": 0.0, "source": "no_candidates"}

    candidate_lines = [f"{i+1}. {name} (similarity: {score:.2f})" for i, (name, score) in enumerate(candidates)]
    rerank_prompt = (
        f'Пользователь указал навык: "{user_input}"\n\n'
        f"Кандидаты из базы навыков:\n"
        + "\n".join(candidate_lines)
        + f"\n\nВыбери номер кандидата (1-{len(candidates)}), который лучше всего соответствует навыку. "
        f"Если ни один не подходит — ответь 0. Только число."
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": rerank_prompt}],
            max_tokens=5,
            temperature=0,
        )
        choice_str = (response.choices[0].message.content or "").strip()
        choice = int(choice_str)
    except (ValueError, TypeError):
        choice = 0
    except Exception:
        if best_score >= Config.SKILL_MAP_SIMILARITY_THRESHOLD and best_name:
            return {"canonical_name": best_name, "confidence": best_score, "source": "vector_fallback_llm_error"}
        return {"canonical_name": None, "confidence": 0.0, "source": "llm_error"}

    if choice < 1 or choice > len(candidates):
        return {"canonical_name": None, "confidence": 0.0, "source": "no_match_llm"}

    selected_name, selected_score = candidates[choice - 1]
    return {"canonical_name": selected_name, "confidence": selected_score, "source": "llm_reranked"}


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
        embedder = _get_embedder(model_name=Config.EMBED_MODEL_NAME)
    except Exception:
        return opportunities
    # Текст профиля пользователя (без параметров атласа — они общие для всех ролей и раздувают текст)
    atlas_keys = getattr(data_loader, "atlas_map", None) or {}
    profile_parts = [
        f"{name} (уровень {lvl})"
        for name, lvl in user_skills.items()
        if name not in atlas_keys
    ]
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
        req_skill_keys = [k for k in reqs if k not in atlas_keys]
        req_text = " ".join(req_skill_keys) if req_skill_keys else role_display
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
    return _get_embedder(model_name=Config.EMBED_MODEL_NAME)


# --- Semantic skill matching ---

_skill_embeddings_cache: Optional[Dict[str, Any]] = None


def _get_skill_embeddings(skill_names: List[str]) -> Dict[str, Any]:
    """Кеширует эмбеддинги для списка навыков (E5-large для точности)."""
    global _skill_embeddings_cache
    if _skill_embeddings_cache is not None:
        return _skill_embeddings_cache
    try:
        import numpy as np
        names = list(skill_names)
        texts = [_e5_passage_text(n) for n in names]
        vecs = _encode_texts(texts, model_name=Config.EMBED_MODEL_NAME_V2, normalize=True)
        _skill_embeddings_cache = {name: vec for name, vec in zip(names, vecs)}
        return _skill_embeddings_cache
    except Exception:
        try:
            embedder = _get_embedder(model_name=Config.EMBED_MODEL_NAME)
            import numpy as np
            names = list(skill_names)
            vecs = embedder.encode(names, normalize_embeddings=True, show_progress_bar=False)
            _skill_embeddings_cache = {name: vec for name, vec in zip(names, vecs)}
            return _skill_embeddings_cache
        except Exception:
            return {}


def _encode_for_matching(
    texts: List[str],
    is_query: bool = False,
    explore_fast: bool = False,
) -> Any:
    """Encode texts for semantic matching using E5-large with fallback to MiniLM.

    explore_fast: use MiniLM only (no E5) — для цикла explore_opportunities, иначе сотни тяжёлых батчей.
    """
    if explore_fast:
        return _encode_texts(texts, model_name=Config.EMBED_MODEL_NAME, normalize=True)
    try:
        if is_query:
            wrapped = [_e5_query_text(t) for t in texts]
        else:
            wrapped = [_e5_passage_text(t) for t in texts]
        return _encode_texts(wrapped, model_name=Config.EMBED_MODEL_NAME_V2, normalize=True)
    except Exception:
        return _encode_texts(texts, model_name=Config.EMBED_MODEL_NAME, normalize=True)


def encode_user_skills_query_vectors(
    user_skill_names: List[str],
    explore_fast: bool = False,
) -> Any:
    """Precompute query-side embeddings for user skills (explore / semantic_match hot paths)."""
    if not user_skill_names:
        return None
    try:
        return _encode_for_matching(user_skill_names, is_query=True, explore_fast=explore_fast)
    except Exception:
        return None


def semantic_match_skills(
    user_skill_names: List[str],
    required_skill_names: List[str],
    threshold: Optional[float] = None,
    user_vectors: Any = None,
    req_vectors: Any = None,
    explore_fast: bool = False,
) -> Dict[str, str]:
    """Для каждого user-навыка находит ближайший required-навык по embedding similarity.
    Возвращает {user_name: matched_required_name} для пар с score >= threshold.
    Пары выбираются жадно: один required-навык может быть сопоставлен только одному user-навыку.
    Uses E5-large (query/passage) for higher accuracy, with MiniLM fallback.

    user_vectors: optional precomputed embeddings (same order as user_skill_names) to avoid
    re-encoding the user profile inside tight loops (e.g. explore_opportunities).
    req_vectors: optional passage-side embeddings (same order as required_skill_names), e.g. from
    _cached_role_passage_embeddings — avoids encoding role requirements twice per iteration.
    """
    threshold = threshold or Config.SKILL_MATCH_THRESHOLD
    if not user_skill_names or not required_skill_names:
        return {}
    try:
        import numpy as np
    except Exception:
        return {}
    try:
        if user_vectors is not None:
            user_vecs = np.asarray(user_vectors, dtype=float)
            if user_vecs.shape[0] != len(user_skill_names):
                user_vecs = _encode_for_matching(
                    user_skill_names, is_query=True, explore_fast=explore_fast
                )
        else:
            user_vecs = _encode_for_matching(
                user_skill_names, is_query=True, explore_fast=explore_fast
            )
        if req_vectors is not None:
            req_vecs = np.asarray(req_vectors, dtype=float)
            if req_vecs.shape[0] != len(required_skill_names):
                req_vecs = _encode_for_matching(
                    required_skill_names, is_query=False, explore_fast=explore_fast
                )
        else:
            req_vecs = _encode_for_matching(
                required_skill_names, is_query=False, explore_fast=explore_fast
            )
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


def compute_profile_similarity(
    user_skill_names: List[str],
    role_skill_names: List[str],
    precomputed_user_vecs: Any = None,
    precomputed_role_vecs: Any = None,
    explore_fast: bool = False,
) -> float:
    """Cosine similarity между средним эмбеддингом профиля пользователя и профиля роли.
    Uses E5-large for higher accuracy.

    precomputed_user_vecs: optional matrix of user skill embeddings (same order as user_skill_names)
    to avoid re-encoding the user profile for every role×grade pair in explore_opportunities.
    precomputed_role_vecs: optional passage embeddings for role_skill_names (same order).
    """
    if not user_skill_names or not role_skill_names:
        return 0.0
    try:
        import numpy as np
        if precomputed_user_vecs is not None:
            u_vecs = np.asarray(precomputed_user_vecs, dtype=float)
            if u_vecs.shape[0] != len(user_skill_names):
                u_vecs = _encode_for_matching(
                    user_skill_names, is_query=True, explore_fast=explore_fast
                )
        else:
            u_vecs = _encode_for_matching(
                user_skill_names, is_query=True, explore_fast=explore_fast
            )
        if precomputed_role_vecs is not None:
            r_vecs = np.asarray(precomputed_role_vecs, dtype=float)
            if r_vecs.shape[0] != len(role_skill_names):
                r_vecs = _encode_for_matching(
                    role_skill_names, is_query=False, explore_fast=explore_fast
                )
        else:
            r_vecs = _encode_for_matching(
                role_skill_names, is_query=False, explore_fast=explore_fast
            )
        u_mean = np.mean(u_vecs, axis=0)
        r_mean = np.mean(r_vecs, axis=0)
        u_mean = u_mean / (np.linalg.norm(u_mean) + 1e-9)
        r_mean = r_mean / (np.linalg.norm(r_mean) + 1e-9)
        return float(np.dot(u_mean, r_mean))
    except Exception:
        return 0.0

from config import Config


class ScenarioHandler:
    def __init__(self, data_loader):
        self.data = data_loader

    def next_grade(self, current_role, current_grade, user_skills):
        grade_sequence = {
            "Junior": "Middle", "Middle": "Senior",
            "Senior": "Lead", "Lead": "Expert", "Expert": "Expert",
        }
        target_grade = grade_sequence.get(current_grade, "Senior")
        target_reqs = self.data.get_role_requirements(current_role, target_grade)
        return target_reqs, f"{current_role} ({target_grade})"

    def change_profession(self, target_role, user_skills):
        target_reqs = self.data.get_role_requirements(target_role, "Middle")
        return target_reqs, f"{target_role} (Transition)"

    def explore_opportunities(self, user_skills):
        """Explore с семантическим мэтчингом и profile embedding."""
        try:
            from gap_analyzer import _normalize_skill_set
            norm = _normalize_skill_set(user_skills)
        except Exception:
            norm = user_skills

        user_skill_names = [n for n in norm if n not in self.data.atlas_map]

        # Пытаемся использовать profile embedding
        try:
            from rag_service import (
                semantic_match_skills,
                compute_profile_similarity,
                encode_user_skills_query_vectors,
                _cached_role_passage_embeddings,
            )
            use_semantic = True
        except Exception:
            use_semantic = False
            _cached_role_passage_embeddings = None  # type: ignore

        explore_fast = bool(getattr(Config, "EXPLORE_FAST_EMBEDDINGS", True))
        user_skill_vecs = None
        if use_semantic and user_skill_names:
            user_skill_vecs = encode_user_skills_query_vectors(
                user_skill_names, explore_fast=explore_fast
            )

        opportunities = []
        for role_display in self.data.get_all_roles():
            internal = self.data.get_internal_role_name(role_display)
            if not internal:
                continue
            for grade in ["Junior", "Middle", "Senior"]:
                requirements = self.data.get_role_requirements(internal, grade)
                if not requirements:
                    continue
                skill_reqs = {k: v for k, v in requirements.items() if k not in self.data.atlas_map}
                if not skill_reqs:
                    continue

                req_names = list(skill_reqs.keys())

                # Exact match (after normalization)
                exact_overlap = sum(1 for s, req in skill_reqs.items()
                                    if s in norm and norm[s] >= req)

                # Semantic match (reuse passage embeddings for this role×grade)
                sem_overlap = 0
                profile_sim = 0.0
                req_passage_vecs = None
                if use_semantic and user_skill_names and _cached_role_passage_embeddings:
                    try:
                        req_passage_vecs = _cached_role_passage_embeddings(
                            (internal, grade), req_names, explore_fast=explore_fast
                        )
                    except Exception:
                        req_passage_vecs = None
                if use_semantic and user_skill_names and req_passage_vecs is not None:
                    try:
                        sem_map = semantic_match_skills(
                            user_skill_names,
                            req_names,
                            user_vectors=user_skill_vecs,
                            req_vectors=req_passage_vecs,
                            explore_fast=explore_fast,
                        )
                        for u_name, r_name in sem_map.items():
                            if r_name not in norm and norm.get(u_name, 0) >= skill_reqs.get(r_name, 1):
                                sem_overlap += 1
                    except Exception:
                        pass

                total = len(skill_reqs)
                combined = min(exact_overlap + sem_overlap, total)
                score = int((combined / total) * 100) if total else 0

                # Profile similarity bonus
                if use_semantic and user_skill_names and req_passage_vecs is not None:
                    try:
                        profile_sim = compute_profile_similarity(
                            user_skill_names,
                            req_names,
                            precomputed_user_vecs=user_skill_vecs,
                            precomputed_role_vecs=req_passage_vecs,
                            explore_fast=explore_fast,
                        )
                    except Exception:
                        pass

                opportunities.append({
                    "role": f"{role_display} ({grade})",
                    "match": score,
                    "semantic_score": round(profile_sim, 3),
                    "internal_role": internal,
                })
        return sorted(opportunities, key=lambda x: (-x.get("semantic_score", 0), -x["match"], x["role"]))[:30]

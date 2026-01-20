import json
import os
import re
import html
from typing import Optional

from sentence_transformers import SentenceTransformer, util
import torch
import torch.nn.functional as F

TAG_RE = re.compile(r"<[^>]+>")
WS_RE  = re.compile(r"\s+")

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
# MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_TAXONOMY_PATH = "/shared/lumen_taxonomy_iptc_l1l2_subcategories_tight_v3.1.0.json"

def clean_text(raw: Optional[str]) -> str:
    if not raw:
        return ""
    # decode entities
    raw = html.unescape(raw)
    # drop tags
    raw = TAG_RE.sub(" ", raw)
    # drop leftover image/media urls quickly
    raw = re.sub(r"https?://\S+", " ", raw)
    # normalize whitespace
    raw = WS_RE.sub(" ", raw).strip()
    return raw

class NewsClassifier:
    def __init__(
        self,
        taxonomy_path: str = DEFAULT_TAXONOMY_PATH,
        model_name: str = MODEL_NAME,
        device: str = "cpu",
        centroids_cache: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device
        self.taxonomy_path = taxonomy_path
        self.centroids_cache = centroids_cache
        self.categories = {}
        self.taxonomy_version = None
        self.taxonomy_data = None

        if cache_dir:
            os.environ["HF_HOME"] = cache_dir
            os.environ["TRANSFORMERS_CACHE"] = cache_dir
            os.environ["HUGGINGFACE_HUB_CACHE"] = cache_dir
            os.environ["SENTENCE_TRANSFORMERS_HOME"] = cache_dir

        self.model = SentenceTransformer(model_name, device=device)
        self.load_taxonomy()

    def load_taxonomy(self):
        """Loads taxonomy and pre-calculates the Centroid (DNA) for each category."""
        if not os.path.exists(self.taxonomy_path):
            print(f"Warning: Taxonomy file not found at {self.taxonomy_path}")
            return

        taxonomy_mtime = os.path.getmtime(self.taxonomy_path)

        with open(self.taxonomy_path, "r", encoding="utf-8") as f:
            taxonomy_data = json.load(f)

        self.taxonomy_version = taxonomy_data.get("version")
        self.taxonomy_data = taxonomy_data

        if self.centroids_cache and os.path.exists(self.centroids_cache):
            payload = torch.load(self.centroids_cache, map_location=self.device)
            payload_model = payload.get("model_name") or payload.get("model")
            cache_ok = (
                payload_model in (None, self.model_name)
                and payload.get("taxonomy_path") in (None, self.taxonomy_path)
                and payload.get("taxonomy_mtime") in (None, taxonomy_mtime)
                and payload.get("taxonomy_version") in (None, self.taxonomy_version)
                and payload.get("device") in (None, self.device)
            )
            if cache_ok:
                self.categories = payload.get("categories", {})
                for cid in self.categories:
                    self.categories[cid]["centroid"] = self.categories[cid]["centroid"].to(self.device)
                if self.categories:
                    print(f"Classifier initialized with {len(self.categories)} categories (cache).")
                    return

        if "categories" in taxonomy_data:
            classification_level = taxonomy_data.get("modeling", {}).get("classification_level")
            items = []
            for category in taxonomy_data.get("categories", []):
                if classification_level is None or category.get("level") == classification_level:
                    items.append(category)
                for subcategory in category.get("subcategories", []):
                    if classification_level is None or subcategory.get("level") == classification_level:
                        items.append(subcategory)
        else:
            items = taxonomy_data.get("taxonomy", [])
        
        for category in items:
            cat_id = category.get("id")
            label = category.get("labels", {}).get("en", cat_id)
            anchors = category.get("anchors", [])
            if isinstance(anchors, dict):
                anchors = anchors.get("en", []) + anchors.get("fr", [])

            if not cat_id:
                continue

            # Use label + anchors to form the prototype text set
            prototype_texts = [label] + anchors
            embeddings = self.model.encode(prototype_texts, convert_to_tensor=True, normalize_embeddings=True)
            embeddings = embeddings.to(self.device)

            centroid = F.normalize(embeddings.mean(dim=0), p=2, dim=0).to(self.device)

            self.categories[cat_id] = {
                "label": label,
                "labels": category.get("labels", {}),
                "anchors": anchors,
                "centroid": centroid,
            }

        if self.centroids_cache:
            payload = {
                "model_name": self.model_name,
                "taxonomy_path": self.taxonomy_path,
                "taxonomy_mtime": taxonomy_mtime,
                "taxonomy_version": self.taxonomy_version,
                "device": self.device,
                "categories": self.categories,
            }
            torch.save(payload, self.centroids_cache)

        print(f"Classifier initialized with {len(self.categories)} categories.")

    def classify_text_with_scores(
        self,
        text: str,
        threshold: float = 0.36,
        margin_threshold: float = 0.07,
        min_len: int = 30,
        low_bucket: str = "other",
    ):
        text = clean_text(text)
        if not text or len(text) < min_len:
            return {
                "category_id": low_bucket,
                "confidence": 0.0,
                "needs_review": True,
                "reason": "no_text",
                "runner_up_confidence": None,
                "margin": None,
            }

        query_embedding = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        query_embedding = query_embedding.to(self.device)
        best_category_id = None
        highest_score = -1.0
        second_score = -1.0

        for cat_id, data in self.categories.items():
            score = util.cos_sim(query_embedding, data["centroid"].to(self.device)).item()
            if score > highest_score:
                second_score = highest_score
                highest_score = score
                best_category_id = cat_id
            elif score > second_score:
                second_score = score

        margin = (highest_score - second_score) if second_score >= 0 else None
        accept = (highest_score >= threshold) or ((margin is not None) and (margin >= margin_threshold))

        if not accept or best_category_id is None:
            return {
                "category_id": low_bucket,
                "confidence": float(highest_score),
                "needs_review": True,
                "reason": "low_confidence",
                "runner_up_confidence": None if second_score < 0 else float(second_score),
                "margin": None if second_score < 0 else float(margin),
            }

        return {
            "category_id": best_category_id,
            "confidence": float(highest_score),
            "needs_review": False,
            "reason": "ok",
            "runner_up_confidence": None if second_score < 0 else float(second_score),
            "margin": None if second_score < 0 else float(margin),
        }

    def score_text(self, text: str, min_len: int = 30):
        cleaned = clean_text(text)
        if not cleaned or len(cleaned) < min_len:
            return cleaned, []

        query_embedding = self.model.encode(cleaned, convert_to_tensor=True, normalize_embeddings=True)
        query_embedding = query_embedding.to(self.device)
        scores = []

        for cat_id, data in self.categories.items():
            score = util.cos_sim(query_embedding, data["centroid"].to(self.device)).item()
            scores.append({
                "category_id": cat_id,
                "score": float(score),
                "label": data.get("label") or cat_id,
            })

        scores.sort(key=lambda item: item["score"], reverse=True)
        return cleaned, scores

    def classify_text(
        self,
        text: str,
        threshold: float = 0.36,
        margin_threshold: float = 0.07,
        min_len: int = 30,
        low_bucket: str = "other",
    ):
        result = self.classify_text_with_scores(
            text,
            threshold=threshold,
            margin_threshold=margin_threshold,
            min_len=min_len,
            low_bucket=low_bucket,
        )
        return result["category_id"]
    
    def get_taxonomy(self, lang="en"):
        """
        Returns taxonomy labels and tree for the specified language.
        """
        labels = {}
        tree = []

        uncat_translations = {
            "en": "Uncategorized",
            "es": "Sin categoría",
            "fr": "Non classé",
            "pt": "Não categorizado",
        }

        if not self.taxonomy_data:
            labels["uncategorized"] = uncat_translations.get(lang, "Uncategorized")
            return {"labels": labels, "tree": tree}

        if "categories" not in self.taxonomy_data:
            for cat_id, data in self.categories.items():
                category_labels = data.get("labels", {})
                label = category_labels.get(lang) or category_labels.get("en") or cat_id
                labels[cat_id] = label
            labels["uncategorized"] = uncat_translations.get(lang, "Uncategorized")
            tree = [
                {
                    "id": cat_id,
                    "label": labels.get(cat_id, cat_id),
                    "children": [],
                }
                for cat_id in sorted(labels.keys())
                if cat_id != "uncategorized"
            ]
            return {"labels": labels, "tree": tree}

        for category in self.taxonomy_data.get("categories", []):
            label = category.get("labels", {}).get(lang) or category.get("labels", {}).get("en") or category.get("id")
            labels[category.get("id")] = label
            children = []
            for subcategory in category.get("subcategories", []):
                sub_label = subcategory.get("labels", {}).get(lang) or subcategory.get("labels", {}).get("en") or subcategory.get("id")
                labels[subcategory.get("id")] = sub_label
                children.append(
                    {
                        "id": subcategory.get("id"),
                        "label": sub_label,
                        "children": [],
                    }
                )
            tree.append(
                {
                    "id": category.get("id"),
                    "label": label,
                    "children": children,
                }
            )

        labels["uncategorized"] = uncat_translations.get(lang, "Uncategorized")

        return {"labels": labels, "tree": tree}



# Initialize a singleton instance to be used across the FastAPI app
# This ensures the model is only loaded into memory ONCE.
_classifier_engine = None


def get_classifier_engine(
    taxonomy_path: str = DEFAULT_TAXONOMY_PATH,
    model_name: str = MODEL_NAME,
    device: str = "cpu",
    centroids_cache: Optional[str] = None,
):
    global _classifier_engine
    if _classifier_engine is None:
        cache_dir = os.getenv("CLASSIFIER_CACHE_DIR") or None
        if not centroids_cache:
            centroids_cache = os.getenv("CLASSIFIER_CENTROIDS_CACHE") or None
        if not centroids_cache and os.path.isdir("/shared"):
            centroids_cache = "/shared/lumen_classifier_centroids.pt"
        _classifier_engine = NewsClassifier(
            taxonomy_path=taxonomy_path,
            model_name=model_name,
            device=device,
            centroids_cache=centroids_cache,
            cache_dir=cache_dir,
        )
    return _classifier_engine

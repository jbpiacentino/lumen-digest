import json
import os
from sentence_transformers import SentenceTransformer, util
import torch
import torch.nn.functional as F

import re
import html

TAG_RE = re.compile(r"<[^>]+>")
WS_RE  = re.compile(r"\s+")

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
# MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

def clean_text(raw: str) -> str:
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
    def __init__(self, taxonomy_path="/shared/taxonomy.json", model_name=MODEL_NAME, centroids_cache=None):
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.taxonomy_path = taxonomy_path
        self.centroids_cache = centroids_cache
        self.categories = {}
        self.load_taxonomy()

    def load_taxonomy(self):
        """Loads taxonomy and pre-calculates the Centroid (DNA) for each category."""
        if not os.path.exists(self.taxonomy_path):
            print(f"Warning: Taxonomy file not found at {self.taxonomy_path}")
            return

        taxonomy_mtime = os.path.getmtime(self.taxonomy_path)
        if self.centroids_cache and os.path.exists(self.centroids_cache):
            payload = torch.load(self.centroids_cache, map_location="cpu")
            if (
                payload.get("model") == self.model_name
                and payload.get("taxonomy_path") == self.taxonomy_path
                and payload.get("taxonomy_mtime") == taxonomy_mtime
            ):
                self.categories = payload.get("categories", {})
                if self.categories:
                    print(f"Classifier initialized with {len(self.categories)} categories (cache).")
                    return

        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            taxonomy_data = json.load(f)

        items = taxonomy_data.get("taxonomy", [])
        
        for category in items:
            cat_id = category.get("id")
            label = category.get("labels", {}).get("en", cat_id)
            anchors = category.get("anchors", [])

            # We only create centroids for categories that have anchors 
            # (Level 1 items in the JSON)
            if anchors and cat_id:
                print(f"DEBUG: Generating DNA for {cat_id}...")
                
                # # 1. Convert all anchor strings into vectors
                # anchor_embeddings = self.model.encode(anchors)

                # # 2. Calculate the Centroid (Average Vector)
                # centroid = np.mean(anchor_embeddings, axis=0)

                # # Store by ID, but also keep the labels for the UI
                # self.categories[cat_id] = {
                #     "labels": category.get("labels", {}),
                #     "centroid": centroid
                # }
                # Use label + anchors to form the prototype text set
                prototype_texts = [label] + anchors
                embeddings = self.model.encode(prototype_texts, convert_to_tensor=True, normalize_embeddings=True)
                # embeddings: [N, dim], already normalized row-wise

                centroid = embeddings.mean(dim=0)         # [dim]
                centroid = F.normalize(centroid, p=2, dim=0)  # normalize centroid vector

                self.categories[cat_id] = {
                    "label": label,
                    "labels": category.get("labels", {}),
                    "anchors": anchors,
                    "centroid": centroid,
                }

        if self.centroids_cache:
            payload = {
                "model": self.model_name,
                "taxonomy_path": self.taxonomy_path,
                "taxonomy_mtime": taxonomy_mtime,
                "categories": self.categories,
            }
            torch.save(payload, self.centroids_cache)

        print(f"Classifier initialized with {len(self.categories)} categories.")

    def classify_text_with_scores(self, text, threshold=0.38, min_len=30):
        text = clean_text(text)
        if not text or len(text) < min_len:
            return {
                "category_id": "other",
                "confidence": 0.0,
                "runner_up_confidence": None,
                "margin": None,
                "needs_review": True,
                "reason": "short_text",
            }

        query_embedding = self.model.encode(text, convert_to_tensor=True, normalize_embeddings=True)
        best_category_id = None
        highest_score = -1.0
        second_score = -1.0

        for cat_id, data in self.categories.items():
            score = util.cos_sim(query_embedding, data["centroid"]).item()
            if score > highest_score:
                second_score = highest_score
                highest_score = score
                best_category_id = cat_id
            elif score > second_score:
                second_score = score

        if highest_score < threshold or best_category_id is None:
            return {
                "category_id": "other",
                "confidence": float(highest_score),
                "runner_up_confidence": None if second_score < 0 else float(second_score),
                "margin": None if second_score < 0 else float(highest_score - second_score),
                "needs_review": True,
                "reason": "low_confidence",
            }

        return {
            "category_id": best_category_id,
            "confidence": float(highest_score),
            "runner_up_confidence": None if second_score < 0 else float(second_score),
            "margin": None if second_score < 0 else float(highest_score - second_score),
            "needs_review": False,
            "reason": None,
        }

    def classify_text(self, text, threshold=0.38):
        result = self.classify_text_with_scores(text, threshold=threshold)
        return result["category_id"]
    
    def get_taxonomy_labels(self, lang="en"):
        """
        Returns a dictionary of {id: label} for the specified language.
        """
        labels = {}

        # Define translations for the system-generated 'uncategorized' key
        # You can expand this list as needed
        uncat_translations = {
            "en": "Uncategorized",
            "es": "Sin categoría",
            "fr": "Non classé",
            "pt": "Não categorizado"
        }

        for cat_id, data in self.categories.items():
            # 1. Look for the specific language
            # 2. Fallback to English ("en")
            # 3. Fallback to the ID itself if all else fails
            category_labels = data.get("labels", {})
            label = category_labels.get(lang) or category_labels.get("en") or cat_id
            labels[cat_id] = label

        # Add the uncategorized label for the requested language
        labels["uncategorized"] = uncat_translations.get(lang, "Uncategorized")
        
        return labels



# Initialize a singleton instance to be used across the FastAPI app
# This ensures the model is only loaded into memory ONCE.
_classifier_engine = None


def get_classifier_engine(taxonomy_path="/shared/taxonomy.json", model_name=MODEL_NAME, centroids_cache=None):
    global _classifier_engine
    if _classifier_engine is None:
        _classifier_engine = NewsClassifier(
            taxonomy_path=taxonomy_path,
            model_name=model_name,
            centroids_cache=centroids_cache,
        )
    return _classifier_engine

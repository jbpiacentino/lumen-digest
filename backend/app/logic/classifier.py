import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer, util

class NewsClassifier:
    def __init__(self, taxonomy_path="/shared/taxonomy.json"):
        self.taxonomy_path = taxonomy_path
        # We use a multilingual model since you mentioned French and English
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.categories = {}
        self.load_taxonomy()

    def load_taxonomy(self):
        """Loads taxonomy and pre-calculates the Centroid (DNA) for each category."""
        if not os.path.exists(self.taxonomy_path):
            print(f"Warning: Taxonomy file not found at {self.taxonomy_path}")
            return

        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            taxonomy_data = json.load(f)

        # Your JSON uses the key "taxonomy", not "categories"
        items = taxonomy_data.get("taxonomy", [])
        
        for category in items:
            # FIX: Use "id" instead of "name"
            cat_id = category.get("id")
            anchors = category.get("anchors", [])

            # We only create centroids for categories that have anchors 
            # (Level 1 items in your JSON)
            if anchors and cat_id:
                print(f"DEBUG: Generating DNA for {cat_id}...")
                
                # 1. Convert all anchor strings into vectors
                anchor_embeddings = self.model.encode(anchors)

                # 2. Calculate the Centroid (Average Vector)
                centroid = np.mean(anchor_embeddings, axis=0)

                # Store by ID, but also keep the labels for the UI
                self.categories[cat_id] = {
                    "labels": category.get("labels", {}),
                    "centroid": centroid
                }

        print(f"Classifier initialized with {len(self.categories)} categories.")

    def classify_text(self, text, threshold=0.38):
            if not text or len(text) < 10:
                return "uncategorized" # Use lowercase ID

            query_embedding = self.model.encode(text, convert_to_tensor=True)
            
            best_category_id = None
            highest_score = -1

            for cat_id, data in self.categories.items():
                score = util.cos_sim(query_embedding, data["centroid"]).item()
                if score > highest_score:
                    highest_score = score
                    best_category_id = cat_id

            if highest_score < threshold:
                return "uncategorized"

            return best_category_id
    
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
classifier_engine = NewsClassifier()

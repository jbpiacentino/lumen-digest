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

    def classify_text(self, text: str, threshold: float = 0.25):
        """
        Compares text embedding to category centroids using Cosine Similarity.
        Returns the name of the best category or 'Uncategorized'.
        """
        if not self.categories:
            return "Uncategorized"

        # 1. Embed the incoming text (article title or summary)
        text_embedding = self.model.encode(text)

        best_category = "Uncategorized"
        highest_score = 0

        # 2. Compare against every category centroid
        for name, data in self.categories.items():
            # util.cos_sim returns a tensor, we convert to float
            score = float(util.cos_sim(text_embedding, data["centroid"]))
            
            if score > highest_score:
                highest_score = score
                best_category = name

        # 3. Apply threshold logic
        if highest_score < threshold:
            return "Uncategorized"

        return best_category

# Initialize a singleton instance to be used across the FastAPI app
# This ensures the model is only loaded into memory ONCE.
classifier_engine = NewsClassifier()

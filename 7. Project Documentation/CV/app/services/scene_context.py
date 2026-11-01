from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


MODEL_NAME = "openai/clip-vit-base-patch32"

SCENE_LABELS = {
    "real_world": "a real-world photograph or camera recording",
    "gameplay": "a screenshot from a 3D first-person shooter video game",
    "cgi": "a computer-generated 3D scene or rendered environment",
    "animation": "an animated cartoon scene",
}


class SceneContextService:
    def __init__(self) -> None:
        self.device = "cpu"
        self.processor = CLIPProcessor.from_pretrained(MODEL_NAME)
        self.model = CLIPModel.from_pretrained(MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()

    def classify_image(self, image_path: str | Path) -> dict[str, Any]:
        image_path = Path(image_path)

        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with Image.open(image_path) as source:
            image = source.convert("RGB")

        candidates = list(SCENE_LABELS.values())
        inputs = self.processor(
            text=candidates,
            images=image,
            return_tensors="pt",
            padding=True,
        )

        with torch.inference_mode():
            outputs = self.model(**inputs)
            scores = outputs.logits_per_image.softmax(dim=1)[0]

        ranked = sorted(
            [
                {
                    "category": category,
                    "description": description,
                    "score": round(float(scores[index]), 4),
                }
                for index, (category, description) in enumerate(
                    SCENE_LABELS.items()
                )
            ],
            key=lambda item: item["score"],
            reverse=True,
        )

        return {
            "model": MODEL_NAME,
            "device": self.device,
            "predicted_category": ranked[0]["category"],
            "similarity_scores": ranked,
            "requires_review": True,
            "interpretation_note": (
                "Scores are relative among the supplied candidates, "
                "not calibrated probabilities. Scene classification "
                "may be wrong; human review is required."
            ),
        }

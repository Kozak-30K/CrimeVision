
from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from transformers import BlipProcessor, BlipForConditionalGeneration


MODEL_NAME = "Salesforce/blip-image-captioning-base"


class SceneDescriptionService:
    """Generate a preliminary caption for an image using BLIP."""

    def __init__(self):
        self.device = torch.device("cpu")

        self.processor = BlipProcessor.from_pretrained(MODEL_NAME)
        self.model = BlipForConditionalGeneration.from_pretrained(
            MODEL_NAME
        )
        self.model.to(self.device)
        self.model.eval()

    def describe_image(self, image_path: str | Path) -> dict:
        image_path = Path(image_path).expanduser().resolve()

        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                width, height = image.size

                inputs = self.processor(
                    images=image,
                    return_tensors="pt",
                )

        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("The supplied file is not a valid image.") from exc

        # Inference only: no gradients are needed.
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=60,
            )

        caption = self.processor.decode(
            output[0],
            skip_special_tokens=True,
        ).strip()

        return {
            "analysis_type": "scene_description",
            "source_image": image_path.name,
            "image_dimensions": {
                "width": width,
                "height": height,
            },
            "model": MODEL_NAME,
            "device": "cpu",
            "description": caption,
            "limitations": [
                "This is an AI-generated description, not verified evidence.",
                "The model may omit objects or misinterpret the scene.",
                "The description alone cannot establish criminal activity.",
            ],
        }


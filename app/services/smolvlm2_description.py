
from pathlib import Path

import torch
from PIL import Image, UnidentifiedImageError
from transformers import AutoProcessor, AutoModelForImageTextToText


MODEL_NAME = "HuggingFaceTB/SmolVLM2-500M-Instruct"


class SmolVLM2DescriptionService:
    """Generate preliminary image descriptions using SmolVLM2."""

    def __init__(self):
        self.device = torch.device("cpu")
        self.processor = AutoProcessor.from_pretrained(MODEL_NAME)
        self.model = AutoModelForImageTextToText.from_pretrained(MODEL_NAME)
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

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "image": image,
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image for preliminary "
                                    "forensic review in 3 to 5 concise "
                                    "sentences. Identify the visible setting, "
                                    "objects, people, positions, and "
                                    "observable actions. Describe uncertain "
                                    "objects by appearance instead of "
                                    "guessing their identity. Do not invent "
                                    "details or infer criminal activity."
                                ),
                            },
                        ],
                    }
                ]

                inputs = self.processor.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=True,
                    return_dict=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(self.device)

        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(
                "The supplied file is not a valid image."
            ) from exc

        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=120,
                do_sample=False,
            )

        input_length = inputs["input_ids"].shape[-1]
        generated_tokens = output[:, input_length:]

        description = self.processor.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
        )[0].strip()

        if description.lower().startswith("assistant:"):
            description = description[len("assistant:"):].strip()

        if not description:
            description = (
                "No usable description was generated for this frame. "
                "Review the image manually."
            )

        return {
            "analysis_type": "scene_description",
            "source_image": image_path.name,
            "image_dimensions": {
                "width": width,
                "height": height,
            },
            "model": MODEL_NAME,
            "device": "cpu",
            "description": description,
            "limitations": [
                "This is an AI-generated description, not verified evidence.",
                "The model may omit objects or misinterpret the scene.",
                "Low-light, game, or rendered imagery may be misinterpreted.",
                "The description alone cannot establish criminal activity.",
            ],
        }


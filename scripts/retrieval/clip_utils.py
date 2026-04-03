from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from helpers import l2_normalize


@dataclass
class ClipEmbedder:
    """
    Small wrapper around a pretrained CLIP model.

    CLIP is a good Phase 3 fit because it provides text and image embeddings in
    one shared vector space, which keeps the first multimodal retrieval system
    simple and inspectable.
    """

    model_name: str
    processor: CLIPProcessor
    model: CLIPModel
    device: str
    embedding_dim: int

    @classmethod
    def load(cls, model_name: str) -> "ClipEmbedder":
        device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = CLIPProcessor.from_pretrained(model_name)
        model = CLIPModel.from_pretrained(model_name)
        model.eval()
        model.to(device)

        return cls(
            model_name=model_name,
            processor=processor,
            model=model,
            device=device,
            embedding_dim=int(model.config.projection_dim),
        )

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        with torch.inference_mode():
            batch = self.processor(
                text=texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            batch = {name: tensor.to(self.device) for name, tensor in batch.items()}
            features = self.model.get_text_features(**batch)

        vectors = features.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

    def encode_images(self, images: list[Image.Image]) -> np.ndarray:
        with torch.inference_mode():
            batch = self.processor(images=images, return_tensors="pt")
            batch = {name: tensor.to(self.device) for name, tensor in batch.items()}
            features = self.model.get_image_features(**batch)

        vectors = features.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

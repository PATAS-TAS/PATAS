from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from typing import Dict, List, Union
from app.config import settings
import logging
import time

logger = logging.getLogger(__name__)


class MLModel:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.batch_size = 16  # Maximum batch size for inference
        self._load_model()

    def _load_model(self):
        try:
            model_name = settings.model_name
            logger.info(f"Loading model: {model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info(f"Model loaded successfully on {self.device}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            logger.warning("Model not loaded. Using fallback mode (rule-based only)")
            self.model = None
            self.tokenizer = None

    def predict(self, text: Union[str, List[str]]) -> Union[Dict[str, float], List[Dict[str, float]]]:
        """
        Predict spam/toxicity for single text or batch of texts.
        
        Args:
            text: Single text string or list of text strings (max 16)
        
        Returns:
            Single dict or list of dicts with spam and toxicity scores
        """
        if not self.model or not self.tokenizer:
            if isinstance(text, list):
                return [{"spam": 0.0, "toxicity": 0.0} for _ in text]
            return {"spam": 0.0, "toxicity": 0.0}

        # Handle single text
        if isinstance(text, str):
            return self._predict_single(text)
        
        # Handle batch
        if len(text) > self.batch_size:
            # Split into batches
            results = []
            for i in range(0, len(text), self.batch_size):
                batch = text[i:i + self.batch_size]
                results.extend(self._predict_batch(batch))
            return results
        
        return self._predict_batch(text)

    def _predict_single(self, text: str) -> Dict[str, float]:
        """Predict for a single text."""
        try:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits

            if logits.shape[1] >= 2:
                probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
                toxicity = float(probs[1])
            else:
                probs = torch.sigmoid(logits).cpu().numpy()[0]
                toxicity = float(probs[0])

            return {"spam": toxicity * 0.7, "toxicity": min(toxicity, 0.95)}
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            return {"spam": 0.0, "toxicity": 0.0}

    def _predict_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """Predict for a batch of texts (more efficient)."""
        try:
            start_time = time.time()
            
            # Tokenize batch
            inputs = self.tokenizer(
                texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits

            # Process results
            results = []
            if logits.shape[1] >= 2:
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
                for prob in probs:
                    toxicity = float(prob[1])
                    results.append({
                        "spam": toxicity * 0.7,
                        "toxicity": min(toxicity, 0.95)
                    })
            else:
                probs = torch.sigmoid(logits).cpu().numpy()
                for prob in probs:
                    toxicity = float(prob[0])
                    results.append({
                        "spam": toxicity * 0.7,
                        "toxicity": min(toxicity, 0.95)
                    })
            
            batch_time = time.time() - start_time
            if batch_time > 0.1:  # Log slow batches
                logger.debug(f"Batch inference ({len(texts)} texts) took {batch_time:.4f}s")
            
            return results
        except Exception as e:
            logger.error(f"Error in batch prediction: {e}")
            return [{"spam": 0.0, "toxicity": 0.0} for _ in texts]

    def warmup(self, num_samples: int = 3):
        """Warm up model with dummy predictions to reduce cold start latency."""
        if not self.model or not self.tokenizer:
            return
        dummy_texts = [
            "Sample text for warmup",
            "Another warmup example to preload model",
            "Final warmup text to ensure model is ready"
        ][:num_samples]
        for text in dummy_texts:
            try:
                self.predict(text)
            except Exception as e:
                logger.warning(f"Warmup failed: {e}")
        logger.info(f"Model warmup completed ({num_samples} samples)")


ml_model = MLModel()


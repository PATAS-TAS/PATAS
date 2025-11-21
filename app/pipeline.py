from typing import Dict
from app.preprocessing import clean_text
from app.commercial_patterns import commercial_patterns
from app.ml_model import ml_model
from app.cache import classification_cache
from app.observability import trace_function, add_span_attribute, add_span_event
import logging
import time

logger = logging.getLogger(__name__)


class ClassificationPipeline:
    def __init__(self):
        self.version = "0.1.0"
        # thresholds can be hot-reloaded
        self.spam_label_threshold: float = 0.35
        self.api_threshold: float = 0.40

    def apply_config(self, spam_label_threshold: float, api_threshold: float) -> None:
        self.spam_label_threshold = max(0.0, min(1.0, spam_label_threshold))
        self.api_threshold = max(0.0, min(1.0, api_threshold))

    @trace_function(name="pipeline.classify")
    def classify(self, text: str, lang: str = "en") -> Dict:
        # Check cache first (fastest path)
        cache_start = time.time()
        cached = classification_cache.get(text, lang)
        cache_time = time.time() - cache_start
        if cached:
            from app.latency_profiler import record_stage_timing
            record_stage_timing("cache_hit", cache_time)
            add_span_attribute("pipeline.cache_hit", True)
            return cached
        
        from app.latency_profiler import record_stage_timing
        record_stage_timing("cache_miss", cache_time)
        add_span_attribute("pipeline.cache_hit", False)

        # Preprocessing
        add_span_event("pipeline.preprocessing.start")
        preprocess_start = time.time()
        text = clean_text(text)
        record_stage_timing("preprocessing", time.time() - preprocess_start)
        add_span_event("pipeline.preprocessing.complete")

        # Rule-based checking
        add_span_event("pipeline.rules.start")
        rule_start = time.time()
        rule_results = commercial_patterns.check(text)
        rule_score = sum(score for _, score in rule_results) / max(len(rule_results), 1)
        rule_score = min(rule_score, 0.95)
        record_stage_timing("rule_checking", time.time() - rule_start)
        add_span_attribute("pipeline.rule_score", rule_score)
        add_span_attribute("pipeline.rule_matches", len(rule_results))
        add_span_event("pipeline.rules.complete")

        # Short-circuit: if rules are very confident, skip ML
        from app.config import settings
        if settings.rules_only_bench or (rule_score >= 0.8 or rule_score <= 0.2):
            spam_score = rule_score
            toxicity = 0.0
            add_span_attribute("pipeline.short_circuit", True)
        else:
            # ML inference (single text, but model supports batch internally)
            add_span_event("pipeline.ml_inference.start")
            ml_start = time.time()
            ml_results = ml_model.predict(text)
            ml_spam = ml_results.get("spam", 0.0)
            ml_toxicity = ml_results.get("toxicity", 0.0)
            record_stage_timing("ml_inference", time.time() - ml_start)
            add_span_attribute("pipeline.ml_spam_score", ml_spam)
            add_span_attribute("pipeline.ml_toxicity", ml_toxicity)
            add_span_event("pipeline.ml_inference.complete")

            if ml_model.model is None:
                spam_score = min(rule_score, 0.99)
            else:
                # Optimized weights for better recall while maintaining precision
                # Slightly increase ML weight to catch patterns rules might miss
                spam_score = min(0.80 * rule_score + 0.20 * ml_spam, 0.99)
            toxicity = ml_toxicity
            add_span_attribute("pipeline.short_circuit", False)

        labels = []
        # Thresholds are configurable via config hot-reload
        if spam_score >= self.spam_label_threshold:
            labels.append("spam")
        if spam_score >= 0.7:
            labels.append("scam")
        if toxicity >= 0.5:
            labels.append("toxic")

        reasons = [reason for reason, _ in rule_results[:3]]

        result = {
            "spam_score": round(spam_score, 3),
            "toxicity": round(toxicity, 3),
            "labels": labels,
            "reasons": reasons,
            "version": self.version,
            # Note: labels use 0.35 threshold, but spam_score >= 0.4 is still the API threshold
        }

        classification_cache.set(text, lang, result)
        return result


pipeline = ClassificationPipeline()


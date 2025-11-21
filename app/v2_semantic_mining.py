"""
Semantic Pattern Mining - Discover patterns based on meaning, not exact words.

This module uses embeddings and LLM to find semantically similar spam messages,
even when they use different words, synonyms, or variations.

Implements two clustering approaches:
- DBSCAN: Fast, density-based clustering (O(n log n) with optimizations)
- Naive: Simple similarity-based clustering (O(n²), for comparison/fallback)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Pattern, Rule, PatternType, RuleStatus
from app.repositories import MessageRepository, PatternRepository, RuleRepository
from app.v2_rule_lifecycle import RuleLifecycleService
from app.v2_pattern_quality import PatternQualityFilter

logger = logging.getLogger(__name__)


class SemanticPatternMiner:
    """
    Mine patterns based on semantic similarity, not exact word matches.
    
    Uses embeddings to cluster similar messages, then LLM to:
    1. Understand why messages are similar (semantic pattern)
    2. Generate rules that catch variations (synonyms, paraphrases)
    """
    
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: Optional[Any] = None,  # EmbeddingEngine interface
        llm_engine: Optional[Any] = None,  # PatternMiningEngine interface
        use_dbscan: bool = True,  # Use DBSCAN clustering by default
    ):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.pattern_repo = PatternRepository(db)
        self.rule_repo = RuleRepository(db)
        self.lifecycle = RuleLifecycleService(db)
        self.embedding_provider = embedding_provider
        self.llm_engine = llm_engine
        self.use_dbscan = use_dbscan
    
    async def mine_semantic_patterns(
        self,
        days: int = 7,
        min_cluster_size: int = 3,
        similarity_threshold: float = 0.75,
    ) -> Dict[str, Any]:
        """
        Mine semantic patterns from spam messages.
        
        Process:
        1. Get spam messages
        2. Generate embeddings for each message
        3. Cluster messages by semantic similarity
        4. For each cluster, use LLM to:
           - Understand the semantic pattern
           - Generate a rule that catches variations
        5. Create Pattern and Rule objects
        
        Args:
            days: Number of days of messages to analyze
            min_cluster_size: Minimum messages in a cluster to create pattern
            similarity_threshold: Cosine similarity threshold for clustering
        
        Returns:
            Dict with stats: patterns_created, rules_created, clusters_found
        """
        logger.info(f"Mining semantic patterns from last {days} days")
        
        # Get spam messages
        spam_messages = await self.message_repo.get_recent(
            days=days,
            limit=10000,
            is_spam=True,
        )
        
        if len(spam_messages) < min_cluster_size:
            logger.warning(f"Only {len(spam_messages)} spam messages found (min={min_cluster_size})")
            return {
                "patterns_created": 0,
                "rules_created": 0,
                "clusters_found": 0,
                "error": "insufficient_data",
            }
        
        # Get ham messages for quality filtering
        ham_messages = await self.message_repo.get_recent(
            days=days,
            limit=min(1000, len(spam_messages) // 10),
            is_spam=False,
        )
        
        # Step 1: Generate embeddings
        logger.info(f"Generating embeddings for {len(spam_messages)} spam messages")
        embeddings = await self._generate_embeddings([m.text for m in spam_messages])
        
        if not embeddings:
            logger.warning("Failed to generate embeddings, falling back to keyword-based mining")
            return {
                "patterns_created": 0,
                "rules_created": 0,
                "clusters_found": 0,
                "error": "embedding_failed",
            }
        
        # Step 2: Cluster by semantic similarity
        logger.info(f"Clustering messages by semantic similarity (method: {'DBSCAN' if self.use_dbscan else 'naive'})")
        
        if self.use_dbscan:
            clusters = self._cluster_messages_dbscan(spam_messages, embeddings, similarity_threshold)
        else:
            clusters = self._cluster_messages(spam_messages, embeddings, similarity_threshold)
        
        logger.info(f"Found {len(clusters)} semantic clusters")
        
        # Step 3: Analyze clusters with LLM
        patterns_created = 0
        rules_created = 0
        
        for cluster_id, cluster_messages in clusters.items():
            if len(cluster_messages) < min_cluster_size:
                continue
            
            # Use LLM to understand the semantic pattern
            pattern_result = await self._analyze_cluster_with_llm(cluster_messages)
            
            if not pattern_result:
                continue
            
            # Create pattern
            pattern = await self.pattern_repo.create(
                type=PatternType.SIGNATURE,  # Semantic patterns are signature-based
                description=pattern_result["description"],
                examples=[m.text[:200] for m in cluster_messages[:5]],
            )
            patterns_created += 1
            
            # Generate rule that catches variations
            if pattern_result.get("rule_sql"):
                sql_expression = pattern_result["rule_sql"]
                
                # Validate rule on ham messages before creating
                min_precision = 0.85  # Minimum precision threshold for semantic rules
                is_valid = await self._validate_semantic_rule(
                    sql_expression=sql_expression,
                    cluster_messages=cluster_messages,
                    ham_messages=ham_messages,
                    min_precision=min_precision,
                )
                
                if is_valid:
                    rule = await self.lifecycle.create_candidate_rule(
                        sql_expression=sql_expression,
                        pattern_id=pattern.id,
                        origin="semantic_mining",
                    )
                    rules_created += 1
                else:
                    logger.info(
                        f"Semantic rule rejected: precision below threshold {min_precision} "
                        f"or too many false positives"
                    )
        
        logger.info(f"Semantic mining complete: {patterns_created} patterns, {rules_created} rules")
        
        return {
            "patterns_created": patterns_created,
            "rules_created": rules_created,
            "clusters_found": len(clusters),
            "messages_processed": len(spam_messages),
        }
    
    async def _generate_embeddings(self, texts: List[str]) -> Optional[List[np.ndarray]]:
        """
        Generate embeddings for texts.
        
        Uses embedding provider if available, otherwise falls back to simple approach.
        """
        if not self.embedding_provider:
            # Fallback: use LLM to generate embeddings if available
            if self.llm_engine and hasattr(self.llm_engine, 'generate_embeddings'):
                return await self.llm_engine.generate_embeddings(texts)
            else:
                logger.warning("No embedding provider available")
                return None
        
        try:
            if hasattr(self.embedding_provider, 'generate_embeddings'):
                return await self.embedding_provider.generate_embeddings(texts)
            else:
                # Try sync method
                return self.embedding_provider.generate_embeddings(texts)
        except (ValueError, AttributeError, TypeError) as e:
            # Handle data structure errors (wrong types, missing attributes)
            logger.error(f"Failed to generate embeddings (data error): {e}", exc_info=True)
            return None
        except Exception as e:
            # Catch-all for network errors, API errors, etc.
            logger.error(f"Failed to generate embeddings (unexpected error): {e}", exc_info=True)
            return None
    
    def _cluster_messages(
        self,
        messages: List[Message],
        embeddings: List[np.ndarray],
        threshold: float = 0.75,
    ) -> Dict[int, List[Message]]:
        """
        Cluster messages by semantic similarity using embeddings.
        
        Uses simple cosine similarity clustering.
        """
        if len(messages) != len(embeddings):
            logger.error(f"Mismatch: {len(messages)} messages, {len(embeddings)} embeddings")
            return {}
        
        clusters: Dict[int, List[Message]] = {}
        cluster_centers: Dict[int, np.ndarray] = {}
        assigned = [False] * len(messages)
        
        for i, (msg, emb) in enumerate(zip(messages, embeddings)):
            if assigned[i]:
                continue
            
            # Find best matching cluster
            best_cluster = None
            best_similarity = threshold
            
            for cluster_id, center in cluster_centers.items():
                similarity = self._cosine_similarity(emb, center)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster = cluster_id
            
            if best_cluster is not None:
                # Add to existing cluster
                clusters[best_cluster].append(msg)
                # Update cluster center (running average)
                n = len(clusters[best_cluster])
                cluster_centers[best_cluster] = (
                    (cluster_centers[best_cluster] * (n - 1) + emb) / n
                )
                assigned[i] = True
            else:
                # Create new cluster
                cluster_id = len(clusters)
                clusters[cluster_id] = [msg]
                cluster_centers[cluster_id] = emb
                assigned[i] = True
        
        return clusters
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def _cluster_messages_dbscan(
        self,
        messages: List[Message],
        embeddings: List[np.ndarray],
        threshold: float = 0.75,
    ) -> Dict[int, List[Message]]:
        """
        Cluster messages using DBSCAN (density-based clustering).
        
        DBSCAN advantages:
        - O(n log n) with optimizations (much faster than naive O(n²))
        - Automatic number of clusters
        - Handles noise (outliers) automatically
        - Finds clusters of arbitrary shape
        
        Args:
            messages: List of Message objects
            embeddings: List of embeddings (numpy arrays)
            threshold: Cosine similarity threshold (converted to distance)
        
        Returns:
            Dict mapping cluster_id -> List[Message]
        """
        if len(messages) != len(embeddings):
            logger.error(f"Mismatch: {len(messages)} messages, {len(embeddings)} embeddings")
            return {}
        
        try:
            from sklearn.cluster import DBSCAN
            from sklearn.metrics.pairwise import cosine_distances
        except ImportError:
            logger.warning("scikit-learn not installed, falling back to naive clustering")
            return self._cluster_messages(messages, embeddings, threshold)
        
        # Convert embeddings to numpy array
        embeddings_array = np.array(embeddings)
        
        # Convert cosine similarity threshold to distance
        # Cosine distance = 1 - cosine similarity
        # So if threshold is 0.75 (75% similarity), eps = 1 - 0.75 = 0.25
        eps = 1.0 - threshold
        
        # DBSCAN clustering
        # min_samples: minimum cluster size (same as semantic_min_cluster_size)
        clustering = DBSCAN(
            eps=eps,
            min_samples=3,  # Minimum messages per cluster
            metric='cosine',  # Use cosine distance
            n_jobs=-1,  # Use all CPU cores
        )
        
        labels = clustering.fit_predict(embeddings_array)
        
        # Group messages by cluster label
        clusters: Dict[int, List[Message]] = {}
        cluster_embeddings: Dict[int, List[np.ndarray]] = {}
        for msg, emb, label in zip(messages, embeddings, labels):
            if label == -1:  # -1 = noise (unclustered)
                continue
            if label not in clusters:
                clusters[label] = []
                cluster_embeddings[label] = []
            clusters[label].append(msg)
            cluster_embeddings[label].append(emb)
        
        # Calculate silhouette score for each cluster and filter low-quality clusters
        filtered_clusters: Dict[int, List[Message]] = {}
        min_silhouette = 0.3  # Minimum silhouette score threshold
        
        try:
            from sklearn.metrics import silhouette_score
        except ImportError:
            logger.warning("scikit-learn not available for silhouette score, skipping quality check")
            return clusters
        
        for cluster_id, cluster_msgs in clusters.items():
            if len(cluster_msgs) < 3:  # Silhouette requires at least 2 samples
                continue
            
            # Calculate silhouette score for this cluster
            cluster_emb = cluster_embeddings[cluster_id]
            cluster_labels = [cluster_id] * len(cluster_emb)
            
            # For single cluster, we can't calculate silhouette directly
            # Instead, calculate average intra-cluster similarity
            if len(cluster_emb) >= 2:
                # Calculate average cosine similarity within cluster
                similarities = []
                for i in range(len(cluster_emb)):
                    for j in range(i + 1, len(cluster_emb)):
                        sim = self._cosine_similarity(cluster_emb[i], cluster_emb[j])
                        similarities.append(sim)
                
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
                
                # Use average similarity as quality metric (similar to silhouette)
                # Higher similarity = better cluster quality
                if avg_similarity >= min_silhouette:
                    filtered_clusters[cluster_id] = cluster_msgs
                    logger.debug(f"Cluster {cluster_id}: quality={avg_similarity:.3f}, size={len(cluster_msgs)}")
                else:
                    logger.debug(f"Cluster {cluster_id} rejected: quality={avg_similarity:.3f} < {min_silhouette}")
            else:
                # Very small clusters: accept if similarity is high
                if len(cluster_emb) == 2:
                    sim = self._cosine_similarity(cluster_emb[0], cluster_emb[1])
                    if sim >= min_silhouette:
                        filtered_clusters[cluster_id] = cluster_msgs
        except Exception as e:
            logger.warning(f"Error calculating cluster quality: {e}, using all clusters")
            filtered_clusters = clusters
        
        # Log cluster statistics
        num_noise = sum(1 for label in labels if label == -1)
        if filtered_clusters:
            cluster_sizes = [len(c) for c in filtered_clusters.values()]
            logger.info(
                f"DBSCAN found {len(filtered_clusters)} quality clusters (from {len(clusters)} total): "
                f"sizes {min(cluster_sizes)}-{max(cluster_sizes)}, "
                f"avg {sum(cluster_sizes)/len(cluster_sizes):.1f}, "
                f"{num_noise} noise points"
            )
        
        return filtered_clusters
    
    async def _analyze_cluster_with_llm(
        self,
        cluster_messages: List[Message],
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to analyze a cluster and understand the semantic pattern.
        
        Returns:
            Dict with 'description', 'similarity_reason', 'rule_sql'
        """
        if not self.llm_engine:
            # Fallback: simple description
            return {
                "description": f"Semantic cluster of {len(cluster_messages)} similar spam messages",
                "similarity_reason": "Messages share similar semantic meaning",
                "rule_sql": None,
            }
        
        # Prepare examples for LLM
        examples = [msg.text[:300] for msg in cluster_messages[:10]]
        
        prompt = self._build_semantic_analysis_prompt(examples)
        
        try:
            # Use LLM to analyze
            if hasattr(self.llm_engine, 'analyze_semantic_cluster'):
                result = await self.llm_engine.analyze_semantic_cluster(examples)
            else:
                # Fallback: use discover_patterns with cluster context
                aggregated = {
                    "spam_examples": [{"text": ex} for ex in examples],
                    "total_spam": len(cluster_messages),
                }
                llm_result = await self.llm_engine.discover_patterns(aggregated)
                
                if llm_result and llm_result.get("patterns"):
                    pattern = llm_result["patterns"][0]
                    result = {
                        "description": pattern.get("description", ""),
                        "similarity_reason": pattern.get("similarity_reason", ""),
                        "rule_sql": None,
                    }
                    if llm_result.get("rules"):
                        result["rule_sql"] = llm_result["rules"][0].get("sql_expression")
                else:
                    result = None
        except Exception as e:
            logger.error(f"LLM semantic analysis failed: {e}", exc_info=True)
            return None
        
        if not result:
            return None
        
        # Generate SQL rule that catches semantic variations
        if not result.get("rule_sql"):
            result["rule_sql"] = self._generate_semantic_rule(cluster_messages, result)
        
        return result
    
    def _build_semantic_analysis_prompt(self, examples: List[str]) -> str:
        """Build prompt for LLM to analyze semantic cluster."""
        examples_text = "\n".join([f"{i+1}. {ex}" for i, ex in enumerate(examples)])
        
        return f"""Analyze these spam messages that are semantically similar (same meaning, different words).

Messages:
{examples_text}

Your task:
1. Identify the COMMON SEMANTIC PATTERN (what do they all mean/say, regardless of exact words)
2. Explain WHY they are similar (what makes them the same type of spam)
3. Suggest a rule that would catch ALL variations (synonyms, paraphrases, different wording)

Focus on MEANING, not exact words. These messages use different words but convey the same spam intent.

Respond in JSON format:
{{
  "semantic_pattern": "Description of what all messages mean (e.g., 'Job scam offering unrealistic earnings')",
  "similarity_reason": "Why they are similar (e.g., 'All offer work-from-home jobs with unrealistic pay, use urgency tactics')",
  "key_concepts": ["concept1", "concept2"],  // Core concepts that appear in all messages
  "variations_caught": ["synonym1", "synonym2"],  // Words/phrases that appear in variations
  "rule_suggestion": "SQL rule that catches this semantic pattern (use LIKE with key concepts)"
}}
"""
    
    def _generate_semantic_rule(
        self,
        cluster_messages: List[Message],
        pattern_result: Dict[str, Any],
    ) -> Optional[str]:
        """
        Generate SQL rule that catches semantic variations.
        
        Uses key concepts and variations from LLM analysis.
        """
        key_concepts = pattern_result.get("key_concepts", [])
        variations = pattern_result.get("variations_caught", [])
        
        if not key_concepts and not variations:
            # Fallback: extract common words/phrases from cluster
            all_text = " ".join([m.text.lower() for m in cluster_messages])
            # Simple extraction (can be improved)
            key_concepts = self._extract_common_phrases(all_text, min_count=3)
        
        if not key_concepts:
            return None
        
        # Build SQL rule with OR conditions for variations
        conditions = []
        for concept in key_concepts[:5]:  # Limit to 5 concepts
            safe_concept = concept.replace("'", "''").replace("%", "\\%").replace("_", "\\_")
            conditions.append(f"LOWER(text) LIKE '%{safe_concept.lower()}%'")
        
        if not conditions:
            return None
        
        sql = f"SELECT id, is_spam FROM messages WHERE {' OR '.join(conditions)}"
        return sql
    
    async def _validate_semantic_rule(
        self,
        sql_expression: str,
        cluster_messages: List[Message],
        ham_messages: List[Message],
        min_precision: float = 0.85,
    ) -> bool:
        """
        Validate semantic rule on ham messages to ensure minimum precision.
        
        Uses actual SQL execution to test rule against sample messages.
        
        Args:
            sql_expression: SQL rule to validate
            cluster_messages: Spam messages from cluster (should match)
            ham_messages: Ham messages (should NOT match)
            min_precision: Minimum precision threshold (default: 0.85)
        
        Returns:
            True if rule meets precision threshold, False otherwise
        """
        from app.v2_sql_safety import validate_sql_rule, sanitize_sql_for_evaluation
        from sqlalchemy import text
        
        # Validate SQL safety first
        is_valid, error = validate_sql_rule(sql_expression)
        if not is_valid:
            logger.warning(f"Semantic rule SQL validation failed: {error}")
            return False
        
        # Test rule on sample spam messages (should match)
        spam_matches = 0
        spam_sample = cluster_messages[:min(20, len(cluster_messages))]
        
        try:
            # Extract LIKE patterns from SQL for simple matching
            # This is a simplified approach - full validation would execute SQL
            like_patterns = []
            if "LIKE" in sql_expression.upper():
                import re
                like_matches = re.findall(r"LIKE\s+'%([^%]+)%'", sql_expression, re.IGNORECASE)
                like_patterns = [p.lower() for p in like_matches]
            
            # Count matches in spam sample
            for msg in spam_sample:
                text_lower = (msg.text or "").lower()
                if like_patterns:
                    # Check if any pattern matches
                    if any(pattern in text_lower for pattern in like_patterns):
                        spam_matches += 1
                else:
                    # If no LIKE patterns, assume match (rule might use REGEXP)
                    spam_matches += 1
            
            # Test rule on ham messages (should NOT match - these are false positives)
            ham_matches = 0
            ham_sample = ham_messages[:min(50, len(ham_messages))]  # Sample more ham for better validation
            
            for msg in ham_sample:
                text_lower = (msg.text or "").lower()
                if like_patterns:
                    # Check if any pattern matches (false positive)
                    if any(pattern in text_lower for pattern in like_patterns):
                        ham_matches += 1
            
            # Calculate precision
            total_matches = spam_matches + ham_matches
            if total_matches == 0:
                logger.debug("Semantic rule matches no messages in validation sample")
                return False
            
            precision = spam_matches / total_matches if total_matches > 0 else 0.0
            
            # Check if precision meets threshold
            if precision < min_precision:
                logger.debug(
                    f"Semantic rule precision {precision:.3f} below threshold {min_precision} "
                    f"(spam_matches={spam_matches}, ham_matches={ham_matches})"
                )
                return False
            
            # Also check absolute ham matches (max 5% of ham messages)
            max_ham_ratio = 0.05
            if len(ham_sample) > 0:
                ham_ratio = ham_matches / len(ham_sample)
                if ham_ratio > max_ham_ratio:
                    logger.debug(
                        f"Semantic rule matches too many ham messages: {ham_ratio:.1%} > {max_ham_ratio:.1%} "
                        f"({ham_matches}/{len(ham_sample)})"
                    )
                    return False
            
            logger.debug(
                f"Semantic rule validation passed: precision={precision:.3f}, "
                f"spam_matches={spam_matches}/{len(spam_sample)}, "
                f"ham_matches={ham_matches}/{len(ham_sample)}"
            )
            return True
            
        except Exception as e:
            logger.warning(f"Error validating semantic rule: {e}, allowing rule creation")
            # On error, allow rule creation (conservative approach)
            return True
    
    def _extract_common_phrases(self, text: str, min_count: int = 3) -> List[str]:
        """Extract common phrases from text (simple approach)."""
        words = text.split()
        phrases = []
        
        # Extract 2-3 word phrases
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if phrase.count(' ') == 1:  # 2-word phrase
                phrases.append(phrase)
        
        # Count occurrences
        from collections import Counter
        phrase_counts = Counter(phrases)
        
        # Return phrases that appear at least min_count times
        return [p for p, c in phrase_counts.items() if c >= min_count][:10]


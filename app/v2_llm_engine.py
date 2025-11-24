"""
LLM abstraction for pattern mining.

Allows swapping LLM providers (cloud vs on-prem) for pattern discovery.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import httpx

logger = logging.getLogger(__name__)


class PatternMiningEngine(ABC):
    """Abstract interface for pattern mining engines (LLM-based)."""
    
    @abstractmethod
    async def discover_patterns(
        self,
        aggregated_signals: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Discover patterns from aggregated signals.
        
        Args:
            aggregated_signals: Compact summary of spam patterns (URLs, keywords, examples)
        
        Returns:
            Dict with discovered patterns and suggested rules, or None if failed
        """
        pass


class OpenAIPatternMiningEngine(PatternMiningEngine):
    """OpenAI-based pattern mining engine (default implementation)."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    def _get_client(self):
        """Get OpenAI client (lazy initialization)."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI package not installed")
                return None
        return self._client
    
    async def discover_patterns(
        self,
        aggregated_signals: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Use OpenAI to discover patterns from aggregated signals.
        
        Returns structured patterns and rule suggestions.
        """
        client = self._get_client()
        if not client:
            return None
        
        # Prepare compact prompt
        prompt = self._build_prompt(aggregated_signals)
        
        try:
            # Run sync OpenAI client in executor for async compatibility
            import asyncio
            import json
            
            loop = asyncio.get_event_loop()
            
            def _call_openai():
                return client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a spam pattern detection expert. Analyze spam signals and suggest SQL blocking rules."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=1500,
                    temperature=0.2,
                )
            
            response = await loop.run_in_executor(None, _call_openai)
            result = json.loads(response.choices[0].message.content)
            return result
            
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            # Handle JSON parsing errors, malformed responses
            logger.error(f"OpenAI pattern discovery failed (data error): {e}", exc_info=True)
            return None
        except Exception as e:
            # Catch-all for network errors, API errors, etc.
            logger.error(f"OpenAI pattern discovery failed (unexpected error): {e}", exc_info=True)
            return None
    
    def _build_prompt(self, aggregated_signals: Dict[str, Any]) -> str:
        """Build compact prompt from aggregated signals."""
        prompt = f"""Analyze these spam patterns and suggest SQL blocking rules.

CRITICAL SAFETY REQUIREMENTS:
1. Generate NARROW, INTERPRETABLE patterns focused on explicit commercial/abusive spam
2. Avoid over-broad rules (e.g., matching all messages with "price" or "group")
3. NEVER base rules on sensitive attributes: politics, religion, race, ethnicity, gender, sexual orientation
4. SQL rules MUST be safe SELECT queries only:
   - Format: SELECT id, is_spam FROM messages WHERE <conditions>
   - Only whitelisted columns: id, text, is_spam, timestamp, language, sender, source, country, has_media
   - No subqueries, no semicolons, no UPDATE/DELETE/INSERT
   - No "match everything" patterns (WHERE 1=1, empty WHERE, etc.)
   - Rules should match <80% of all messages (if too broad, reject the pattern)

IMPORTANT: Focus on SEMANTIC PATTERNS (meaning), not exact words. Spammers use synonyms, 
paraphrases, and variations. Your rules should catch ALL variations of the same spam intent.

Spam Statistics:
- Total spam messages: {aggregated_signals.get('total_spam', 0)}
- Total ham messages: {aggregated_signals.get('total_ham', 0)}

Top URL Patterns:
{self._format_list(aggregated_signals.get('url_patterns', {}).keys(), limit=5)}

Top Keyword Patterns:
{self._format_list(aggregated_signals.get('keyword_patterns', {}).keys(), limit=10)}

Sample Spam Messages (analyze for SEMANTIC similarity):
{self._format_examples(aggregated_signals.get('spam_examples', []), limit=10)}

Your task:
1. Identify NARROW SEMANTIC PATTERNS (what do messages mean, not exact words)
   - Focus on explicit commercial spam (job scams, fake money-making, phishing)
   - Focus on abusive patterns (harassment, threats, explicit content promotion)
   - Avoid patterns that would match legitimate discussions
2. Group messages by semantic similarity (same spam intent, different wording)
3. Generate SAFE SQL rules that catch ALL variations (synonyms, paraphrases, different phrasings)
   - Rules must be specific enough to avoid false positives
   - Rules must use only whitelisted columns
   - Rules must not match >80% of messages

Example (GOOD):
- Messages: "Earn money fast!", "Get rich quick!", "Make cash now!"
- Semantic pattern: "Unrealistic income promises with urgency"
- Rule: SELECT id, is_spam FROM messages WHERE (LOWER(text) LIKE '%earn money%' OR LOWER(text) LIKE '%get rich%' OR LOWER(text) LIKE '%make cash%') AND (LOWER(text) LIKE '%fast%' OR LOWER(text) LIKE '%quick%' OR LOWER(text) LIKE '%now%')

Example (BAD - too broad):
- Pattern: "Any message mentioning price"
- Rule: SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%price%'
- Why bad: Would match legitimate price discussions

Example (BAD - sensitive attribute):
- Pattern: "Messages from specific political group"
- Why bad: Never base rules on politics, religion, race, etc.

Provide a JSON response with:
{{
  "patterns": [
    {{
      "type": "url|keyword|signature",
      "description": "Narrow semantic pattern description (explicit commercial/abusive spam only)",
      "similarity_reason": "Why messages are semantically similar (e.g., 'All offer unrealistic work-from-home earnings with urgency tactics, use different words but same scam intent')",
      "key_concepts": ["concept1", "concept2"],  // Core concepts that define this pattern
      "variations": ["synonym1", "synonym2"],  // Words/phrases that appear in variations
      "examples": ["example1", "example2"]
    }}
  ],
  "rules": [
    {{
      "pattern_type": "url|keyword|semantic",
      "sql_expression": "SELECT id, is_spam FROM messages WHERE (LOWER(text) LIKE '%concept1%' OR LOWER(text) LIKE '%concept2%' OR LOWER(text) LIKE '%synonym1%')",
      "description": "Safe SQL rule that catches semantic variations (narrow, interpretable, no sensitive attributes)"
    }}
  ]
}}
"""
        return prompt
    
    def _format_list(self, items, limit: int = 10) -> str:
        """Format list for prompt."""
        items_list = list(items)[:limit]
        return "\n".join(f"- {item}" for item in items_list)
    
    def _format_examples(self, examples: List[Dict[str, Any]], limit: int = 5) -> str:
        """Format examples for prompt."""
        examples_list = examples[:limit]
        formatted = []
        for i, ex in enumerate(examples_list, 1):
            text = ex.get("text", "")[:200]
            formatted.append(f"{i}. {text}")
        return "\n".join(formatted)


class LocalHttpPatternMiningEngine(PatternMiningEngine):
    """
    LLM engine that talks to a local/self-hosted model over HTTP.
    
    Typical use-case: Mistral-7B-Instruct served via vLLM / TGI / Ollama.
    The endpoint is expected to follow OpenAI-compatible chat completion API.
    """
    
    def __init__(
        self,
        endpoint_url: str,
        model: str = "mistralai/Mistral-7B-Instruct-v0.2",
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize local HTTP LLM engine.
        
        Args:
            endpoint_url: Base URL for LLM endpoint (e.g., "http://localhost:8000/v1")
            model: Model identifier (e.g., "mistralai/Mistral-7B-Instruct-v0.2")
            api_key: Optional API key for authentication
            timeout_seconds: Request timeout in seconds
            client: Optional httpx.AsyncClient (for testing or custom configuration)
        """
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._client = client
    
    def _get_client(self) -> Optional[httpx.AsyncClient]:
        """Get or create httpx client."""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
            )
        return self._client
    
    async def discover_patterns(
        self,
        aggregated_signals: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Use local HTTP endpoint to discover patterns from aggregated signals.
        
        Request format:
        POST {endpoint_url}/chat/completions
        {
            "model": "<model>",
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "<prompt>"}
            ],
            "max_tokens": 1500,
            "temperature": 0.0
        }
        
        Response format (OpenAI-compatible):
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "{...}"
                    }
                }
            ]
        }
        """
        client = self._get_client()
        if not client:
            return None
        
        # Build prompt (reuse OpenAI engine's prompt builder)
        prompt = self._build_prompt(aggregated_signals)
        
        url = f"{self.endpoint_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a spam pattern detection expert. Analyze spam signals and suggest SQL blocking rules."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.0,  # Low temperature for deterministic outputs
        }
        
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse OpenAI-compatible response
            if "choices" not in data or not data["choices"]:
                logger.error("Local LLM endpoint returned unexpected format: missing 'choices'")
                return None
            
            content = data["choices"][0].get("message", {}).get("content", "")
            if not content:
                logger.error("Local LLM endpoint returned empty content")
                return None
            
            # Parse JSON response
            result = json.loads(content)
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Local LLM HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                exc_info=False,
            )
            return None
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            # Handle JSON parsing errors, malformed responses
            logger.error(f"Local LLM pattern discovery failed (data error): {e}", exc_info=True)
            return None
        except Exception as e:
            # Catch-all for network errors, timeouts, etc.
            logger.error(f"Local LLM pattern discovery failed (unexpected error): {e}", exc_info=True)
            return None
    
    def _build_prompt(self, aggregated_signals: Dict[str, Any]) -> str:
        """
        Build prompt from aggregated signals.
        
        Reuses the same prompt format as OpenAI engine for consistency.
        """
        # Reuse OpenAI engine's prompt builder logic
        prompt = f"""Analyze these spam patterns and suggest SQL blocking rules.

CRITICAL SAFETY REQUIREMENTS:
1. Generate NARROW, INTERPRETABLE patterns focused on explicit commercial/abusive spam
2. Avoid over-broad rules (e.g., matching all messages with "price" or "group")
3. NEVER base rules on sensitive attributes: politics, religion, race, ethnicity, gender, sexual orientation
4. SQL rules MUST be safe SELECT queries only:
   - Format: SELECT id, is_spam FROM messages WHERE <conditions>
   - Only whitelisted columns: id, text, is_spam, timestamp, language, sender, source, country, has_media
   - No subqueries, no semicolons, no UPDATE/DELETE/INSERT
   - No "match everything" patterns (WHERE 1=1, empty WHERE, etc.)
   - Rules should match <80% of all messages (if too broad, reject the pattern)

IMPORTANT: Focus on SEMANTIC PATTERNS (meaning), not exact words. Spammers use synonyms, 
paraphrases, and variations. Your rules should catch ALL variations of the same spam intent.

CRITICAL RULES FOR QUALITY:
1. QUALITY OVER QUANTITY:
   - Generate rules for ~60-70% of patterns
   - For 30-40% of patterns, mark as INSIGHT_ONLY (too vague/risky)
   - Only create rules that are SPECIFIC and ACTIONABLE

2. PATTERN SPECIFICITY:
   - GOOD: "Crypto investment offers promising 10% daily ROI on cloud mining"
   - BAD: "Messages containing investment opportunities" (too broad)
   - GOOD: "Phishing emails impersonating PayPal payment failures"
   - BAD: "Payment-related messages" (catches legitimate support)

3. TIERING (BE STRICT):
   - SAFE_AUTO: High confidence (HIGH), Low risk (<10%). Very specific pattern.
   - REVIEW_ONLY: Medium confidence/risk (10-30%). Good pattern but needs verification.
   - DANGEROUS: High risk (30-75%). Insight only, SQL commented out.
   - INSIGHT_ONLY: Too vague (>75% risk) or LOW confidence. DO NOT generate SQL rule.

4. TRACEABILITY:
   - In 'description', MUST include matched IDs
   - Format: "Crypto investment scam pattern. Matches IDs: 12, 15, 23, 45, 67"
   - Use 3-10 IDs from the provided example_ids (or placeholder if not available)

Spam Statistics:
- Total spam messages: {aggregated_signals.get('total_spam', 0)}
- Total ham messages: {aggregated_signals.get('total_ham', 0)}

Top URL Patterns:
{self._format_list(aggregated_signals.get('url_patterns', {}).keys(), limit=5)}

Top Keyword Patterns:
{self._format_list(aggregated_signals.get('keyword_patterns', {}).keys(), limit=10)}

Sample Spam Messages (analyze for SEMANTIC similarity):
{self._format_examples(aggregated_signals.get('spam_examples', []), limit=10)}

Your task:
1. Identify NARROW SEMANTIC PATTERNS (what do messages mean, not exact words)
   - Focus on explicit commercial spam (job scams, fake money-making, phishing)
   - Focus on abusive patterns (harassment, threats, explicit content promotion)
   - Avoid patterns that would match legitimate discussions
2. Group messages by semantic similarity (same spam intent, different wording)
3. Generate SAFE SQL rules that catch ALL variations (synonyms, paraphrases, different phrasings)
   - Rules must be specific enough to avoid false positives
   - Rules must use only whitelisted columns
   - Rules must not match >80% of messages

Example (GOOD):
- Messages: "Earn money fast!", "Get rich quick!", "Make cash now!"
- Semantic pattern: "Unrealistic income promises with urgency"
- Rule: SELECT id, is_spam FROM messages WHERE (LOWER(text) LIKE '%earn money%' OR LOWER(text) LIKE '%get rich%' OR LOWER(text) LIKE '%make cash%') AND (LOWER(text) LIKE '%fast%' OR LOWER(text) LIKE '%quick%' OR LOWER(text) LIKE '%now%')

Example (BAD - too broad):
- Pattern: "Any message mentioning price"
- Rule: SELECT id, is_spam FROM messages WHERE LOWER(text) LIKE '%price%'
- Why bad: Would match legitimate price discussions

Example (BAD - sensitive attribute):
- Pattern: "Messages from specific political group"
- Why bad: Never base rules on politics, religion, race, etc.

Provide a JSON response with:
{{
  "patterns": [
    {{
      "type": "url|keyword|signature",
      "description": "Narrow semantic pattern description (explicit commercial/abusive spam only)",
      "similarity_reason": "Why messages are semantically similar (e.g., 'All offer unrealistic work-from-home earnings with urgency tactics, use different words but same scam intent')",
      "key_concepts": ["concept1", "concept2"],  // Core concepts that define this pattern
      "variations": ["synonym1", "synonym2"],  // Words/phrases that appear in variations
      "examples": ["example1", "example2"]
    }}
  ],
  "rules": [
    {{
      "pattern_type": "url|keyword|semantic",
      "sql_expression": "SELECT id, is_spam FROM messages WHERE (LOWER(text) LIKE '%concept1%' OR LOWER(text) LIKE '%concept2%' OR LOWER(text) LIKE '%synonym1%')",
      "description": "Safe SQL rule that catches semantic variations (narrow, interpretable, no sensitive attributes)"
    }}
  ]
}}
"""
        return prompt
    
    def _format_list(self, items, limit: int = 10) -> str:
        """Format list for prompt."""
        items_list = list(items)[:limit]
        return "\n".join(f"- {item}" for item in items_list)
    
    def _format_examples(self, examples: List[Dict[str, Any]], limit: int = 5) -> str:
        """Format examples for prompt."""
        examples_list = examples[:limit]
        formatted = []
        for i, ex in enumerate(examples_list, 1):
            text = ex.get("text", "")[:200]
            formatted.append(f"{i}. {text}")
        return "\n".join(formatted)


def create_mining_engine(
    provider: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    **kwargs,
) -> Optional[PatternMiningEngine]:
    """
    Factory function to create pattern mining engine.
    
    Args:
        provider: Engine provider ("openai", "local", etc.)
        api_key: API key for cloud providers (required for OpenAI, optional for local)
        base_url: Base URL for local HTTP endpoint (if provider="local")
        timeout_seconds: Request timeout in seconds (for local HTTP)
        **kwargs: Additional provider-specific config (e.g., model)
    
    Returns:
        PatternMiningEngine instance or None if provider not available
    """
    if provider == "openai" or provider == "default":
        return OpenAIPatternMiningEngine(
            api_key=api_key,
            model=kwargs.get("model", "gpt-4o-mini")
        )
    elif provider == "local":
        if not base_url:
            logger.warning("Local LLM provider requires base_url, falling back to None")
            return None
        return LocalHttpPatternMiningEngine(
            endpoint_url=base_url,
            model=kwargs.get("model", "mistralai/Mistral-7B-Instruct-v0.2"),
            api_key=api_key,
            timeout_seconds=timeout_seconds or 30.0,
        )
    elif provider == "none" or provider == "disabled":
        return None
    else:
        logger.warning(f"Unknown LLM provider: {provider}, falling back to None")
        return None


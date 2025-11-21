"""
Embedding engine abstraction for semantic pattern mining.

Allows using different embedding providers (OpenAI, local models, etc.)
for generating semantic embeddings of messages.

Includes caching to avoid redundant API calls.
"""

import logging
from typing import List, Optional
from abc import ABC, abstractmethod
import numpy as np
import httpx

logger = logging.getLogger(__name__)


class EmbeddingEngine(ABC):
    """Abstract interface for embedding engines."""
    
    @abstractmethod
    async def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings
        
        Returns:
            List of numpy arrays (embeddings)
        """
        pass


class OpenAIEmbeddingEngine(EmbeddingEngine):
    """OpenAI-based embedding engine with automatic batching and caching."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small", batch_size: int = 2048, use_cache: bool = True):
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size  # OpenAI API limit
        self.use_cache = use_cache
        self._client = None
        self._cache = None  # Lazy initialization
    
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
    
    def _get_cache(self):
        """Get embedding cache (lazy initialization)."""
        if self._cache is None and self.use_cache:
            from app.embedding_cache import get_embedding_cache
            self._cache = get_embedding_cache()
        return self._cache
    
    async def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using OpenAI API with automatic batching and caching.
        
        Splits large requests into batches of self.batch_size to respect API limits.
        Uses cache to avoid redundant API calls.
        """
        client = self._get_client()
        if not client:
            return []
        
        # Try cache first
        cache = self._get_cache()
        if cache:
            cached_embeddings, uncached_texts = cache.get_batch(texts)
            
            if not uncached_texts:
                # All embeddings cached
                logger.info(f"All {len(texts)} embeddings retrieved from cache")
                return [emb for emb in cached_embeddings if emb is not None]
            
            # Generate embeddings for uncached texts
            logger.info(f"Cache: {len(texts) - len(uncached_texts)}/{len(texts)} embeddings cached, generating {len(uncached_texts)}")
            new_embeddings = await self._generate_embeddings_with_batching(uncached_texts)
            
            if not new_embeddings:
                return []
            
            # Cache new embeddings
            cache.set_batch(uncached_texts, new_embeddings)
            
            # Merge cached and new embeddings in correct order
            result = []
            new_idx = 0
            for cached_emb in cached_embeddings:
                if cached_emb is not None:
                    result.append(cached_emb)
                else:
                    result.append(new_embeddings[new_idx])
                    new_idx += 1
            
            return result
        else:
            # No cache, generate all
            return await self._generate_embeddings_with_batching(texts)
    
    async def _generate_embeddings_with_batching(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings with batching (no caching)."""
        # If texts fit in one batch, use simple approach
        if len(texts) <= self.batch_size:
            return await self._generate_batch(texts)
        
        # Otherwise, batch the requests
        logger.info(f"Batching {len(texts)} texts into chunks of {self.batch_size}")
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self._generate_batch(batch)
            
            if not batch_embeddings:
                logger.warning(f"Failed to generate embeddings for batch {i//self.batch_size + 1}")
                # Return empty list on any batch failure
                return []
            
            all_embeddings.extend(batch_embeddings)
            logger.debug(f"Generated embeddings for batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1}")
        
        logger.info(f"Generated {len(all_embeddings)} embeddings in {(len(texts)-1)//self.batch_size + 1} batches")
        return all_embeddings
    
    async def _generate_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for a single batch."""
        client = self._get_client()
        if not client:
            return []
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _call_openai():
                response = client.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                return [np.array(item.embedding) for item in response.data]
            
            embeddings = await loop.run_in_executor(None, _call_openai)
            return embeddings
            
        except (ValueError, KeyError, AttributeError) as e:
            # Handle data structure errors (malformed response, missing fields)
            logger.error(f"OpenAI embedding generation failed (data error): {e}", exc_info=True)
            return []
        except Exception as e:
            # Catch-all for network errors, API errors, etc.
            logger.error(f"OpenAI embedding generation failed (unexpected error): {e}", exc_info=True)
            return []


class LocalHttpEmbeddingEngine(EmbeddingEngine):
    """
    Embedding engine that calls a local/self-hosted HTTP endpoint.
    
    The endpoint is expected to accept a JSON payload with a list of texts and
    return a JSON payload with a list of float32 embeddings.
    
    Typical use-case: BGE-M3 or similar models served via vLLM/TGI/Ollama.
    """
    
    def __init__(
        self,
        endpoint_url: str,
        model: str = "BAAI/bge-m3",
        api_key: Optional[str] = None,
        batch_size: int = 512,
        timeout_seconds: float = 30.0,
        use_cache: bool = True,
        client: Optional[httpx.AsyncClient] = None,
    ):
        """
        Initialize local HTTP embedding engine.
        
        Args:
            endpoint_url: Base URL for embedding endpoint (e.g., "http://localhost:8080/v1")
            model: Model identifier (e.g., "BAAI/bge-m3")
            api_key: Optional API key for authentication
            batch_size: Batch size for embedding generation (default: 512 for local models)
            timeout_seconds: Request timeout in seconds
            use_cache: Whether to use embedding cache
            client: Optional httpx.AsyncClient (for testing or custom configuration)
        """
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.use_cache = use_cache
        self._client = client
        self._cache = None  # Lazy initialization
    
    def _get_client(self) -> Optional[httpx.AsyncClient]:
        """Get or create httpx client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
            )
        return self._client
    
    def _get_cache(self):
        """Get embedding cache (lazy initialization)."""
        if self._cache is None and self.use_cache:
            from app.embedding_cache import get_embedding_cache
            self._cache = get_embedding_cache()
        return self._cache
    
    async def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using local HTTP endpoint with automatic batching and caching.
        
        Request format:
        POST {endpoint_url}/embeddings
        {
            "model": "<model>",
            "inputs": ["text1", "text2", ...]
        }
        
        Response format:
        {
            "embeddings": [
                [0.1, 0.2, ...],
                [0.3, 0.4, ...]
            ]
        }
        """
        if not texts:
            return []
        
        client = self._get_client()
        if not client:
            return []
        
        # Try cache first
        cache = self._get_cache()
        if cache:
            cached_embeddings, uncached_texts = cache.get_batch(texts)
            
            if not uncached_texts:
                # All embeddings cached
                logger.info(f"All {len(texts)} embeddings retrieved from cache")
                return [emb for emb in cached_embeddings if emb is not None]
            
            # Generate embeddings for uncached texts
            logger.info(f"Cache: {len(texts) - len(uncached_texts)}/{len(texts)} embeddings cached, generating {len(uncached_texts)}")
            new_embeddings = await self._generate_embeddings_with_batching(uncached_texts, client)
            
            if not new_embeddings:
                return []
            
            # Cache new embeddings
            cache.set_batch(uncached_texts, new_embeddings)
            
            # Merge cached and new embeddings in correct order
            result = []
            new_idx = 0
            for cached_emb in cached_embeddings:
                if cached_emb is not None:
                    result.append(cached_emb)
                else:
                    result.append(new_embeddings[new_idx])
                    new_idx += 1
            
            return result
        else:
            # No cache, generate all
            return await self._generate_embeddings_with_batching(texts, client)
    
    async def _generate_embeddings_with_batching(
        self,
        texts: List[str],
        client: httpx.AsyncClient,
    ) -> List[np.ndarray]:
        """Generate embeddings with batching (no caching)."""
        # If texts fit in one batch, use simple approach
        if len(texts) <= self.batch_size:
            return await self._generate_batch(texts, client)
        
        # Otherwise, batch the requests
        logger.info(f"Batching {len(texts)} texts into chunks of {self.batch_size}")
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self._generate_batch(batch, client)
            
            if not batch_embeddings:
                logger.warning(f"Failed to generate embeddings for batch {i//self.batch_size + 1}")
                # Return empty list on any batch failure
                return []
            
            all_embeddings.extend(batch_embeddings)
            logger.debug(f"Generated embeddings for batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1}")
        
        logger.info(f"Generated {len(all_embeddings)} embeddings in {(len(texts)-1)//self.batch_size + 1} batches")
        return all_embeddings
    
    async def _generate_batch(
        self,
        texts: List[str],
        client: httpx.AsyncClient,
    ) -> List[np.ndarray]:
        """Generate embeddings for a single batch."""
        url = f"{self.endpoint_url}/embeddings"
        
        payload = {
            "model": self.model,
            "inputs": texts,
        }
        
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse response: expect {"embeddings": [[...], [...]]}
            if "embeddings" not in data:
                logger.error(f"Local embedding endpoint returned unexpected format: missing 'embeddings' key")
                return []
            
            embeddings_list = data["embeddings"]
            if not isinstance(embeddings_list, list):
                logger.error(f"Local embedding endpoint returned unexpected format: 'embeddings' is not a list")
                return []
            
            if len(embeddings_list) != len(texts):
                logger.warning(f"Local embedding endpoint returned {len(embeddings_list)} embeddings for {len(texts)} texts")
            
            # Convert to numpy arrays
            result = []
            for emb in embeddings_list:
                if not isinstance(emb, list):
                    logger.error(f"Local embedding endpoint returned non-list embedding: {type(emb)}")
                    return []
                result.append(np.array(emb, dtype=np.float32))
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Local embedding HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                exc_info=False,
            )
            return []
        except (ValueError, KeyError, TypeError) as e:
            # Handle JSON parsing errors, malformed responses
            logger.error(f"Local embedding generation failed (data error): {e}", exc_info=True)
            return []
        except Exception as e:
            # Catch-all for network errors, timeouts, etc.
            logger.error(f"Local embedding generation failed (unexpected error): {e}", exc_info=True)
            return []


class LocalEmbeddingEngine(EmbeddingEngine):
    """
    Local embedding engine with batching support.
    
    Can be implemented using:
    - sentence-transformers
    - onnx models
    - other local embedding models
    """
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size  # For local models, smaller batches for memory
        self._model = None
    
    def _load_model(self):
        """Lazy load local embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                logger.warning("sentence-transformers not installed, embeddings unavailable")
                return None
        return self._model
    
    async def generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings using local model with batching.
        
        Batches for memory efficiency with local models.
        """
        model = self._load_model()
        if not model:
            return []
        
        # If texts fit in one batch, use simple approach
        if len(texts) <= self.batch_size:
            return await self._encode_batch(texts)
        
        # Otherwise, batch the requests
        logger.info(f"Batching {len(texts)} texts into chunks of {self.batch_size}")
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_embeddings = await self._encode_batch(batch)
            
            if not batch_embeddings:
                logger.warning(f"Failed to generate embeddings for batch {i//self.batch_size + 1}")
                return []
            
            all_embeddings.extend(batch_embeddings)
        
        logger.info(f"Generated {len(all_embeddings)} embeddings in {(len(texts)-1)//self.batch_size + 1} batches")
        return all_embeddings
    
    async def _encode_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Encode a single batch using local model."""
        model = self._load_model()
        if not model:
            return []
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def _encode():
                embeddings = model.encode(texts, convert_to_numpy=True)
                return [np.array(emb) for emb in embeddings]
            
            embeddings = await loop.run_in_executor(None, _encode)
            return embeddings
            
        except (ValueError, AttributeError, ImportError) as e:
            # Handle data/model errors
            logger.error(f"Local embedding generation failed (data/model error): {e}", exc_info=True)
            return []
        except Exception as e:
            # Catch-all for unexpected errors
            logger.error(f"Local embedding generation failed (unexpected error): {e}", exc_info=True)
            return []


def create_embedding_engine(
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    batch_size: Optional[int] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> Optional[EmbeddingEngine]:
    """
    Create embedding engine based on provider.
    
    Args:
        provider: "openai", "local", or "none"
        api_key: API key for provider (required for OpenAI, optional for local)
        model: Model name (defaults based on provider)
        batch_size: Batch size for embedding generation (defaults: 2048 for OpenAI, 512 for local HTTP, 32 for local sentence-transformers)
        base_url: Base URL for local HTTP endpoint (if provider="local" and using HTTP)
        timeout_seconds: Request timeout in seconds (for local HTTP)
    
    Returns:
        EmbeddingEngine instance or None
    """
    if provider == "openai" or provider == "none":
        if provider == "none":
            return None
        return OpenAIEmbeddingEngine(
            api_key=api_key,
            model=model or "text-embedding-3-small",
            batch_size=batch_size or 2048,
        )
    elif provider == "local":
        # If base_url is provided, use HTTP-based local engine
        if base_url:
            return LocalHttpEmbeddingEngine(
                endpoint_url=base_url,
                model=model or "BAAI/bge-m3",
                api_key=api_key,
                batch_size=batch_size or 512,
                timeout_seconds=timeout_seconds or 30.0,
            )
        else:
            # Fall back to sentence-transformers based engine
            return LocalEmbeddingEngine(
                model_name=model or "sentence-transformers/all-MiniLM-L6-v2",
                batch_size=batch_size or 32,
            )
    else:
        logger.warning(f"Unknown embedding provider: {provider}")
        return None


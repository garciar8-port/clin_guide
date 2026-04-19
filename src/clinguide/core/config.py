from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CLINGUIDE_", "env_file": ".env"}

    # --- API keys ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    cohere_api_key: str = ""
    pinecone_api_key: str = ""

    # --- Pinned model IDs ---
    claude_model: str = "claude-sonnet-4-20250514"
    claude_classifier_model: str = "claude-haiku-4-5-20251001"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    cohere_rerank_model: str = "rerank-english-v3.0"

    # --- Pinecone ---
    pinecone_index: str = "clinguide"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # --- Retrieval ---
    retrieval_top_k: int = 20
    rerank_top_n: int = 5
    rrf_weight: float = 0.5
    rrf_k: int = 60
    abstain_threshold: float = 0.3

    # --- Chunking ---
    chunk_target_tokens: int = 800
    chunk_overlap_tokens: int = 120

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


settings = Settings()

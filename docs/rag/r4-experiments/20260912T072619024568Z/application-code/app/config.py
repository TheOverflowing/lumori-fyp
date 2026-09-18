from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
import os
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Endpoint:
    base_url: str = ''
    api_key: str = field(default='', repr=False)
    model: str = ''
    path: str = ''
    extra: dict = field(default_factory=dict)

    @property
    def configured(self):
        return bool(self.base_url and self.model and self.api_key)

    @property
    def signature(self):
        # Credentials are deliberately excluded. Endpoint/model changes require reindexing.
        value = json.dumps([self.base_url, self.path, self.model, self.extra], sort_keys=True)
        return hashlib.sha256(value.encode()).hexdigest()[:20]

    def require(self, capability):
        if not self.configured:
            raise ValueError(f'{capability} API 尚未配置。请在本地 .env 中设置地址、模型和密钥后重启。')
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise ValueError(f'{capability} API 地址格式无效。')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('远程 API 必须使用 HTTPS。')
        if '://' in self.path or not self.path.startswith('/'):
            raise ValueError('API path 必须是相对路径，以 / 开始。')

@dataclass
class Settings:
    data_dir: Path = ROOT / 'data'
    text: Endpoint = field(default_factory=lambda: Endpoint(path='/chat/completions'))
    embedding: Endpoint = field(default_factory=lambda: Endpoint(path='/embeddings'))
    rerank: Endpoint = field(default_factory=lambda: Endpoint(path='/rerank'))
    speech: Endpoint = field(default_factory=lambda: Endpoint(path='/audio/speech'))
    image: Endpoint = field(default_factory=lambda: Endpoint(path='/images/generations'))
    voice: str = 'alloy'
    timeout: float = 120
    text_json_mode: bool = False
    top_k: int = 5
    retrieval_strategy: str = 'dense_v1'
    retrieval_candidate_k: int = 20
    retrieval_rrf_k: int = 60
    retrieval_mmr_lambda: float = 0.7
    retrieval_metadata_weight: float = 0.0
    retrieval_document_encoding: str = 'raw_text_v1'
    retrieval_query_encoding: str = 'raw_topic_v1'
    retrieval_context_tokens: int = 0
    retrieval_expansion: str = 'none'
    rag_tokenizer_path: Path = ROOT / '.rag-models/embedding-tokenizer/tokenizer.json'
    chunk_strategy: str = 'recursive_v1'
    chunk_max_tokens: int = 256
    chunk_max_chars: int = 1200
    chunk_overlap_chars: int = 120
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pages: int = 300
    max_chunks: int = 400
    max_daily_calls: int = 100
    workers: int = 2

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env', override=False)
        def ep(prefix, path):
            extra = json.loads(os.getenv(prefix + '_EXTRA_JSON', '{}'))
            if not isinstance(extra, dict): raise ValueError(prefix + '_EXTRA_JSON must be an object')
            base=os.getenv(prefix+'_BASE_URL', '').rstrip('/')
            key=os.getenv(prefix+'_API_KEY', '')
            if prefix=='RERANK' and not key and os.getenv('RERANK_USE_EMBEDDING_KEY','false').lower()=='true':
                if base!=os.getenv('EMBEDDING_BASE_URL','').rstrip('/'):
                    raise ValueError('复用嵌入密钥的重排接口必须使用相同网关地址。')
                key=os.getenv('EMBEDDING_API_KEY','')
            return Endpoint(base, key, os.getenv(prefix+'_MODEL', ''),
                            os.getenv(prefix+'_PATH', path), extra)
        return cls(data_dir=Path(os.getenv('DATA_DIR', str(ROOT/'data'))).resolve(),
                   text=ep('TEXT', '/chat/completions'), embedding=ep('EMBEDDING', '/embeddings'),
                   rerank=ep('RERANK', '/rerank'),
                   speech=ep('SPEECH', '/audio/speech'), image=ep('IMAGE', '/images/generations'),
                   voice=os.getenv('SPEECH_VOICE', 'alloy'),
                   text_json_mode=os.getenv('TEXT_JSON_MODE', 'false').lower() in ('true', '1', 'yes'),
                   top_k=int(os.getenv('RETRIEVAL_TOP_K', '5')),
                   retrieval_strategy=os.getenv('RETRIEVAL_STRATEGY', 'dense_v1'),
                   retrieval_candidate_k=int(os.getenv('RETRIEVAL_CANDIDATE_K', '20')),
                   retrieval_rrf_k=int(os.getenv('RETRIEVAL_RRF_K', '60')),
                   retrieval_mmr_lambda=float(os.getenv('RETRIEVAL_MMR_LAMBDA', '0.7')),
                   retrieval_metadata_weight=float(os.getenv('RETRIEVAL_METADATA_WEIGHT', '0')),
                   retrieval_document_encoding=os.getenv('RETRIEVAL_DOCUMENT_ENCODING', 'raw_text_v1'),
                   retrieval_query_encoding=os.getenv('RETRIEVAL_QUERY_ENCODING', 'raw_topic_v1'),
                   retrieval_context_tokens=int(os.getenv('RETRIEVAL_CONTEXT_TOKENS', '0')),
                   retrieval_expansion=os.getenv('RETRIEVAL_EXPANSION', 'none'),
                   rag_tokenizer_path=Path(os.getenv('RAG_TOKENIZER_PATH', str(ROOT/'.rag-models/embedding-tokenizer/tokenizer.json'))),
                   chunk_strategy=os.getenv('CHUNK_STRATEGY', 'recursive_v1'),
                   chunk_max_tokens=int(os.getenv('CHUNK_MAX_TOKENS', '256')),
                   chunk_max_chars=int(os.getenv('CHUNK_MAX_CHARS', '1200')),
                   chunk_overlap_chars=int(os.getenv('CHUNK_OVERLAP_CHARS', '120')),
                   max_daily_calls=max(1, int(os.getenv('MAX_DAILY_API_CALLS', '100'))))

# Vector 인제스트

## 1) `ingest_pipeline.py` — 로컬 BGE-M3 → Chroma `itsm_bge_m3_chunks`

- OpenAI API 불필요 (HuggingFace `BAAI/bge-m3`).
- `app.api.routes.chat` 의 `get_rag_pipeline()` (bootstrap) 과 **동일 스택**에 맞춤.

```powershell
cd backend
$env:PYTHONPATH="."
python -m app.rag.vector.ingest_pipeline
```

- 저장 경로: `backend/chroma` (`rag_pipeline.VDB_PATH` 와 동일 디렉터리).

## 2) `ingest_openai_pipeline.py` — OpenAIEmbeddings → Chroma `RAG_COLLECTION_NAME`

- `app.rag.rag_pipeline` / LangGraph Agent 가 사용.
- `.env` 의 `OPENAI_EMBEDDING_MODEL` 이 **실제 엔드포인트에 존재하는 모델**이어야 함.  
  공개 OpenAI API에는 `bge-m3` 이름이 없음 → 예: `text-embedding-3-small` 등.

```powershell
$env:OPENAI_EMBEDDING_MODEL="text-embedding-3-small"
$env:RAG_COLLECTION_NAME="itsm_openai_te3"
python -m app.rag.vector.ingest_openai_pipeline
```

인제스트 후 `app.rag.rag_pipeline.clear_rag_cache()` 호출 또는 프로세스 재시작.

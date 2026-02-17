# REQ-002 — Domain Analysis

## RESEARCH SOURCES
- DeepWiki: `vllm-project/vllm` (OpenAI-compatible serving endpoints + runtime considerations)
- DeepWiki: `fastapi/fastapi` (DI, settings/env, timeout/retry, typed errors)
- DeepWiki: `coleam00/Archon` (extension points for provider + embeddings + settings UI)
- DeepWiki: `google/adk-python` (provider abstraction patterns over OpenAI-compatible backends)
- DeepWiki: `idosal/mcp-ui` (typed provider configuration + secure UI/backend separation)
- Code inspection (repo local):
  - `python/src/server/services/llm_provider_service.py`
  - `python/src/server/services/embeddings/embedding_service.py`
  - `python/src/server/services/credential_service.py`
  - `archon-ui-main/src/components/settings/RAGSettings.tsx`

---

## CURRENT STATE ANALYSIS

### Provider Architecture (Backend)
- `llm_provider_service.py` centraliza creación de clientes OpenAI-compatible (`get_llm_client`).
- Providers válidos hoy: `openai`, `ollama`, `google`, `openrouter`, `anthropic`, `grok`.
- `credential_service.get_active_provider()` resuelve provider/model/base_url desde `archon_settings` (`rag_strategy`).
- Embeddings usan `embedding_service.py` con adapter OpenAI-compatible por defecto + adapter nativo Google.

### Provider Architecture (Frontend)
- `RAGSettings.tsx` controla selección independiente chat/embeddings.
- `ProviderKey` y `EMBEDDING_CAPABLE_PROVIDERS` no incluyen `vllm`.
- Defaults de modelos y estado local por provider están hardcoded por enum.

### Gap Exacto
- No existe provider lógico `vllm` end-to-end (backend validation + credential mapping + UI selection + defaults).
- Aunque vLLM habla OpenAI API, falta cableado explícito para configuración estable y UX clara.

---

## DESIGN DECISION

### Decision: Add `vllm` as first-class OpenAI-compatible provider
- Reutilizar `openai.AsyncOpenAI` con `base_url` configurable.
- Extender validaciones y routing de provider, sin reescribir pipeline de embeddings/chat.
- Mantener KISS: mínima superficie de cambio en puntos ya diseñados para multi-provider.

### Why this over alternatives
- Evita branches ad-hoc en múltiples servicios.
- Encaja con patrón existente de provider config desde DB (`archon_settings`).
- Preserva backward compatibility con providers actuales.

---

## IMPLEMENTATION SURFACE (EXPECTED)

### Backend
1. `llm_provider_service.py`
   - Añadir `vllm` en validación `_is_valid_provider`.
   - Soporte en `get_llm_client` para construir `AsyncOpenAI(api_key=..., base_url=vllm_url)`.
   - Defaults seguros para URL y API key (key opcional según despliegue vLLM).

2. `credential_service.py`
   - Incluir `vllm` en provider resolution y `embedding_capable_providers`.
   - Añadir mapeo para key/base_url vLLM (e.g. `VLLM_API_KEY`, `VLLM_BASE_URL` o settings equivalentes).

3. `embedding_service.py` + helpers en `llm_provider_service.py`
   - Permitir defaults de embedding model compatibles con vLLM.
   - Validación de modelo compatible para provider `vllm` usando política OpenAI-compatible.

### Frontend
4. `RAGSettings.tsx`
   - Extender `ProviderKey` con `vllm`.
   - Añadir `vllm` a providers de embeddings.
   - Definir defaults de `chatModel` / `embeddingModel` para `vllm`.
   - Exponer campos/config para URL custom del backend.

### Config/Docs
5. `.env.example` + docs arquitectura
   - Variables y quickstart vLLM.
   - Notas de timeout/concurrency recomendadas para operación estable.

---

## RISK MAP

| Risk | Severity | Mitigation |
|------|----------|------------|
| provider enum inconsistente BE/FE | HIGH | contrato único + tests de smoke por provider |
| URL malformada (`/v1` duplicado/faltante) | MEDIUM | normalización centralizada base_url |
| embeddings con modelo no compatible | MEDIUM | validación provider-model + fallback explícito |
| degradación por timeout/concurrencia | MEDIUM | timeout configurable + mensajes de error tipados |

---

## CONCLUSIONS
1. El repo ya tiene arquitectura multi-provider adecuada; `vllm` es extensión natural.
2. El menor riesgo es modelar vLLM como provider OpenAI-compatible first-class.
3. Cambios deben concentrarse en provider routing, settings y validaciones; no en lógica de negocio RAG.
4. Requisito puede implementarse en bloques atómicos (QUANT) con impacto controlado.

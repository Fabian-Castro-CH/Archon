# REQ-002 — QUANT Breakdown

## SUMMARY
**Total**: 6 QUANTs | **AI est.**: ~14h | **Human review**: ~3.5h
**Critical path**: Q-001 → Q-002 → Q-003 → Q-004 → Q-005 (Q-006 paralelo al final)

---

## DEPENDENCY DAG

```text
Q-001 (Provider Contract)
  └── Q-002 (LLM Provider Routing)
        └── Q-003 (Embedding Compatibility)
              └── Q-004 (Settings UI Integration)
                    └── Q-005 (Docs + Env + Architecture)
Q-006 (Verification Matrix) depends on Q-002 + Q-003 + Q-004
```

---

## QUANT-001: Provider Contract Extension (`vllm`)
**~2h AI | ~0.5h Human**

### Description
Extender contratos/tipos de provider para soportar `vllm` en backend y frontend sin cambiar comportamiento existente.

### Acceptance
- [ ] `vllm` agregado en validación backend de providers.
- [ ] `vllm` agregado en tipos de UI provider (`ProviderKey`).
- [ ] No rompe compilación/lint/tests existentes.

### Files (expected)
- `python/src/server/services/llm_provider_service.py`
- `python/src/server/services/credential_service.py`
- `archon-ui-main/src/components/settings/RAGSettings.tsx`

### Dependencies
- none

---

## QUANT-002: LLM Client Routing for vLLM
**~3h AI | ~0.75h Human**

### Description
Implementar rama `vllm` en `get_llm_client()` usando cliente OpenAI-compatible con `base_url` configurable y política de auth coherente.

### Acceptance
- [ ] `provider=vllm` crea `openai.AsyncOpenAI` funcional.
- [ ] `base_url` normalizado (`/v1`) y validado.
- [ ] Timeout/error transport produce excepción con contexto.
- [ ] Existing providers mantienen comportamiento previo.

### Files (expected)
- `python/src/server/services/llm_provider_service.py`
- `python/src/server/services/credential_service.py`

### Dependencies
- Q-001

---

## QUANT-003: Embedding Flow Compatibility (vLLM)
**~2h AI | ~0.5h Human**

### Description
Asegurar que embeddings usen provider `vllm` con defaults/validaciones de modelo compatibles OpenAI endpoint shape.

### Acceptance
- [ ] `EMBEDDING_PROVIDER=vllm` válido en resolución activa.
- [ ] `get_embedding_model()` retorna default estable para `vllm`.
- [ ] `create_embeddings_batch()` funciona con `provider=vllm` sin cambios de contrato.

### Files (expected)
- `python/src/server/services/credential_service.py`
- `python/src/server/services/llm_provider_service.py`
- `python/src/server/services/embeddings/embedding_service.py`

### Dependencies
- Q-002

---

## QUANT-004: Settings UI Integration (Provider + Models + URL)
**~3h AI | ~1h Human**

### Description
Integrar `vllm` en `RAGSettings` para selección chat/embedding, defaults de modelos y configuración de endpoint custom.

### Acceptance
- [ ] `vllm` visible como provider en UI.
- [ ] Soporte embedding provider separado con `vllm`.
- [ ] Persistencia de modelo/URL por provider sin regressions.

### Files (expected)
- `archon-ui-main/src/components/settings/RAGSettings.tsx`
- `archon-ui-main/src/services/credentialsService.ts` (si requiere nuevos keys)

### Dependencies
- Q-001, Q-003

---

## QUANT-005: Documentation + Environment
**~2h AI | ~0.5h Human**

### Description
Actualizar `.env.example`, arquitectura y guía de setup para vLLM backend custom.

### Acceptance
- [ ] Variables vLLM documentadas (`VLLM_BASE_URL`, `VLLM_API_KEY` o equivalente definido).
- [ ] Flujo rápido de configuración y ejemplo mínimo en docs.
- [ ] Claridad sobre fallback/compatibilidad con providers existentes.

### Files (expected)
- `.env.example`
- `PRPs/ai_docs/ARCHITECTURE.md`
- `README.md` (sección configuración provider)

### Dependencies
- Q-002, Q-004

---

## QUANT-006: Verification Matrix (E2E Provider)
**~2h AI | ~0.25h Human**

### Description
Definir y ejecutar matriz mínima de verificación para provider `vllm` en chat + embeddings + settings persistence.

### Acceptance
- [ ] Caso feliz chat completions.
- [ ] Caso feliz embeddings batch.
- [ ] Caso de error por timeout/URL inválida con mensaje tipado.
- [ ] Caso de fallback/backward compatibility (openai/ollama) intacto.

### Files (expected)
- `python/tests/` (tests provider/embedding)
- `archon-ui-main/tests/` (si aplica smoke settings)
- Documento corto de resultados (en PR o notes)

### Dependencies
- Q-002, Q-003, Q-004

---

## ESTIMATES SUMMARY

| QUANT | Title | AI est. | Human est. | Depends on |
|---|---|---:|---:|---|
| Q-001 | Provider Contract Extension | 2h | 0.5h | — |
| Q-002 | LLM Routing vLLM | 3h | 0.75h | Q-001 |
| Q-003 | Embedding Compatibility | 2h | 0.5h | Q-002 |
| Q-004 | Settings UI Integration | 3h | 1h | Q-001, Q-003 |
| Q-005 | Docs + Env | 2h | 0.5h | Q-002, Q-004 |
| Q-006 | Verification Matrix | 2h | 0.25h | Q-002, Q-003, Q-004 |
| **TOTAL** |  | **14h** | **3.5h** |  |

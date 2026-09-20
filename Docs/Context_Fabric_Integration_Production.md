# Context Fabric Integration — Production Design Spec

**Status:** Implementation spec
**Date:** 20 September 2026
**Audience:** Backend engineers, integration engineers, security review
**Scope:** How a client-side agent (Context Fabric) feeds the ING FM Deal Intelligence Digital Twin in production

---

## Overview

Let me break down how to connect a production client-side agent like **Context Fabric** to the backend without over-engineering the architecture.

In production, client tools installed on RM (Relationship Manager) or DCM specialist workstations act as **edge collectors**. They observe local work activity (emails, meeting transcripts, deal memos) and summarize operational intent locally.

The integration is straightforward and enterprise-standard: a single secure webhook endpoint that the Context Fabric desktop agent calls whenever it synthesizes a new signal. The receiver maps the external payload to the platform's canonical IDs and hands off to the existing ingestion pipeline.

---

## 1. The Logical Production Architecture

```
┌────────────────────────────────────────────────────────┐
│  RM Workstation (Client Side)                          │
│  Context Fabric Desktop Agent                          │
│  • Captures tacit notes / Outlook / Teams              │
│  • Summarizes deal intent locally                      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           │ HTTPS POST (Signed Webhook + Bearer Token)
                           ▼
┌────────────────────────────────────────────────────────┐
│  ING Digital Twin Ingestion Endpoint                   │
│  POST /api/webhooks/context-fabric                     │
│  • Validates API key / HMAC signature                  │
│  • Maps external client ID → canonical CLI ID          │
│  • Delegates to ingest_text_signal()                   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Gemini (gemini-2.5-flash) Extraction Engine           │
│  • Extracts signals from raw_text                      │
│  • Two-layer dedup (signal-level + chunk-level)        │
│  • Writes ca.digital_twin_signals                      │
│  • Writes ca.document_vector_chunks                    │
│  • Invalidates synthesis cache for the client          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Next /api/opportunities call (cache miss)             │
│  • Re-runs mandate synthesis                           │
│  • Recomputes priority_score with weighted rubric      │
│  • Writes back to ca.ca_opportunity_scoring            │
│  • UI (via /api/signals polling) reflects new signal   │
└────────────────────────────────────────────────────────┘
```

**Note on "real time":** ingestion lands in the DB immediately, but the UI reflects the change on the next synthesis cache miss (up to 300 seconds) unless the webhook explicitly invalidates the cache. The receiver does invalidate — see §4.

---

## 2. Context Fabric Webhook Payload Format

Context Fabric exports structured event payloads over standard HTTPS. Configure Context Fabric's outbound webhook setting to deliver this JSON:

```json
{
  "event_id": "evt_9823410a",
  "timestamp": "2026-09-20T10:15:30Z",
  "source_agent": {
    "user_id": "rm_klaus_weber",
    "user_name": "Klaus Weber",
    "desk": "DCM Origination Germany",
    "application_source": "WorkFabric Desktop v2.4"
  },
  "entity": {
    "external_client_id": "BASF_SE",
    "lei": "52990021RFURJ1U72T14"
  },
  "context_memo": {
    "product_family": "INTEREST_RATE_HEDGING",
    "raw_text": "Executive Committee approved accelerated debt rollover. Mandate requires EUR 2.0B 6Y Senior EMTN benchmark with immediate EUR 1.2B Fixed-to-Floating IRS pre-hedge.",
    "priority": "HIGH",
    "confidence_score": 0.95
  }
}
```

**Field notes:**

- `entity.external_client_id` — the client identifier from the external system. **Not** a canonical `CLI###` ID. The receiver maps this to the canonical form.
- `entity.lei` — Legal Entity Identifier. Stable external identifier, useful for future reconciliation. Not required for the initial implementation but should be carried in the payload.
- `context_memo.product_family` — a free-text product family hint. Currently unused by the receiver; the ingestion pipeline classifies the family from the extracted signals.

---

## 3. Canonical Client ID Mapping

The platform uses **canonical client IDs** `CLI001` … `CLI105` across all tables (per persona §7.4). External systems will not speak this format. The webhook receiver must map external identifiers to canonical IDs before calling the ingestion service.

**Mapping implementation:**

```python
# External → canonical ID mapping. Extend as new client integrations onboard.
# In production this should be sourced from a table (ca.client_id_aliases);
# for the demo a module-level dict is sufficient.
_EXTERNAL_CLIENT_ID_MAP = {
    # External format used by Context Fabric
    "BASF_SE":     "CLI103",
    "ENEL_SPA":    "CLI101",
    "ENEL":        "CLI101",
    # LEI fallback
    "52990021RFURJ1U72T14": "CLI103",
}

def _resolve_canonical_client_id(external_id: str, lei: str = None) -> str:
    """
    Resolve an external client identifier to the platform's canonical CLI### form.
    Raises ValueError if the identifier is not recognized.
    """
    if not external_id:
        raise ValueError("Missing external_client_id")
    # Try the primary identifier first
    canonical = _EXTERNAL_CLIENT_ID_MAP.get(str(external_id).strip().upper())
    if canonical:
        return canonical
    # Fall back to LEI
    if lei:
        canonical = _EXTERNAL_CLIENT_ID_MAP.get(str(lei).strip())
        if canonical:
            return canonical
    raise ValueError(f"Unrecognized client identifier: {external_id!r} / LEI {lei!r}")
```

**Backlog:** replace `_EXTERNAL_CLIENT_ID_MAP` with a `ca.client_id_aliases` table once DDL is unlocked (persona §7.2). This would allow onboarding new clients without a code change.

---

## 4. Backend Webhook Receiver Endpoint (`main.py`)

A single dedicated endpoint on the FastAPI service.

### 4.1 Security — MUST-FIX before production

**No hardcoded fallback secret.** The endpoint must fail closed if the expected token is not configured.

**Recommended pattern:**

```python
import os
import hmac
from fastapi import Header, HTTPException
from pydantic import BaseModel

class ContextFabricWebhookPayload(BaseModel):
    event_id: str
    timestamp: str
    source_agent: dict
    entity: dict
    context_memo: dict


@app.post("/api/webhooks/context-fabric")
async def receive_context_fabric_feed(
    payload: ContextFabricWebhookPayload,
    authorization: str = Header(None),
):
    # ---------------------------------------------------------------
    # SECURITY: fail closed. No default secret. No fallback.
    # The expected token is sourced from Secret Manager (see §6).
    # ---------------------------------------------------------------
    expected_token = os.getenv("CONTEXT_FABRIC_API_KEY")
    if not expected_token:
        # Configuration error — the service cannot authenticate any caller.
        raise HTTPException(status_code=503, detail="Webhook auth not configured")

    if not authorization or not hmac.compare_digest(
        authorization, f"Bearer {expected_token}"
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # ---------------------------------------------------------------
    # Resolve the external client identifier to a canonical CLI### ID.
    # ---------------------------------------------------------------
    external_id = payload.entity.get("external_client_id")
    lei = payload.entity.get("lei")
    try:
        cid = _resolve_canonical_client_id(external_id, lei)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    raw_text = payload.context_memo.get("raw_text", "").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="Empty raw_text")

    author = (
        f"{payload.source_agent.get('user_name', 'RM')} "
        f"({payload.source_agent.get('desk', 'Coverage')})"
    )

    # ---------------------------------------------------------------
    # Delegate to the existing ingestion pipeline.
    # The pipeline handles: multi-signal extraction, two-layer dedup,
    # vector persistence, and signal persistence.
    # ---------------------------------------------------------------
    req = TextIngestRequest(
        client_id=cid,
        source_channel="WORKFABRIC_MEMO",
        source_name=author,
        text_content=raw_text,
    )
    result = ingest_text_signal(req)

    # ---------------------------------------------------------------
    # Propagate the real ingestion status. The dedup guard may have
    # skipped the write if a matching signal already exists.
    # ---------------------------------------------------------------
    actual_status = result.get("status", "UNKNOWN")

    # ---------------------------------------------------------------
    # Invalidate the synthesis cache for this client so the next
    # /api/opportunities call recomputes with the new signal, rather
    # than waiting up to 300s for TTL expiry.
    # ---------------------------------------------------------------
    if actual_status == "INGESTED_AND_EVALUATED":
        _MANDATE_SYNTH_CACHE.pop(cid, None)

    return {
        "status": actual_status,
        "event_id": payload.event_id,
        "client_id": cid,
        "digital_twin_recalculated": actual_status == "INGESTED_AND_EVALUATED",
    }
```

### 4.2 Why `WORKFABRIC_MEMO`, not `CONTEXT_FABRIC`

Per persona §3.2, the canonical `source_channel` values are:
`PDF_REPORT`, `NEWS_RSS`, `CLIENT_EMAIL`, `TEAMS_CHAT`, `WORKFABRIC_MEMO`.

`CONTEXT_FABRIC` is a legacy alias that exists in historical data. **The webhook must send the canonical value `WORKFABRIC_MEMO`**, so the read paths don't need to know about a new channel era.

### 4.3 Why the client ID mapping is required

If the receiver passed `"BASF_SE"` directly to `ingest_text_signal`, the signal would be written with `client_id = 'BASF_SE'` — a value no downstream query reads. All read paths filter by canonical `CLI###` IDs. The mapping step is not optional.

### 4.4 Why the cache is invalidated explicitly

The synthesis cache has a 300-second TTL. Without explicit invalidation, a signal ingested by webhook takes up to 5 minutes to reflect in the opportunity card and pitchbook preview. The `_MANDATE_SYNTH_CACHE.pop(cid, None)` call makes the next `/api/opportunities` request a cache miss, forcing fresh synthesis. That's what makes the "near-real-time" claim accurate.

**Note:** this depends on single-instance deployment (`max-instances=1`) so the in-memory cache is shared. See persona §5.5.

---

## 5. Authentication and Payload Signing

Two layers of authentication are recommended for production:

### 5.1 Bearer token (minimum)

A shared secret distributed to the Context Fabric deployment, passed as `Authorization: Bearer <token>`. The endpoint validates with `hmac.compare_digest` for constant-time comparison (prevents timing attacks).

### 5.2 HMAC request signature (recommended)

For higher assurance, Context Fabric signs the request body with a shared HMAC key:

```
X-Context-Fabric-Signature: sha256=<hex>
X-Context-Fabric-Timestamp: 1758369330
```

The receiver recomputes the HMAC over the canonical JSON body and compares. Reject requests with timestamps older than ~5 minutes to prevent replay.

**Not implemented in this doc.** HMAC signing is a recommended next layer once the basic bearer-token integration is validated. Recorded here so the design accounts for it.

---

## 6. Secret Management

The `CONTEXT_FABRIC_API_KEY` must be provisioned through Google Secret Manager, not set as a plain environment variable in the Cloud Run service config.

**Provisioning:**

```bash
echo -n "ing_live_<generated>" | gcloud secrets create context-fabric-api-key \
  --data-file=- \
  --project=dulcet-radar-508218-c5
```

**Mounting on Cloud Run:**

```bash
gcloud run services update ing-fm-poc-service \
  --region=europe-west1 \
  --project=dulcet-radar-508218-c5 \
  --update-secrets=CONTEXT_FABRIC_API_KEY=context-fabric-api-key:latest
```

This mirrors the pattern already used for `db-postgres-pass` (`DB_PASS` env var).

---

## 7. Frontend Sync

### 7.1 Current mechanism — polling

The frontend currently polls `/api/signals` on an interval and re-renders the Live Signal Marquee, Segment 3 (Context Fabric), and Segment 4 (Mandate) when new signals are present.

**There is no SSE endpoint today.** The design below describes how it would work if added; the current implementation uses polling.

### 7.2 SSE — future enhancement

If sub-second updates are required, a Server-Sent Events endpoint could be added at `/api/signals/stream`:

- The endpoint holds the connection open.
- On cache invalidation for a client, it pushes the refreshed signal set.
- The frontend replaces polling with an `EventSource` subscription.

Not in scope for the initial Context Fabric integration. Polling is sufficient for the demo and near-term production.

### 7.3 No per-client endpoint today

The current endpoint is `/api/signals` (unfiltered, though read paths narrow to `_DEMO_CLIENT_IDS`). There is no `/api/signals/{client_id}`. Client-side filtering is done in the browser.

---

## 8. Summary for Leadership

1. **Zero client disruption.** RMs do not manually copy-paste into the web portal. Context Fabric pushes synthesized memos automatically via background HTTPS webhooks.

2. **Standard API gateway.** A single secure endpoint (`POST /api/webhooks/context-fabric`) secured with a bearer token (and optionally HMAC), provisioned via Secret Manager.

3. **Reuses existing logic.** The webhook maps the external client ID to the canonical `CLI###` form, then calls the existing `ingest_text_signal` pipeline — extracting signals with Gemini, persisting vectors to Cloud SQL, and updating the Digital Twin.

4. **Near-real-time, not immediate.** The signal lands in the DB in ~1 second. The UI reflects it on the next `/api/opportunities` call. The webhook explicitly invalidates the synthesis cache so this happens on the next request rather than waiting up to 5 minutes for TTL expiry.

5. **Auditable.** Every signal traces to a row in `ca.digital_twin_signals`; every score traces to a row in `ca.ca_opportunity_scoring`. The webhook does not bypass any invariant.

---

## 9. Implementation Checklist

Before the endpoint is considered production-ready:

- [ ] **`CONTEXT_FABRIC_API_KEY` provisioned via Secret Manager** and mounted on Cloud Run. **No hardcoded fallback in code.**
- [ ] **Endpoint fails closed** if the secret is not configured (HTTP 503, not 401-with-default).
- [ ] **`hmac.compare_digest` used** for token comparison (constant-time).
- [ ] **Canonical ID mapping** implemented and tested for at least Enel and BASF identifiers.
- [ ] **`source_channel="WORKFABRIC_MEMO"`** (canonical), not `"CONTEXT_FABRIC"` (legacy).
- [ ] **Webhook response propagates** the `ingest_text_signal` status, not a hardcoded `PROCESSED`.
- [ ] **Cache invalidation** happens on successful ingestion (not on dedup-skipped).
- [ ] **Payload validation** rejects empty `raw_text` and unknown clients with HTTP 422.
- [ ] **Rate limiting** at the Cloud Run / API gateway layer (not in this spec; separate infrastructure concern).
- [ ] **Logging** captures `event_id`, canonical `client_id`, and ingestion status for audit.

---

## 10. Backlog — Post-Integration

1. **Move the ID mapping to a DB table.** `ca.client_id_aliases` with `(external_system, external_id, canonical_id)`. Blocked by §7.2 (no DDL).

2. **Add HMAC request signing** (§5.2) once the bearer-token flow is validated.

3. **Add rate limiting** on the webhook endpoint to prevent abuse from a compromised client deployment.

4. **Add a dead-letter queue** for webhooks that fail ingestion, so events aren't lost.

5. **SSE endpoint** if polling latency becomes a concern (§7.2).

---

## 11. Changelog — 20 Sep 2026

Corrections to the draft spec in light of the current codebase and the 19-20 Sep session:

- **§4.1** — flagged the hardcoded fallback secret (`"ing_live_secret_key"`) as a MUST-FIX. New code fails closed if the secret is not configured.
- **§3** — added explicit external → canonical client ID mapping. Prior draft passed `"BASF_SE"` directly to the ingestion pipeline, which would write signals no read path retrieves.
- **Endpoint path** — changed from `/api/v1/webhooks/context-fabric` to `/api/webhooks/context-fabric`. The `/api/v1/` prefix is not used elsewhere in the platform.
- **§4.2** — changed `source_channel` from `"CONTEXT_FABRIC"` (legacy alias) to `"WORKFABRIC_MEMO"` (canonical value).
- **§4.1** — webhook response now propagates the actual `ingest_text_signal` status (may be `duplicate_skipped`), not a hardcoded `PROCESSED`.
- **§4.4** — added explicit synthesis cache invalidation so the UI reflects new signals on the next request, not after TTL expiry.
- **§6** — added Secret Manager provisioning section.
- **§7** — clarified that the current frontend polls; SSE is a future enhancement. Corrected the endpoint reference (there is no `/api/signals/{client_id}` today).
- **§1 diagram** — replaced stale "Gemini Pro" with `gemini-2.5-flash`. Corrected the re-rank description to reflect the cache-miss-then-synthesis path rather than a direct trigger.
- **§5.2** — HMAC signing noted as recommended next layer, not implemented in this pass.
- **§9** — added implementation checklist.
- **§10** — backlog section added.

The overall architectural direction (webhook → existing ingestion pipeline → Digital Twin update) is unchanged.

---

*End of document.*
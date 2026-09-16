# Warranty Claim Intelligence POC

Phase-1 deterministic advisory solution for warranty and service claim intelligence using SAP HANA Cloud data, FastAPI backend, SAP AI Hub LLM integration scaffold, and a lightweight HTML/CSS/JavaScript frontend.

## What this solution does

- Reads warranty claim data from SAP HANA Cloud
- Exposes API endpoints for:
  - products
  - suppliers
  - raw claims
  - recurring failure-pattern aggregation
  - single-claim intelligence with deterministic classification
- Calculates:
  - repeat failure counts
  - batch concentration signals
  - deterministic severity score
  - advisory recommendations
- Optionally calls an SAP AI Hub compatible LLM endpoint to generate explanations
- Serves a simple browser dashboard

## Project structure

- `app/main.py` - FastAPI app and deterministic intelligence endpoints
- `app/database.py` - SAP HANA Cloud connection and query execution
- `app/chat.py` - SAP AI Hub compatible LLM explanation integration
- `app/static/index.html` - frontend UI
- `app/static/styles.css` - frontend styles
- `app/static/script.js` - frontend logic

## Required environment variables

For SAP HANA Cloud:
- `HANA_HOST`
- `HANA_PORT`
- `HANA_USER`
- `HANA_PASSWORD`

For SAP AI Hub / AI Core compatible LLM endpoint:
- `GENAI_ENABLED=true`
- `GENAI_AUTH_URL`
- `GENAI_CLIENT_ID`
- `GENAI_CLIENT_SECRET`
- `GENAI_DEPLOYMENT_URL`

Optional:
- `GENAI_RESOURCE_GROUP`
- `GENAI_MODEL`
- `GENAI_VERIFY_SSL`
- `GENAI_TIMEOUT_SECONDS`

## Install

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python -m uvicorn app.main:app --reload
```

Open:
- `http://127.0.0.1:8000/`

## API endpoints

### Health / UI
- `GET /` - dashboard

### Base data
- `GET /api/products`
- `GET /api/suppliers`
- `GET /api/claims`

### Intelligence
- `GET /api/intelligence/patterns`
- `GET /api/intelligence/patterns?days=30`
- `GET /api/intelligence/claims/{claim_id}`

## Deterministic classification logic

### Repeat failure
A claim is tagged `REPEAT_FAILURE` when the same product/material and failure code appears 5 or more times.

### Concentration signal
A claim is tagged `CONCENTRATION_SIGNAL` when:
- same product/material + failure code repeat count is at least 3
- same batch concentration ratio is at least 0.35

### High severity
A claim is tagged `HIGH_SEVERITY` when:
- severity bucket becomes `HIGH`
- or cost is at least 1500

### Isolated
If none of the above apply, the claim is tagged `ISOLATED`.

## Compliance / advisory behavior

- The agent separates observed evidence from inferred causes
- Recommendations are advisory only
- No warranty approval is automated
- No financial posting is automated

## Notes for your HANA schema

Current implementation expects a `WARRANTY_CLAIMS` table and optionally:
- `PRODUCTS`
- `SUPPLIERS`

Supported claim field names in the logic include common variants such as:
- `claim_id` or `id`
- `product`, `material`, `product_id`, `material_id`
- `serial`, `serial_no`, `serial_number`
- `batch`, `batch_no`, `batch_number`
- `failure_code`, `failure`, `defect_code`
- `cost`, `cost_amount`, `amount`
- `severity`, `severity_code`, `priority`

If your actual column names differ, adjust the SQL and field mapping in `app/main.py`.

## Demo scenario coverage

This POC is designed to support:
1. repeated warranty claims with the same failure code for one product family
2. failure concentration linked to one serial/batch range
3. supplier/component correlation where traceability fields exist in data
4. prioritization of high-cost or high-severity claims
5. isolated claims staying low priority without false escalation

## Next recommended hardening

- align SQL exactly to your real HANA table names and columns
- add joins to quality, supplier traceability, service order and production context tables
- add a dedicated endpoint for top risky batches/suppliers/products
- improve the frontend with filters, cards and claim drill-down
- connect Joule Studio to the same evidence service for enterprise demo flow

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

This project uses rule-based logic in `app/main.py` to enrich warranty claims with explainable fields. The goal is to make every output easy to justify to business users, quality teams, and auditors.

### 1. Severity score

Severity score is calculated by the `_build_severity_score(cost_amount, severity_raw)` function.

Formula:

```text
severity_score = cost_component + severity_flag_component
final_score = min(100, severity_score)
```

#### Cost component
The cost part contributes up to **70 points**.

Formula:

```text
cost_component = min(70, (cost_amount / 1000) * 70)
```

Examples:
- cost = 0 -> 0 points
- cost = 250 -> 17.5 points
- cost = 500 -> 35 points
- cost = 1000 -> 70 points
- cost = 1500 -> still 70 points because cost contribution is capped

This means cost is the dominant driver of severity in Phase-1.

#### Severity flag / code component
The optional severity field contributes additional fixed points.

Accepted values are normalized to uppercase text before comparison.

Mapping:
- `CRITICAL`, `HIGH`, `S3` -> +30 points
- `MEDIUM`, `S2` -> +15 points
- `LOW`, `S1` -> +5 points
- anything else or missing -> +0 points

#### Final severity score examples

Example 1:
```text
cost = 500
severity = MEDIUM

cost_component = (500 / 1000) * 70 = 35
severity_flag_component = 15
final_score = 50
```

Example 2:
```text
cost = 2000
severity = HIGH

cost_component = min(70, (2000 / 1000) * 70) = 70
severity_flag_component = 30
final_score = 100
```

Example 3:
```text
cost = 300
severity = LOW

cost_component = 21
severity_flag_component = 5
final_score = 26
```

### 2. Severity bucket

Severity bucket is derived from the numeric severity score by `_severity_bucket(severity_score)`.

Rules:
- `HIGH` if severity score is **80 or above**
- `MEDIUM` if severity score is **50 or above** but below 80
- `LOW` if severity score is below 50

Examples:
- score 26 -> `LOW`
- score 50 -> `MEDIUM`
- score 79.9 -> `MEDIUM`
- score 80 -> `HIGH`

### 3. Repeat count

For each claim, the service checks how many claims have the same:
- product/material
- failure code

That count becomes `repeat_count`.

In `/api/claims`, this is calculated by scanning all returned claims and counting matches for the same product + failure combination.

In `/api/intelligence/claims/{claim_id}`, it is calculated with SQL:

```sql
SELECT COUNT(*) AS repeat_count
FROM WARRANTY_CLAIMS
WHERE COALESCE(product, material, product_id, material_id) = ?
  AND failure_code = ?
```

### 4. Product concentration

`product_concentration` shows how concentrated a failure pattern is within all claims for that product.

Formula:

```text
product_concentration = repeat_count / total_product_claims
```

Where:
- `repeat_count` = claims with same product + failure code
- `total_product_claims` = all claims for the same product, regardless of failure code

Example:
- Product P1 has 10 total claims
- 4 of them have failure code F1

Then:

```text
product_concentration = 4 / 10 = 0.40
```

Meaning: 40% of claims for that product are showing the same failure pattern.

### 5. Batch concentration

`batch_concentration` shows how much the repeated failure pattern is concentrated inside the same batch.

Formula:

```text
batch_concentration = batch_pattern_claims / repeat_count
```

Where:
- `batch_pattern_claims` = claims with same product + same failure code + same batch
- `repeat_count` = claims with same product + same failure code

Example:
- 5 claims exist for product P1 + failure F1
- 3 of those 5 are from batch B100

Then:

```text
batch_concentration = 3 / 5 = 0.60
```

Meaning: 60% of that failure pattern comes from one batch, which is a strong containment signal.

### 6. Supplier concentration

`supplier_concentration` shows how much a supplier is associated with a specific failure code relative to all claims for that supplier.

Formula:

```text
supplier_concentration = supplier_pattern_claims / total_supplier_claims
```

Where:
- `supplier_pattern_claims` = claims for same supplier + same failure code
- `total_supplier_claims` = all claims for the same supplier

Example:
- Supplier S1 has 20 total claims
- 12 of them have failure code F1

Then:

```text
supplier_concentration = 12 / 20 = 0.60
```

Meaning: 60% of that supplier's claims are associated with one failure code.

### 7. Which concentration ratio is used in classification

When `_classify_claim()` is called from `/api/claims`, the code passes:

```text
max(product_concentration, batch_concentration, supplier_concentration)
```

This means the classifier uses the strongest detected concentration signal among:
- product concentration
- batch concentration
- supplier concentration

So if:
- product concentration = 0.40
- batch concentration = 0.60
- supplier concentration = 0.25

Then the classifier receives:

```text
concentration_ratio = 0.60
```

### 8. Labels

Labels are business tags assigned by `_classify_claim()`.

#### `REPEAT_FAILURE`
Added when:

```text
repeat_count >= 5
```

Meaning: the same product + failure combination has happened at least five times.

#### `CONCENTRATION_SIGNAL`
Added when both conditions are true:

```text
concentration_ratio >= 0.35
repeat_count >= 3
```

Meaning: the failure is not only repeating, but also clustered strongly in product, batch, or supplier behavior.

#### `HIGH_SEVERITY`
Added when either condition is true:
- severity bucket is `HIGH`
- cost is at least `1500`

Meaning: the claim deserves faster attention due to financial impact or severity level.

#### `ISOLATED`
If no other labels are added, the claim gets:

```text
["ISOLATED"]
```

Meaning: no strong repeat, concentration, or severity signal exists in the current dataset.

### 9. Recommendations

Recommendations are deterministic text messages based on labels.

- `REPEAT_FAILURE` ->
  `Investigate recurring failure code for this product family and validate repair actions.`

- `CONCENTRATION_SIGNAL` ->
  `Check batch/serial range containment: review production window, inspection history and supplier lots.`

- `HIGH_SEVERITY` ->
  `Prioritize triage due to high cost/severity; validate customer impact and consider expedited root-cause review.`

- `ISOLATED` ->
  `Monitor only; no evidence of a wider pattern in current dataset.`

A claim can receive multiple recommendations if it has multiple labels.

### 10. Advisory only

`advisory_only` is always returned as `True`.

This is an important compliance and design decision.

It means:
- the system gives guidance only
- the output is a recommendation, not an automated business decision
- no claim is auto-approved
- no supplier is auto-blamed
- no financial posting or warranty settlement is triggered automatically

In short, the system helps humans investigate claims faster, but humans still make the final business decision.

### 11. LLM explanation behavior

For `/api/claims`, an LLM explanation is only attempted when:

```text
supplier_concentration >= 0.60
and supplier exists
```

If enabled, the LLM-generated explanation is appended to the deterministic recommendation.
If not enabled or unavailable, the deterministic recommendation is still returned.

For `/api/intelligence/claims/{claim_id}`, the deterministic classification is always returned first, and the LLM explanation is attached separately.

### 12. Simple end-to-end interpretation example

Assume one claim has:
- cost = 1200
- severity = `MEDIUM`
- repeat_count = 6
- total product claims = 10
- same batch pattern claims = 4
- total supplier claims = 20
- same supplier + failure claims = 8

Step 1: severity score

```text
cost_component = min(70, (1200 / 1000) * 70) = 70
severity_flag_component = 15
severity_score = 85
severity_bucket = HIGH
```

Step 2: concentrations

```text
product_concentration = 6 / 10 = 0.60
batch_concentration = 4 / 6 = 0.67
supplier_concentration = 8 / 20 = 0.40
concentration_ratio used by classifier = max(0.60, 0.67, 0.40) = 0.67
```

Step 3: labels

- `REPEAT_FAILURE` because repeat_count = 6
- `CONCENTRATION_SIGNAL` because concentration_ratio = 0.67 and repeat_count >= 3
- `HIGH_SEVERITY` because severity bucket = `HIGH`

Step 4: outcome

The claim is enriched with:
- high numeric severity
- `HIGH` bucket
- evidence of repeated failure
- evidence of concentration around a batch/product pattern
- advisory recommendations for triage and investigation

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

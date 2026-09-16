from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.database import execute_query
from app.chat import generate_warranty_explanation

app = FastAPI(title="Warranty Claims POC")

# Serve simple frontend (static HTML/CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/products")
def get_products():
    sql = """
    SELECT *
    FROM PRODUCTS
    """
    return execute_query(sql)


@app.get("/api/suppliers")
def get_suppliers():
    sql = """
    SELECT *
    FROM SUPPLIERS
    """
    return execute_query(sql)


@app.get("/api/claims")
def get_claims():
    """
    Existing UI consumes this endpoint.
    Return enriched claim rows with deterministic evidence and recommendations
    while preserving the current dashboard structure.
    """
    claims = execute_query("SELECT * FROM WARRANTY_CLAIMS")
    if not claims:
        return []

    enriched_claims: List[Dict[str, Any]] = []

    for claim in claims:
        product_key = claim.get("product") or claim.get("material") or claim.get("product_id") or claim.get("material_id")
        failure_code = claim.get("failure_code") or claim.get("failure") or claim.get("defect_code")
        supplier_key = claim.get("supplier") or claim.get("supplier_id")
        batch_key = claim.get("batch") or claim.get("batch_no") or claim.get("batch_number") or claim.get("batch_id")

        repeat_count = 1
        same_pattern_claim_ids: List[str] = []
        product_concentration = 0.0
        supplier_concentration = 0.0
        batch_concentration = 0.0

        same_pattern_claim_ids = []
        batch_claim_ids = []
        supplier_claim_ids = []

        for candidate in claims:
            candidate_claim_id = candidate.get("claim_id")
            candidate_product_key = candidate.get("product") or candidate.get("material") or candidate.get("product_id") or candidate.get("material_id")
            candidate_failure_code = candidate.get("failure_code") or candidate.get("failure") or candidate.get("defect_code")
            candidate_supplier_key = candidate.get("supplier") or candidate.get("supplier_id")
            candidate_batch_key = candidate.get("batch") or candidate.get("batch_no") or candidate.get("batch_number") or candidate.get("batch_id")

            if candidate_product_key == product_key:
                product_concentration += 1

            if candidate_product_key == product_key and candidate_failure_code == failure_code:
                if candidate_claim_id:
                    same_pattern_claim_ids.append(str(candidate_claim_id))

                if batch_key and candidate_batch_key == batch_key:
                    if candidate_claim_id:
                        batch_claim_ids.append(str(candidate_claim_id))

            if candidate_supplier_key == supplier_key:
                supplier_concentration += 1

            if candidate_supplier_key == supplier_key and candidate_failure_code == failure_code:
                if candidate_claim_id:
                    supplier_claim_ids.append(str(candidate_claim_id))

        repeat_count = len(same_pattern_claim_ids) if same_pattern_claim_ids else 1
        total_product_claims = sum(
            1
            for candidate in claims
            if (candidate.get("product") or candidate.get("material") or candidate.get("product_id") or candidate.get("material_id")) == product_key
        )
        total_supplier_claims = sum(
            1
            for candidate in claims
            if (candidate.get("supplier") or candidate.get("supplier_id")) == supplier_key
        )

        product_concentration = (repeat_count / total_product_claims) if total_product_claims else 0.0
        batch_concentration = (len(batch_claim_ids) / repeat_count) if repeat_count else 0.0
        supplier_concentration = (len(supplier_claim_ids) / total_supplier_claims) if total_supplier_claims else 0.0

        classified = _classify_claim(
            claim=claim,
            repeat_count=repeat_count,
            concentration_ratio=max(product_concentration, batch_concentration, supplier_concentration),
        )

        if supplier_concentration >= 0.60 and supplier_key:
            llm_result = generate_warranty_explanation(classified)
            if llm_result["enabled"]:
                recommendation_text = f"{llm_result['explanation']} | Explanation: {classified['observed_evidence']}"
            else:
                recommendation_text = (
                    f" | ".join(classified["recommendations"])
                    + f" | LLM unavailable: {llm_result['explanation']}"
                )
        else:
            recommendation_text = " | ".join(classified["recommendations"])

        enriched_claims.append(
            {
                **claim,
                "product": claim.get("product") or claim.get("product_id") or claim.get("material"),
                "material": claim.get("material") or claim.get("material_id") or claim.get("product_id"),
                "supplier": claim.get("supplier") or claim.get("supplier_id"),
                "serial": claim.get("serial") or claim.get("serial_no") or claim.get("serial_number"),
                "batch": claim.get("batch") or claim.get("batch_no") or claim.get("batch_number") or claim.get("batch_id"),
                "severity_bucket": classified["severity_bucket"],
                "severity_score": classified["severity_score"],
                "repeat_count": repeat_count,
                "product_concentration": round(product_concentration, 2),
                "batch_concentration": round(batch_concentration, 2),
                "supplier_concentration": round(supplier_concentration, 2),
                "evidence_claim_ids": same_pattern_claim_ids,
                "recommendations": [recommendation_text],
                "labels": classified["labels"],
                "advisory_only": True,
            }
        )

    return enriched_claims


def _as_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _severity_bucket(severity_score: float) -> str:
    if severity_score >= 80:
        return "HIGH"
    if severity_score >= 50:
        return "MEDIUM"
    return "LOW"


def _build_severity_score(cost_amount: float, severity_raw: Any) -> float:
    """
    Deterministic severity scoring (Phase-1):
    - cost drives most of the score
    - optional severity flag/code increases score
    """
    score = 0.0

    # Cost component (cap at 70)
    if cost_amount > 0:
        score += min(70.0, (cost_amount / 1000.0) * 70.0)

    severity_text = (str(severity_raw).strip().upper() if severity_raw is not None else "")
    if severity_text in {"CRITICAL", "HIGH", "S3"}:
        score += 30.0
    elif severity_text in {"MEDIUM", "S2"}:
        score += 15.0
    elif severity_text in {"LOW", "S1"}:
        score += 5.0

    return min(100.0, score)


def _classify_claim(
    claim: Dict[str, Any],
    repeat_count: int,
    concentration_ratio: float,
) -> Dict[str, Any]:
    """
    Deterministic classification rules:
    - separate evidence (observed) from advisory recommendation
    - no auto approvals / postings
    """
    cost = _as_float(claim.get("cost") or claim.get("cost_amount") or claim.get("amount") or claim.get("claim_cost") or 0)
    severity_raw = claim.get("severity") or claim.get("severity_code") or claim.get("priority")
    severity_score = _build_severity_score(cost, severity_raw)
    severity_bucket = _severity_bucket(severity_score)

    labels: List[str] = []
    if repeat_count >= 5:
        labels.append("REPEAT_FAILURE")
    if concentration_ratio >= 0.35 and repeat_count >= 3:
        labels.append("CONCENTRATION_SIGNAL")
    if severity_bucket == "HIGH" or cost >= 1500:
        labels.append("HIGH_SEVERITY")

    if not labels:
        labels = ["ISOLATED"]

    # Advisory recommendation (deterministic text)
    recommendations: List[str] = []
    if "REPEAT_FAILURE" in labels:
        recommendations.append("Investigate recurring failure code for this product family and validate repair actions.")
    if "CONCENTRATION_SIGNAL" in labels:
        recommendations.append("Check batch/serial range containment: review production window, inspection history and supplier lots.")
    if "HIGH_SEVERITY" in labels:
        recommendations.append("Prioritize triage due to high cost/severity; validate customer impact and consider expedited root-cause review.")
    if labels == ["ISOLATED"]:
        recommendations.append("Monitor only; no evidence of a wider pattern in current dataset.")

    return {
        "claim_id": claim.get("claim_id") or claim.get("id"),
        "product": claim.get("product") or claim.get("material") or claim.get("product_id"),
        "material": claim.get("material") or claim.get("product") or claim.get("material_id"),
        "supplier": claim.get("supplier") or claim.get("supplier_id"),
        "serial": claim.get("serial") or claim.get("serial_no") or claim.get("serial_number"),
        "batch": claim.get("batch") or claim.get("batch_no") or claim.get("batch_number"),
        "failure_code": claim.get("failure_code") or claim.get("failure") or claim.get("defect_code"),
        "claim_date": claim.get("claim_date") or claim.get("date"),
        "cost": cost,
        "severity_raw": severity_raw,
        "severity_score": severity_score,
        "severity_bucket": severity_bucket,
        "repeat_count": repeat_count,
        "concentration_ratio": concentration_ratio,
        "labels": labels,
        "observed_evidence": {
            "repeat_count": repeat_count,
            "concentration_ratio": concentration_ratio,
            "severity_score": severity_score,
        },
        "recommendations": recommendations,
        "advisory_only": True,
    }


@app.get("/api/intelligence/patterns")
def get_patterns(
    days: Optional[int] = Query(default=None, ge=1, le=365),
):
    """
    Aggregates recurring failure patterns by product/material + failure_code (+ optional supplier, batch).
    This uses deterministic SQL GROUP BY and is the Phase-1 backbone.
    """
    # keep query flexible: if schema doesn't have claim_date, the WHERE might fail;
    # so we only add it if requested and claim_date column exists (handled by try/except).
    base_sql = """
    SELECT
        COALESCE(product, material, product_id, material_id) AS product_key,
        failure_code,
        COUNT(*) AS claim_count,
        COUNT(DISTINCT COALESCE(batch, batch_no, batch_number)) AS batch_count,
        COUNT(DISTINCT COALESCE(serial, serial_no, serial_number)) AS serial_count,
        SUM(COALESCE(cost, cost_amount, amount, 0)) AS total_cost,
        AVG(COALESCE(cost, cost_amount, amount, 0)) AS avg_cost
    FROM WARRANTY_CLAIMS
    GROUP BY COALESCE(product, material, product_id, material_id), failure_code
    ORDER BY claim_count DESC, total_cost DESC
    """
    try:
        if days is None:
            return execute_query(base_sql)

        sql_with_date = """
        SELECT
            COALESCE(product, material, product_id, material_id) AS product_key,
            failure_code,
            COUNT(*) AS claim_count,
            COUNT(DISTINCT COALESCE(batch, batch_no, batch_number)) AS batch_count,
            COUNT(DISTINCT COALESCE(serial, serial_no, serial_number)) AS serial_count,
            SUM(COALESCE(cost, cost_amount, amount, 0)) AS total_cost,
            AVG(COALESCE(cost, cost_amount, amount, 0)) AS avg_cost
        FROM WARRANTY_CLAIMS
        WHERE claim_date >= ADD_DAYS(CURRENT_DATE, -?)
        GROUP BY COALESCE(product, material, product_id, material_id), failure_code
        ORDER BY claim_count DESC, total_cost DESC
        """
        return execute_query(sql_with_date, (days,))
    except Exception:
        # fallback to base query if claim_date not available
        return execute_query(base_sql)


@app.get("/api/intelligence/claims/{claim_id}")
def get_claim_intelligence(claim_id: str):
    """
    Returns deterministic classification + evidence for a single claim,
    and includes LLM advisory explanation if configured.
    """
    from app.chat import generate_warranty_explanation

    # 1) fetch claim
    claim_sql = """
    SELECT *
    FROM WARRANTY_CLAIMS
    WHERE claim_id = ?
    """
    claims = execute_query(claim_sql, (claim_id,))
    if not claims:
        # some schemas might use ID instead of claim_id
        claim_sql2 = """
        SELECT *
        FROM WARRANTY_CLAIMS
        WHERE id = ?
        """
        claims = execute_query(claim_sql2, (claim_id,))

    if not claims:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = claims[0]

    product_key = claim.get("product") or claim.get("material") or claim.get("product_id") or claim.get("material_id")
    failure_code = claim.get("failure_code") or claim.get("failure") or claim.get("defect_code")
    batch = claim.get("batch") or claim.get("batch_no") or claim.get("batch_number")

    if product_key is None or failure_code is None:
        raise HTTPException(
            status_code=400,
            detail="Claim is missing product/material or failure_code fields required for deterministic classification",
        )

    # 2) repeat count for same product+failure
    repeat_sql = """
    SELECT COUNT(*) AS repeat_count
    FROM WARRANTY_CLAIMS
    WHERE COALESCE(product, material, product_id, material_id) = ?
      AND failure_code = ?
    """
    repeat_rows = execute_query(repeat_sql, (product_key, failure_code))
    repeat_count = int(repeat_rows[0]["repeat_count"]) if repeat_rows else 1

    # 3) concentration ratio by batch for that product+failure (if batch exists)
    concentration_ratio = 0.0
    if batch is not None:
        batch_sql = """
        SELECT
            COUNT(*) AS batch_claim_count
        FROM WARRANTY_CLAIMS
        WHERE COALESCE(product, material, product_id, material_id) = ?
          AND failure_code = ?
          AND COALESCE(batch, batch_no, batch_number) = ?
        """
        batch_rows = execute_query(batch_sql, (product_key, failure_code, batch))
        batch_claim_count = int(batch_rows[0]["batch_claim_count"]) if batch_rows else 0
        concentration_ratio = (batch_claim_count / repeat_count) if repeat_count else 0.0

    classified_result = _classify_claim(
        claim=claim,
        repeat_count=repeat_count,
        concentration_ratio=concentration_ratio,
    )

    # 4) Add LLM explanation advisory
    llm_explanation = generate_warranty_explanation(classified_result)

    # Combine and return
    return {
        "classification": classified_result,
        "llm_explanation": llm_explanation,
    }

async function fetchClaims() {
    try {
        const response = await fetch('/api/claims');
        const claims = await response.json();
        console.log("Claims fetched:", claims); // DEBUG LOG
        return claims;
    } catch (error) {
        console.error('Error fetching claims:', error);
        return [];
    }
}

function appendCell(row, value, className = '') {
    const cell = document.createElement('td');
    cell.textContent = value ?? '';
    if (className) {
        cell.className = className;
    }
    row.appendChild(cell);
}

function appendRecommendationCell(row, claim) {
    const cell = document.createElement('td');
    cell.className = 'recommendations';

    const recommendationText = Array.isArray(claim.recommendations)
        ? claim.recommendations.join('\n\n')
        : '';
    const hasGeneratedAnalysis = recommendationText.includes('1. Observed evidence');

    const preview = document.createElement('div');
    preview.className = 'recommendation-preview';
    preview.textContent = hasGeneratedAnalysis
        ? 'AI warranty analysis available'
        : recommendationText.split('\n')[0];
    cell.appendChild(preview);

    if (hasGeneratedAnalysis) {
        const details = document.createElement('details');
        details.className = 'recommendation-details';

        const summary = document.createElement('summary');
        summary.textContent = 'View AI analysis';

        const body = document.createElement('div');
        body.className = 'recommendation-body';
        body.textContent = recommendationText;

        details.append(summary, body);
        cell.appendChild(details);
    }

    row.appendChild(cell);
}

function renderClaimsTable(claims) {
    const tbody = document.getElementById('claims-table-body');
    tbody.innerHTML = '';

    claims.forEach((claim) => {
        const tr = document.createElement('tr');

        appendCell(tr, claim.claim_id);
        appendCell(tr, claim.product || claim.product_id);
        appendCell(tr, claim.material || claim.material_id || claim.product_id);
        appendCell(tr, claim.supplier || claim.supplier_id);
        appendCell(tr, claim.serial);
        appendCell(tr, claim.batch || claim.batch_id);
        appendCell(tr, claim.failure_code);

        const severity = String(claim.severity || '').toLowerCase();
        appendCell(tr, claim.severity, `severity severity-${severity}`);
        appendRecommendationCell(tr, claim);

        tbody.appendChild(tr);
    });
}

async function initializeDashboard() {
    const claims = await fetchClaims();

    renderClaimsTable(claims);
}

document.addEventListener('DOMContentLoaded', initializeDashboard);

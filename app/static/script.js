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
    if (Array.isArray(value)) {
        cell.textContent = value.join(', ');
    } else if (value && typeof value === 'object') {
        cell.textContent = JSON.stringify(value);
    } else {
        cell.textContent = value ?? '';
    }
    if (className) {
        cell.className = className;
    }
    row.appendChild(cell);
}

function formatColumnName(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function findClaimValue(claim, column) {
    const matchingKey = Object.keys(claim).find(
        (key) => key.toLowerCase() === column.toLowerCase()
    );
    return matchingKey ? claim[matchingKey] : '';
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
    const tableHead = document.getElementById('claims-table-head');
    const tbody = document.getElementById('claims-table-body');
    tableHead.innerHTML = '';
    tbody.innerHTML = '';

    const apiColumns = [...new Set(claims.flatMap((claim) => Object.keys(claim)))];
    const requestedColumns = ['supplier_name', 'product_family', 'product_name'];
    const columns = [
        ...requestedColumns,
        ...apiColumns.filter((column) => !requestedColumns.includes(column.toLowerCase())),
    ];
    const headerRow = document.createElement('tr');
    columns.forEach((column) => {
        const header = document.createElement('th');
        header.textContent = formatColumnName(column);
        headerRow.appendChild(header);
    });
    tableHead.appendChild(headerRow);

    claims.forEach((claim) => {
        const tr = document.createElement('tr');

        columns.forEach((column) => {
            if (column === 'recommendations') {
                appendRecommendationCell(tr, claim);
                return;
            }

            const value = findClaimValue(claim, column);
            const className = column === 'severity'
                ? `severity severity-${String(value || '').toLowerCase()}`
                : '';
            appendCell(tr, value, className);
        });

        tbody.appendChild(tr);
    });
}

async function initializeDashboard() {
    const claims = await fetchClaims();

    renderClaimsTable(claims);
}

document.addEventListener('DOMContentLoaded', initializeDashboard);

/**
 * Chart.js utilities for fantasy football analytics.
 * Color palette: purple #6c5ce7, green #00b894, red #d63031, gray #636e72
 */

const COLORS = {
    purple: '#6c5ce7',
    green: '#00b894',
    red: '#d63031',
    gray: '#636e72',
    lightPurple: 'rgba(108, 92, 231, 0.15)',
    lightGreen: 'rgba(0, 184, 148, 0.15)',
    lightRed: 'rgba(214, 48, 49, 0.15)',
};

/**
 * Create a projection chart showing actual scores and projected future weeks.
 *
 * @param {string} canvasId - Canvas element ID
 * @param {Array} actualWeeks - [{week, points}]
 * @param {Array} projectedWeeks - [{week, points, low, high}]
 * @param {number} seasonAvg - Season average for reference line
 */
function createProjectionChart(canvasId, actualWeeks, projectedWeeks, seasonAvg) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const allWeeks = [];
    const actualData = [];
    const projectedData = [];
    const confidenceLow = [];
    const confidenceHigh = [];

    actualWeeks.forEach(w => {
        allWeeks.push('Wk ' + w.week);
        actualData.push(w.points);
        projectedData.push(null);
        confidenceLow.push(null);
        confidenceHigh.push(null);
    });

    projectedWeeks.forEach(w => {
        allWeeks.push('Wk ' + w.week);
        actualData.push(null);
        projectedData.push(w.points);
        confidenceLow.push(w.low);
        confidenceHigh.push(w.high);
    });

    // Bridge: connect last actual to first projected
    if (actualWeeks.length > 0 && projectedWeeks.length > 0) {
        projectedData[actualWeeks.length - 1] = actualData[actualWeeks.length - 1];
    }

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels: allWeeks,
            datasets: [
                {
                    label: 'Actual',
                    data: actualData,
                    borderColor: COLORS.purple,
                    backgroundColor: COLORS.purple,
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: COLORS.purple,
                    tension: 0.2,
                },
                {
                    label: 'Projected',
                    data: projectedData,
                    borderColor: COLORS.purple,
                    backgroundColor: COLORS.lightPurple,
                    borderWidth: 2,
                    borderDash: [6, 4],
                    pointRadius: 3,
                    pointStyle: 'triangle',
                    tension: 0.2,
                },
                {
                    label: 'Confidence High',
                    data: confidenceHigh,
                    borderColor: 'transparent',
                    backgroundColor: COLORS.lightPurple,
                    fill: '+1',
                    pointRadius: 0,
                },
                {
                    label: 'Confidence Low',
                    data: confidenceLow,
                    borderColor: 'transparent',
                    backgroundColor: COLORS.lightPurple,
                    fill: '-1',
                    pointRadius: 0,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                annotation: seasonAvg ? {
                    annotations: {
                        avgLine: {
                            type: 'line',
                            yMin: seasonAvg,
                            yMax: seasonAvg,
                            borderColor: COLORS.gray,
                            borderWidth: 1,
                            borderDash: [4, 4],
                            label: {
                                display: true,
                                content: 'Avg: ' + seasonAvg.toFixed(1),
                                position: 'end',
                            },
                        },
                    },
                } : {},
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Fantasy Points (PPR)' },
                },
            },
        },
    });
}

/**
 * Create a histogram chart for Monte Carlo simulation results.
 *
 * @param {string} canvasId - Canvas element ID
 * @param {Array} histogramData - [{bin_start, bin_end, count}]
 * @param {Object} percentiles - {p10, p25, p50, p75, p90}
 */
function createDistributionChart(canvasId, histogramData, percentiles) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const labels = histogramData.map(d =>
        d.bin_start.toFixed(0) + '-' + d.bin_end.toFixed(0)
    );
    const counts = histogramData.map(d => d.count);

    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Simulations',
                data: counts,
                backgroundColor: COLORS.lightPurple,
                borderColor: COLORS.purple,
                borderWidth: 1,
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Season Outcome Distribution',
                    font: { size: 14, weight: 'bold' },
                },
            },
            scales: {
                x: { title: { display: true, text: 'Projected Season Points' } },
                y: { title: { display: true, text: 'Simulations' }, beginAtZero: true },
            },
        },
    });
}

/**
 * Create a radar chart comparing player profile to cluster average.
 *
 * @param {string} canvasId - Canvas element ID
 * @param {Object} playerFeatures - {avg_points, std_dev, floor, ceiling, snap_pct, consistency}
 * @param {Object} clusterCenter - same keys as playerFeatures
 */
function createClusterRadarChart(canvasId, playerFeatures, clusterCenter) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const featureLabels = ['Avg Points', 'Std Dev', 'Floor', 'Ceiling', 'Snap %', 'Consistency'];
    const featureKeys = ['avg_points', 'std_dev', 'floor', 'ceiling', 'snap_pct', 'consistency'];

    const playerData = featureKeys.map(k => playerFeatures[k] || 0);
    const clusterData = featureKeys.map(k => clusterCenter[k] || 0);

    return new Chart(canvas, {
        type: 'radar',
        data: {
            labels: featureLabels,
            datasets: [
                {
                    label: 'Player',
                    data: playerData,
                    borderColor: COLORS.purple,
                    backgroundColor: COLORS.lightPurple,
                    borderWidth: 2,
                    pointRadius: 3,
                },
                {
                    label: 'Cluster Avg',
                    data: clusterData,
                    borderColor: COLORS.green,
                    backgroundColor: COLORS.lightGreen,
                    borderWidth: 2,
                    pointRadius: 3,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom' },
            },
            scales: {
                r: { beginAtZero: true },
            },
        },
    });
}

/**
 * Initialize the risk slider to update projections via API.
 *
 * @param {string} sliderId - Slider input element ID
 * @param {string} playerId - Player ID for API call
 * @param {number} season - Season year
 * @param {number} week - Week number
 */
function initRiskSlider(sliderId, playerId, season, week) {
    const slider = document.getElementById(sliderId);
    if (!slider) return;

    const riskLabels = ['conservative', 'medium', 'aggressive'];
    const riskLabelEl = document.getElementById('risk-label');
    const projValueEl = document.getElementById('proj-value');
    const projRangeEl = document.getElementById('proj-range');

    slider.addEventListener('input', function () {
        const riskLevel = riskLabels[parseInt(this.value)];
        if (riskLabelEl) riskLabelEl.textContent = riskLevel.charAt(0).toUpperCase() + riskLevel.slice(1);

        fetch('/api/projection/' + playerId + '?season=' + season + '&week=' + week + '&risk=' + riskLevel)
            .then(response => {
                if (!response.ok) throw new Error('API error');
                return response.json();
            })
            .then(data => {
                if (projValueEl) projValueEl.textContent = data.display_points.toFixed(1);
                if (projRangeEl) {
                    projRangeEl.textContent = data.confidence_low.toFixed(1) + ' - ' + data.confidence_high.toFixed(1);
                }
            })
            .catch(() => {});
    });
}

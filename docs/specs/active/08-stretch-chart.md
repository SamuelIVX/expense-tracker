# Spec: Stretch — Chart.js Bar Chart

## Applicable Skills
- `owasp-security`: A08 Software and Data Integrity Failures (Subresource Integrity `integrity` and `crossorigin` on CDN scripts), A03 Injection defense (safe JSON serialization via `json.dumps()`).
- `better-ui`: Data visualization consistency, aligning chart series colors with CSS category design tokens.

## Objective
Enhance the spending dashboard with an interactive horizontal bar chart using Chart.js loaded via CDN.
This visualizes the per-category expenditure breakdown computed by spec 06 without requiring any new
database queries or backend models. This is an optional stretch feature designed to demonstrate client-side
data visualization skills.

> **Status: `[stretch]` — Implement only if core specs 01–07 are complete. Do NOT mark complete in final submission unless verified working.**

## Scope
- Package: `expense-tracker`
- Modifies (existing):
  - `tracker/views.py` (serializes `category_breakdown` to JSON using `json.dumps()`)
  - `templates/tracker/dashboard.html` (adds Chart.js CDN script tag with SRI, `<canvas>` container, and chart initialization script)
- Off-limits: all other backend and template files.

## Non-Goals
- No dedicated JSON API endpoint (data is passed directly via Django template context).
- No complex multi-series or drill-down interactions.
- No client-side build tools (npm/Vite) — Chart.js is imported strictly via CDN.

## Invariants
- Chart.js MUST be imported from a reputable public CDN (e.g. `cdn.jsdelivr.net`) with an explicit Subresource Integrity (SRI) hash and `crossorigin="anonymous"`. [OWASP A08 / ASVS 14.2.4]
- Chart data embedded in the HTML MUST be JSON-encoded via `json.dumps()` in Python and marked `|safe` in the template to avoid invalid JavaScript syntax and XSS vectors. [OWASP A03]
- The chart canvas MUST NOT render when there are no transactions in the current month.

## Requirements
1. WHEN `category_breakdown` contains at least one item, THE SYSTEM SHALL render a `<canvas id="categoryChart">` inside `templates/tracker/dashboard.html`.
2. THE SYSTEM SHALL load Chart.js v4.4.2 from CDN with Subresource Integrity:
   ```html
   <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js" 
           integrity="sha256-R4pqcOYV8lt7snxMQO/HSbVCFRPMdrhAFMH+vr9giYI=" 
           crossorigin="anonymous"></script>
   ```
3. THE SYSTEM SHALL pass `category_breakdown_json` in the view context containing category names, colors, and total spending.
4. THE SYSTEM SHALL instantiate a horizontal bar chart displaying:
   - Y-axis: Category names
   - X-axis: Dollar amounts formatted as currency (`$XX.XX`)
   - Bar colors matching each category's configured `color` attribute
5. WHEN `category_breakdown` is empty, THE SYSTEM SHALL NOT render the chart canvas.

## Acceptance Criteria
- [ ] Chart.js loads cleanly from CDN with valid SRI without browser console errors.
- [ ] Navigating to `/dashboard/` with recorded expenses displays both the data table and the interactive bar chart.
- [ ] Hovering over a chart bar displays a tooltip with the exact formatted currency amount.
- [ ] Zero-state months display the zero-state message without attempting to initialize Chart.js.

## Design

### `tracker/views.py` (Add JSON Serialization)
```python
import json

# Inside dashboard_view, before render:
category_breakdown_json = json.dumps(category_breakdown)

context = {
    ...
    'category_breakdown_json': category_breakdown_json,
}
```

### `templates/tracker/dashboard.html` (Chart.js Script Excerpt)
```html
{% if category_breakdown %}
    <div class="et-chart-container" style="margin-top: 2rem;">
        <canvas id="categoryChart" height="200" aria-label="Horizontal bar chart showing spending by category" role="img"></canvas>
    </div>
{% endif %}

{% block extra_js %}
{% if category_breakdown %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js" 
        integrity="sha256-R4pqcOYV8lt7snxMQO/HSbVCFRPMdrhAFMH+vr9giYI=" 
        crossorigin="anonymous"></script>
<script>
    document.addEventListener('DOMContentLoaded', () => {
        const rawData = {{ category_breakdown_json|safe }};
        const canvas = document.getElementById('categoryChart');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: rawData.map(item => item.name),
                datasets: [{
                    label: 'Spent ($)',
                    data: rawData.map(item => item.total),
                    backgroundColor: rawData.map(item => item.color),
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => '$' + Number(value).toFixed(2)
                        }
                    }
                }
            }
        });
    });
</script>
{% endif %}
{% endblock %}
```

## Constraints
- Dependencies: `06-dashboard` must be completed and merged.

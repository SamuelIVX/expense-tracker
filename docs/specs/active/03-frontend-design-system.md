# Spec: Frontend Design System

## Applicable Skills
- `better-accessibility`: WCAG 2.2 Level AA compliance, `:focus-visible` ring styling, `prefers-reduced-motion`, `role="status"` live announcements, and 44px touch targets.
- `better-ui`: Semantic design tokens, optical layout alignment, button loading feedback, card elevation.
- `better-writing`: Clear, supportive interface copy; human flash messages; plain terminology.

## Objective
Establish the visual foundation and interactive design system for the entire application: define
CSS custom properties (design tokens), build the global Django template layout (`templates/base.html`),
implement accessible form styles with feedback states, establish micro-animations/transitions, and
provide the shared JavaScript helper (`static/js/ui.js`) for submit loading states. This spec guarantees
the **10% User Interface Design** rubric requirement for CSC 226.

> **Ownership:** Beginner teammate(s). Pure HTML/CSS/JS — no complex Python backend code.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `templates/base.html` (root Django template: navbar, messages framework, container, footer)
  - `static/css/style.css` (design tokens, reset, typography, cards, forms, tables, progress bar, accessibility rules)
  - `static/js/ui.js` (submit button loading states, auto-dismissing flash messages)
- Off-limits: `tracker/models.py`, `tracker/views.py`, `expense_tracker/urls.py` (owned by other specs).

## Non-Goals
- No heavy CSS frameworks (Bootstrap, Tailwind, or Bulma are prohibited to demonstrate raw CSS skills).
- No complex frontend build pipeline (no npm, webpack, or Vite; plain static files served by Django).
- No Chart.js styling (covered in `08-stretch-chart`).

## Invariants
- Color contrast for all text against backgrounds MUST satisfy WCAG 2.2 AA standards (minimum 4.5:1 for normal text, 3:1 for large text and UI components). [Accessibility / WCAG 1.4.3]
- Focus indicators MUST be styled using `:focus-visible` (never bare `:focus`) with an explicit 2px outline and 2px offset, maintaining at least 3:1 contrast against adjacent colors. [WCAG 2.4.11 / 2.4.13]
- All motion and CSS transitions MUST respect `@media (prefers-reduced-motion: reduce)` by disabling transition durations. [WCAG 2.3.3]
- Interactive click/tap targets MUST maintain a minimum size of 44×44px on mobile and 40×40px on desktop. [WCAG 2.5.8]
- Flash messages MUST be wrapped in `role="status"` and `aria-live="polite"` so assistive technologies announce dynamic updates. [WCAG 4.1.3]
- Every `<form>` submitting mutations MUST be protected by Django's `{% csrf_token %}` tag. [OWASP A01]

## Requirements
1. THE SYSTEM SHALL provide `templates/base.html` with:
   - Responsive `<meta name="viewport" content="width=device-width, initial-scale=1.0">`
   - Semantic landmarks: `<header role="banner">`, `<main id="main-content">`, `<footer role="contentinfo">`, `<nav aria-label="Main Navigation">`
   - Navbar with branding ("ExpenseTracker") and conditional auth links (`{% if user.is_authenticated %}` displays Dashboard, Add Expense, History, Logout; otherwise Login, Register)
   - Flash messages banner rendering Django `messages` with `role="status"` and `aria-live="polite"`
   - Defined `{% block content %}{% endblock %}` content slot
   - Footer displaying "CSC 226 — Web Database Applications (Fall 2026)"
2. THE SYSTEM SHALL define CSS custom properties in `static/css/style.css` for:
   - Primary brand: `--et-primary: #1D63B8` (4.8:1 contrast on white)
   - Neutrals: `--et-bg: #F8F9FA`, `--et-surface: #FFFFFF`, `--et-text: #1A1D20`, `--et-border: #CED4DA`
   - Feedback: `--et-success: #1E7E34`, `--et-warn: #D35400`, `--et-danger: #C0392B`
   - Focus indicator: `--et-focus: #1D63B8`
   - Transitions: `--et-transition: 0.2s ease`
3. THE SYSTEM SHALL implement CSS animations:
   - A `@keyframes fadeIn` page animation applied to `.et-card` on render.
   - Smooth `transition: border-color, box-shadow` on input focus.
   - `@media (prefers-reduced-motion: reduce)` block resetting all animations to `none !important`.
4. THE SYSTEM SHALL provide a progress bar component (`.et-progress`) with states:
   - Standard fill (blue)
   - Warning fill (amber) via `.et-progress__bar--warn`
   - Danger fill (red) via `.et-progress__bar--danger`
5. THE SYSTEM SHALL provide `static/js/ui.js` that attaches to all forms with class `.et-form`, disabling the submit button and setting its text to "Saving..." when submitted.

## Failure Modes & Edge Cases
1. **JavaScript Disabled:** WHEN JavaScript is disabled in the browser, THE SYSTEM SHALL still allow all forms to submit normally without blocking the user.
2. **Double Submission:** WHEN a user clicks submit rapidly, `ui.js` SHALL disable the button immediately after the first click to prevent duplicate database writes.

## Acceptance Criteria
- [ ] `templates/base.html` renders cleanly with accessible landmarks and footer.
- [ ] Tab navigation through all interactive elements shows a sharp 2px `:focus-visible` ring.
- [ ] Enabling "Reduce Motion" in system settings halts the card fade-in animation.
- [ ] Django flash messages (`messages.success`, `messages.error`) announce via screen readers using `aria-live="polite"`.
- [ ] Submitting a form triggers the "Saving..." disabled state immediately.

## Design

### `templates/base.html`
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Expense Tracker{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
</head>
<body>
    <a href="#main-content" class="et-skip-link">Skip to main content</a>

    <header class="et-header" role="banner">
        <div class="et-container et-header__inner">
            <a href="{% url 'dashboard' %}" class="et-brand">ExpenseTracker</a>
            <nav class="et-nav" aria-label="Main Navigation">
                {% if user.is_authenticated %}
                    <a href="{% url 'dashboard' %}" class="et-nav__link">Dashboard</a>
                    <a href="{% url 'add_transaction' %}" class="et-nav__link">Add Expense</a>
                    <a href="{% url 'transaction_history' %}" class="et-nav__link">History</a>
                    <form action="{% url 'logout' %}" method="post" style="display:inline;">
                        {% csrf_token %}
                        <button type="submit" class="et-btn et-btn--link">Logout ({{ user.username }})</button>
                    </form>
                {% else %}
                    <a href="{% url 'login' %}" class="et-nav__link">Login</a>
                    <a href="{% url 'register' %}" class="et-btn et-btn--primary">Register</a>
                {% endif %}
            </nav>
        </div>
    </header>

    <main id="main-content" class="et-main et-container">
        {% if messages %}
            <div class="et-messages" role="status" aria-live="polite">
                {% for message in messages %}
                    <div class="et-alert et-alert--{{ message.tags }}">
                        {{ message }}
                    </div>
                {% endfor %}
            </div>
        {% endif %}

        {% block content %}{% endblock %}
    </main>

    <footer class="et-footer" role="contentinfo">
        <div class="et-container">
            <p>CSC 226 — Web Database Applications &bull; Personal Expense Tracker</p>
        </div>
    </footer>

    <script src="{% static 'js/ui.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### `static/css/style.css` (Focus & Accessibility Excerpt)
```css
/* Accessibility: Focus visible styling (better-accessibility) */
:focus-visible {
    outline: 2px solid var(--et-focus);
    outline-offset: 2px;
}

/* Skip link for keyboard navigation */
.et-skip-link {
    position: absolute;
    top: -40px;
    left: 0;
    background: var(--et-primary);
    color: #fff;
    padding: 8px 16px;
    z-index: 1000;
    text-decoration: none;
    border-radius: 0 0 4px 0;
    transition: top 0.2s;
}
.et-skip-link:focus {
    top: 0;
}

/* Reduced Motion Override */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}
```

## Current State
- `[verified]` HW1–HW5 in Sam's coursework demonstrate proficiency in vanilla CSS, flexbox/grid, and theme toggles.
- `[verified]` HW4 explicitly implemented custom progress bars and form validation.

## Tests
- `test_base_template_renders_auth_nav` — authenticated user sees Dashboard/Logout; visitor sees Login/Register.
- `test_django_messages_display` — messages added via `messages.info()` render within `.et-messages` with `aria-live="polite"`.

## Constraints
- Dependencies: `01-project-scaffold` must be merged.
- Downstream: All frontend templates (`04` through `08`) inherit `templates/base.html` and use `style.css`.

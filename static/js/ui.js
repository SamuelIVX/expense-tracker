/**
 * Expense Tracker — UI Interactive Utilities
 * CSC 226: Web Database Applications (Fall 2026)
 *
 * Provides button loading feedback on form submission to prevent double clicks,
 * bfcache restoration, client-side alert dismissals, and accessibility-compliant interactions.
 */

(function () {
    'use strict';

    /**
     * Resets a form's submitting state and restores original button content and interactivity.
     * @param {HTMLFormElement} form
     */
    function resetButtonState(form) {
        if (!form) {
            return;
        }
        delete form.dataset.submitting;

        var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!submitBtn) {
            return;
        }

        var originalContent = submitBtn.getAttribute('data-original-content');
        if (originalContent !== null) {
            if (submitBtn.tagName === 'INPUT') {
                submitBtn.value = originalContent;
            } else {
                submitBtn.innerHTML = originalContent;
            }
        }
        submitBtn.disabled = false;
        submitBtn.classList.remove('is-loading');
    }

    /**
     * Initializes double-submission protection on forms marked with .et-form.
     */
    function initFormSubmissionGuards() {
        var forms = document.querySelectorAll('form.et-form');
        forms.forEach(function (form) {
            form.addEventListener('submit', function (event) {
                // If the form fails client-side HTML5 validation, do not intercept
                if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
                    return;
                }

                // If already submitting or already prevented, stop duplicate submissions
                if (form.dataset.submitting === 'true' || event.defaultPrevented) {
                    event.preventDefault();
                    return;
                }

                var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (!submitBtn) {
                    return;
                }

                // Mark form as actively submitting synchronously to block rapid repeated submits
                form.dataset.submitting = 'true';

                // Defer button disabling slightly to allow form data serialization and other handlers
                setTimeout(function () {
                    if (event.defaultPrevented) {
                        delete form.dataset.submitting;
                        return;
                    }

                    // Cache original button content
                    var originalContent = submitBtn.tagName === 'INPUT' ? submitBtn.value : submitBtn.innerHTML;
                    if (!submitBtn.hasAttribute('data-original-content')) {
                        submitBtn.setAttribute('data-original-content', originalContent);
                    }

                    // Update text to indicate ongoing processing
                    if (submitBtn.tagName === 'INPUT') {
                        submitBtn.value = 'Saving...';
                    } else {
                        submitBtn.textContent = 'Saving...';
                    }

                    submitBtn.disabled = true;
                    submitBtn.classList.add('is-loading');
                }, 0);
            });
        });
    }

    /**
     * Attaches click handlers to dismissible flash message close buttons.
     */
    function initAlertDismissals() {
        var closeButtons = document.querySelectorAll('.et-alert__close');
        closeButtons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var alert = btn.closest('.et-alert');
                if (alert) {
                    var hadFocus = alert.contains(document.activeElement);
                    alert.style.opacity = '0';
                    alert.style.transform = 'translateY(-4px)';
                    setTimeout(function () {
                        if (alert && alert.parentNode) {
                            alert.parentNode.removeChild(alert);
                            // Return focus to main landmark only if active focus was within the alert
                            var mainContent = document.getElementById('main-content');
                            if (hadFocus && mainContent) {
                                mainContent.focus();
                            }
                        }
                    }, 200);
                }
            });
        });
    }

    /**
     * Restores form button states when navigating back via browser bfcache.
     */
    function initBfcacheRestoration() {
        window.addEventListener('pageshow', function (event) {
            if (event.persisted) {
                var forms = document.querySelectorAll('form.et-form');
                forms.forEach(function (form) {
                    resetButtonState(form);
                });
            }
        });
    }

    /**
     * Initializes dark/light mode toggle with persistence and event notification.
     */
    function initThemeToggle() {
        var toggleBtn = document.getElementById('theme-toggle');
        if (!toggleBtn) {
            return;
        }

        function updateAria(theme) {
            var isDark = theme === 'dark';
            toggleBtn.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            toggleBtn.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        }

        var currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        updateAria(currentTheme);

        toggleBtn.addEventListener('click', function () {
            var activeTheme = document.documentElement.getAttribute('data-theme') || 'light';
            var nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', nextTheme);
            try {
                localStorage.setItem('et-theme', nextTheme);
            } catch (e) {
                // Ignore storage quotas / disabled storage
            }
            updateAria(nextTheme);

            // Dispatch custom event for reactive components (such as Chart.js)
            window.dispatchEvent(new CustomEvent('themechanged', { detail: { theme: nextTheme } }));
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initFormSubmissionGuards();
            initAlertDismissals();
            initBfcacheRestoration();
            initThemeToggle();
        });
    } else {
        initFormSubmissionGuards();
        initAlertDismissals();
        initBfcacheRestoration();
        initThemeToggle();
    }
})();

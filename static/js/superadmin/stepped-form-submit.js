/*
 * Rescue submits on the multi-step onboarding forms.
 *
 * These forms hide every step but the current one with `display: none`, and the
 * fields inside carry HTML5 `required`. When the last step's Submit is pressed
 * the browser validates the whole form; if an empty required field sits in a
 * hidden step it cannot be focused, so Chrome writes
 *   "An invalid form control with name='...' is not focusable"
 * to the console and silently refuses to submit. Nothing moves, nothing
 * explains why — reported as "parent onboarding not submitting".
 *
 * Two fixes:
 *   1. On submit, find the first invalid control, switch to the step holding
 *      it, then let the browser report it where the user can see it.
 *   2. On Next, block moving past a step whose required fields are empty, so
 *      the problem is caught where it happens rather than at the end.
 *
 * Pure enhancement: a valid form submits exactly as before.
 */
(function () {
    'use strict';

    function stepNumberOf(el) {
        var section = el.closest('.step-content');
        if (!section || !section.id) return null;
        var n = parseInt(section.id.replace(/[^0-9]/g, ''), 10);
        return isNaN(n) ? null : n;
    }

    function showStep(n) {
        var sections = document.querySelectorAll('.step-content');
        sections.forEach(function (section) {
            var id = parseInt((section.id || '').replace(/[^0-9]/g, ''), 10);
            section.style.display = id === n ? 'block' : 'none';
        });

        // Keep the stepper header and the Back/Next/Submit buttons in step.
        var total = sections.length;
        document.querySelectorAll('.step').forEach(function (dot, i) {
            dot.classList.remove('active', 'completed');
            if (i + 1 < n) dot.classList.add('completed');
            else if (i + 1 === n) dot.classList.add('active');
        });
        var back = document.getElementById('backBtn');
        var next = document.getElementById('nextBtn');
        var submit = document.getElementById('submitBtn');
        if (back) back.style.display = n > 1 ? 'inline-flex' : 'none';
        if (next) next.style.display = n < total ? 'inline-flex' : 'none';
        if (submit) submit.style.display = n === total ? 'inline-flex' : 'none';
    }

    function firstInvalid(scope) {
        var controls = scope.querySelectorAll('input, select, textarea');
        for (var i = 0; i < controls.length; i++) {
            var c = controls[i];
            if (c.disabled || c.type === 'hidden') continue;
            if (typeof c.checkValidity === 'function' && !c.checkValidity()) return c;
        }
        return null;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.querySelector('form.onboard-form, form#parentForm, form#teacherForm')
                || document.querySelector('.step-content') && document.querySelector('form');
        if (!form || !document.querySelector('.step-content')) return;

        form.addEventListener('submit', function (e) {
            if (form.checkValidity()) return;      // nothing to rescue

            e.preventDefault();
            var bad = firstInvalid(form);
            if (!bad) return;

            var n = stepNumberOf(bad);
            if (n) showStep(n);

            // Only reachable once its step is visible.
            window.setTimeout(function () {
                try { bad.reportValidity(); } catch (err) { /* older browsers */ }
                try { bad.focus({ preventScroll: false }); } catch (err) { bad.focus(); }
                bad.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 0);
        });

        // Catch it at the step boundary too, so the user isn't told at step 8
        // about something they left blank at step 2.
        var next = document.getElementById('nextBtn');
        if (next) {
            next.addEventListener('click', function (e) {
                var visible = Array.prototype.filter.call(
                    document.querySelectorAll('.step-content'),
                    function (s) { return s.style.display !== 'none'; }
                )[0];
                if (!visible) return;
                var bad = firstInvalid(visible);
                if (!bad) return;
                e.preventDefault();
                e.stopImmediatePropagation();
                try { bad.reportValidity(); } catch (err) { /* noop */ }
                bad.focus();
            }, true);   // capture, so it runs before the page's own Next handler
        }
    });
})();

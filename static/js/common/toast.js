/* =====================================================================
   Enpower Skill Lab — Unified Toast Notification System
   Global API:  showToast(message, type, title)
                showToast('Message sent', 'success')
                showToast('Something went wrong', 'error', 'Oops')
   type: 'success' | 'error' | 'warning' | 'info'  (default 'success')

   Also:
   - auto-dismisses any server-rendered Django-messages toasts on load
   - toastFromResponse(data): drives a toast from a {success, message}
     JsonResponse in one line.
   Position: top-right · auto-dismiss 3s · slide-out on close.
   ===================================================================== */
(function (window, document) {
    'use strict';

    var DISMISS_MS = 3000;   // matches CSS progress-bar duration
    var CLOSE_MS = 300;      // matches .closing animation

    var ICONS = {
        success: 'check_circle',
        error: 'cancel',
        warning: 'warning',
        info: 'info'
    };
    var TITLES = {
        success: 'Success',
        error: 'Error',
        warning: 'Warning',
        info: 'Info'
    };

    function getContainer() {
        var c = document.querySelector('.toast-container');
        if (!c) {
            c = document.createElement('div');
            c.className = 'toast-container';
            document.body.appendChild(c);
        }
        return c;
    }

    function dismiss(toast) {
        if (!toast || toast.classList.contains('closing')) return;
        toast.classList.add('closing');
        setTimeout(function () {
            if (toast.parentElement) toast.remove();
        }, CLOSE_MS);
    }

    // exposed so inline onclick="closeToast(this)" in templates keeps working
    function closeToast(button) {
        dismiss(button.closest ? button.closest('.toast') : button);
    }

    function armAutoDismiss(toast) {
        setTimeout(function () { dismiss(toast); }, DISMISS_MS);
    }

    /**
     * Show a toast programmatically.
     * @param {string} message  action-specific text ("Message sent")
     * @param {string} [type]   success|error|warning|info (default success)
     * @param {string} [title]  optional heading override
     */
    function showToast(message, type, title) {
        type = (type && ICONS[type]) ? type : 'success';
        var container = getContainer();

        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.setAttribute('data-toast', '');
        toast.innerHTML =
            '<div class="toast-icon"><span class="material-symbols-outlined">' + ICONS[type] + '</span></div>' +
            '<div class="toast-content">' +
                '<div class="toast-title"></div>' +
                '<div class="toast-message"></div>' +
            '</div>' +
            '<button class="toast-close" type="button" aria-label="Close">' +
                '<span class="material-symbols-outlined">close</span>' +
            '</button>' +
            '<div class="toast-progress"><div class="toast-progress-bar"></div></div>';

        // textContent (not innerHTML) => safe against injection from server messages
        toast.querySelector('.toast-title').textContent = title || TITLES[type];
        toast.querySelector('.toast-message').textContent = message == null ? '' : String(message);
        toast.querySelector('.toast-close').addEventListener('click', function () { dismiss(toast); });

        container.appendChild(toast);
        armAutoDismiss(toast);
        return toast;
    }

    /**
     * One-liner for AJAX: showToast from a {success, message} JsonResponse.
     * Falls back to sensible defaults when message is absent.
     */
    function toastFromResponse(data, opts) {
        opts = opts || {};
        var ok = data && (data.success === true || data.ok === true);
        var msg = (data && data.message) || (ok ? (opts.successText || 'Done successfully') : (opts.errorText || 'Something went wrong'));
        return showToast(msg, ok ? 'success' : 'error');
    }

    // Wire up server-rendered Django-messages toasts already in the DOM,
    // and normalise Django's 'error'/'warning' etc. tags handled in template.
    function initServerToasts() {
        document.querySelectorAll('.toast-container [data-toast]').forEach(function (toast, i) {
            // ensure each has a close handler + staggered auto-dismiss
            var btn = toast.querySelector('.toast-close');
            if (btn && !btn.dataset.eslBound) {
                btn.dataset.eslBound = '1';
                btn.addEventListener('click', function () { dismiss(toast); });
            }
            setTimeout(function () { dismiss(toast); }, DISMISS_MS + i * 250);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initServerToasts);
    } else {
        initServerToasts();
    }

    // Global exports
    window.showToast = showToast;
    window.closeToast = closeToast;
    window.toastFromResponse = toastFromResponse;
})(window, document);

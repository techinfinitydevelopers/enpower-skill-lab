/* ============================================
   TEACHER BASE JAVASCRIPT
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeHeader();
    initializeToasts();
});

/* Sidebar Functionality */
function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const menuToggle = document.getElementById('menuToggle');
    const closeSidebar = document.getElementById('closeSidebar');
    const mainContent = document.querySelector('.main-content');
    const dropdownToggles = document.querySelectorAll('.sidebar-dropdown-toggle');

    // Menu toggle - works for both mobile and desktop
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            if (window.innerWidth < 1024) {
                // Mobile: show sidebar overlay
                sidebar.classList.add('active');
                sidebarOverlay.classList.add('active');
                document.body.style.overflow = 'hidden';
            } else {
                // Desktop: collapse/expand sidebar
                sidebar.classList.toggle('collapsed');
                if (mainContent) {
                    mainContent.classList.toggle('expanded');
                }
            }
        });
    }

    // Close sidebar (mobile only)
    if (closeSidebar) {
        closeSidebar.addEventListener('click', closeSidebarMenu);
    }

    // Close on overlay click (mobile only)
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebarMenu);
    }

    function closeSidebarMenu() {
        sidebar.classList.remove('active');
        sidebarOverlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    // Dropdown toggles
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            const parent = this.closest('.sidebar-dropdown');
            
            // Close other dropdowns
            document.querySelectorAll('.sidebar-dropdown').forEach(dropdown => {
                if (dropdown !== parent) {
                    dropdown.classList.remove('active');
                }
            });

            // Toggle current dropdown
            parent.classList.toggle('active');
        });
    });

    // Close sidebar on window resize if desktop
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 1024) {
            closeSidebarMenu();
        }
    });
}

/* Header Functionality */
function initializeHeader() {
    const notificationToggle = document.getElementById('notificationToggle');
    const notificationDropdown = document.getElementById('notificationDropdownMenu');
    const userInfoToggle = document.getElementById('userInfoToggle');
    const userDropdown = document.getElementById('userDropdownMenu');
    const fullscreenBtn = document.querySelector('.fullscreen-btn');

    // Notification dropdown toggle
    if (notificationToggle && notificationDropdown) {
        notificationToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            notificationDropdown.classList.toggle('active');
            if (userDropdown) {
                userDropdown.classList.remove('active');
            }
        });
    }

    // User dropdown toggle
    if (userInfoToggle && userDropdown) {
        userInfoToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            userDropdown.classList.toggle('active');
            if (notificationDropdown) {
                notificationDropdown.classList.remove('active');
            }
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (notificationDropdown && !notificationDropdown.contains(e.target) && !notificationToggle.contains(e.target)) {
            notificationDropdown.classList.remove('active');
        }
        if (userDropdown && !userDropdown.contains(e.target) && !userInfoToggle.contains(e.target)) {
            userDropdown.classList.remove('active');
        }
    });

    // Fullscreen toggle
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', function() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => {
                    console.log('Error attempting to enable fullscreen:', err);
                });
                this.querySelector('.material-symbols-outlined').textContent = 'fullscreen_exit';
            } else {
                document.exitFullscreen();
                this.querySelector('.material-symbols-outlined').textContent = 'fullscreen';
            }
        });
    }

    // Update fullscreen button on fullscreen change
    document.addEventListener('fullscreenchange', function() {
        if (fullscreenBtn) {
            const icon = fullscreenBtn.querySelector('.material-symbols-outlined');
            if (document.fullscreenElement) {
                icon.textContent = 'fullscreen_exit';
            } else {
                icon.textContent = 'fullscreen';
            }
        }
    });
}

/* Toast Notifications */
function initializeToasts() {
    const toasts = document.querySelectorAll('[data-toast]');
    
    toasts.forEach(toast => {
        // Auto dismiss after 5 seconds
        setTimeout(() => {
            dismissToast(toast);
        }, 5000);
    });
}

function closeToast(button) {
    const toast = button.closest('.esl-toast');
    dismissToast(toast);
}

function dismissToast(toast) {
    if (toast) {
        toast.style.animation = 'toast-slide-out 0.4s ease forwards';
        setTimeout(() => {
            toast.remove();
        }, 400);
    }
}

// Add slide out animation
const style = document.createElement('style');
style.textContent = `
    @keyframes toast-slide-out {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// ============================================
// STUDENT PROFILE PAGE JAVASCRIPT
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Student Profile page loaded successfully');
    initializeProfileEvents();
});

// ============================================
// VALIDATION FUNCTIONS
// ============================================

function validateName(name) {
    if (!name || name.trim().length === 0) {
        return { valid: false, message: 'Name cannot be empty' };
    }
    if (name.trim().length < 2) {
        return { valid: false, message: 'Name must be at least 2 characters long' };
    }
    if (!/^[a-zA-Z\s.]+$/.test(name)) {
        return { valid: false, message: 'Name can only contain letters, spaces, and periods' };
    }
    return { valid: true };
}

function validateEmail(email) {
    if (!email || email.trim().length === 0) {
        return { valid: false, message: 'Email cannot be empty' };
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        return { valid: false, message: 'Please enter a valid email address' };
    }
    return { valid: true };
}

function validatePhone(phone) {
    if (!phone || phone.trim().length === 0) {
        return { valid: false, message: 'Phone number cannot be empty' };
    }
    // Indian phone number format: +91 followed by 10 digits
    const phoneRegex = /^(\+91[\s]?)?[6-9]\d{4}[\s]?\d{5}$/;
    if (!phoneRegex.test(phone.replace(/\s/g, ''))) {
        return { valid: false, message: 'Please enter a valid Indian phone number (10 digits starting with 6-9)' };
    }
    return { valid: true };
}

function validateDate(date) {
    if (!date || date.trim().length === 0) {
        return { valid: false, message: 'Date cannot be empty' };
    }
    return { valid: true };
}

function validateGender(gender) {
    if (!gender || gender.trim().length === 0) {
        return { valid: false, message: 'Gender cannot be empty' };
    }
    const validGenders = ['male', 'female', 'other'];
    if (!validGenders.includes(gender.toLowerCase())) {
        return { valid: false, message: 'Gender must be Male, Female, or Other' };
    }
    return { valid: true };
}

function validateBloodGroup(bloodGroup) {
    if (!bloodGroup || bloodGroup.trim().length === 0) {
        return { valid: false, message: 'Blood group cannot be empty' };
    }
    const validBloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
    if (!validBloodGroups.includes(bloodGroup.toUpperCase())) {
        return { valid: false, message: 'Please enter a valid blood group (A+, A-, B+, B-, AB+, AB-, O+, O-)' };
    }
    return { valid: true };
}

function validateAddress(address) {
    if (!address || address.trim().length === 0) {
        return { valid: false, message: 'Address cannot be empty' };
    }
    if (address.trim().length < 10) {
        return { valid: false, message: 'Address must be at least 10 characters long' };
    }
    return { valid: true };
}

function validateOccupation(occupation) {
    if (!occupation || occupation.trim().length === 0) {
        return { valid: false, message: 'Occupation cannot be empty' };
    }
    if (!/^[a-zA-Z\s]+$/.test(occupation)) {
        return { valid: false, message: 'Occupation can only contain letters and spaces' };
    }
    return { valid: true };
}

function validateText(text, fieldName) {
    if (!text || text.trim().length === 0) {
        return { valid: false, message: `${fieldName} cannot be empty` };
    }
    return { valid: true };
}

function validateField(fieldName, value) {
    switch(fieldName) {
        case 'fullName':
        case 'fatherName':
        case 'motherName':
        case 'emergencyName':
            return validateName(value);
        case 'email':
            return validateEmail(value);
        case 'phone':
        case 'fatherPhone':
        case 'motherPhone':
        case 'emergencyPhone':
            return validatePhone(value);
        case 'dob':
            return validateDate(value);
        case 'gender':
            return validateGender(value);
        case 'bloodGroup':
            return validateBloodGroup(value);
        case 'address':
            return validateAddress(value);
        case 'fatherOccupation':
        case 'motherOccupation':
            return validateOccupation(value);
        case 'nationality':
        case 'religion':
        case 'category':
        case 'previousSchool':
        case 'emergencyRelation':
            return validateText(value, fieldName.replace(/([A-Z])/g, ' $1').trim());
        default:
            return { valid: true };
    }
}

// ============================================
// ERROR HANDLING FUNCTIONS
// ============================================

function showError(inputElem, message) {
    // Remove existing error message if any
    const existingError = inputElem.parentElement.querySelector('.stud-prof-error-message');
    if (existingError) {
        existingError.remove();
    }

    // Add error class to input
    inputElem.classList.add('error');

    // Create and append error message
    const errorSpan = document.createElement('span');
    errorSpan.className = 'stud-prof-error-message';
    errorSpan.textContent = message;
    inputElem.parentElement.appendChild(errorSpan);
}

function clearError(inputElem) {
    // Remove error class
    inputElem.classList.remove('error');

    // Remove error message
    const errorMessage = inputElem.parentElement.querySelector('.stud-prof-error-message');
    if (errorMessage) {
        errorMessage.remove();
    }
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];
    return `${date.getDate()} ${months[date.getMonth()]}, ${date.getFullYear()}`;
}

// Get CSRF token for Django
function getCsrfToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfToken) {
        return csrfToken.value;
    }
    // Try to get from cookie
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    return '';
}

// ============================================
// CARD TOGGLE FUNCTIONALITY
// ============================================

function initializeCardToggle(cardName, ...fieldNames) {
    const toggleBtn = document.getElementById(`${cardName}ToggleBtn`);
    const toggleIcon = document.getElementById(`${cardName}ToggleIcon`);
    const toggleText = document.getElementById(`${cardName}ToggleText`);

    if (!toggleBtn || !toggleIcon || !toggleText) return;

    let isEditing = false;

    toggleBtn.addEventListener('click', () => {
        if (!isEditing) {
            // Switch to Save mode
            toggleIcon.textContent = 'check';
            toggleText.textContent = 'Save';
            toggleBtn.style.background = '#16a34a';
            toggleBtn.style.borderColor = '#16a34a';

            // Show input fields for all specified fields
            fieldNames.forEach(fieldName => {
                const valueElem = document.querySelector(`[data-field="${fieldName}"].stud-prof-info-value`);
                const inputElem = document.querySelector(`[data-field="${fieldName}"].stud-prof-info-input`);

                if (valueElem && inputElem) {
                    // Set current value to input/select
                    if (inputElem.tagName === 'SELECT') {
                        inputElem.value = valueElem.textContent.trim();
                    }

                    valueElem.style.display = 'none';
                    inputElem.style.display = 'block';
                    // Clear any existing errors
                    clearError(inputElem);
                }
            });

            isEditing = true;
        } else {
            // Validate all fields before saving
            let allValid = true;

            fieldNames.forEach(fieldName => {
                const inputElem = document.querySelector(`[data-field="${fieldName}"].stud-prof-info-input`);
                if (inputElem) {
                    const validation = validateField(fieldName, inputElem.value);
                    if (!validation.valid) {
                        allValid = false;
                        showError(inputElem, validation.message);
                    } else {
                        clearError(inputElem);
                    }
                }
            });

            if (!allValid) {
                return;
            }

            // Switch to Edit mode
            toggleIcon.textContent = 'edit';
            toggleText.textContent = 'Edit';
            toggleBtn.style.background = '';
            toggleBtn.style.borderColor = '';

            // Collect data for saving
            const formData = {};

            // Save values and hide inputs
            fieldNames.forEach(fieldName => {
                const valueElem = document.querySelector(`[data-field="${fieldName}"].stud-prof-info-value`);
                const inputElem = document.querySelector(`[data-field="${fieldName}"].stud-prof-info-input`);

                if (valueElem && inputElem) {
                    // Format the value for display
                    if (inputElem.type === 'date') {
                        valueElem.textContent = formatDate(inputElem.value);
                    } else {
                        valueElem.textContent = inputElem.value;
                    }
                    valueElem.style.display = 'block';
                    inputElem.style.display = 'none';
                    clearError(inputElem);

                    // Add to form data
                    formData[fieldName] = inputElem.value;
                }
            });

            // Save to server via AJAX
            saveProfileData(formData);

            isEditing = false;
        }
    });
}

// ============================================
// SAVE PROFILE DATA TO SERVER
// ============================================

async function saveProfileData(data) {
    const csrfToken = getCsrfToken();
    console.log('CSRF Token:', csrfToken ? 'Found' : 'Not found');
    console.log('Saving data:', data);
    
    if (!csrfToken) {
        showToast('Session expired. Please refresh the page.', 'error');
        return;
    }
    
    try {
        const response = await fetch('/student/profile/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        });

        console.log('Response status:', response.status);
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showToast('Profile updated successfully!', 'success');
            } else {
                showToast(result.message || 'Failed to update profile', 'error');
            }
        } else {
            const errorText = await response.text();
            console.error('Failed to save profile data:', errorText);
            showToast('Changes saved locally (server sync pending)', 'info');
        }
    } catch (error) {
        console.error('Error saving profile data:', error);
        showToast('Changes saved locally (server sync pending)', 'info');
    }
}

// ============================================
// AVATAR UPLOAD FUNCTIONALITY
// ============================================

async function uploadAvatar(file) {
    const formData = new FormData();
    formData.append('avatar', file);

    try {
        const response = await fetch('/student/profile/avatar/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                showToast('Avatar updated successfully!', 'success');
                return result.avatar_url;
            }
        }
    } catch (error) {
        console.error('Error uploading avatar:', error);
    }
    return null;
}

// ============================================
// TOAST NOTIFICATION
// ============================================

function showToast(message, type = 'info') {
    // Delegate to global toast API if available
    if (window.showToast) { return window.showToast(message, type); }

    // Fallback (older local implementation)
    // Remove existing toast
    const existingToast = document.querySelector('.stud-prof-toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `stud-prof-toast ${type}`;
    toast.innerHTML = `
        <span class="material-symbols-outlined">${type === 'success' ? 'check_circle' : type === 'error' ? 'error' : 'info'}</span>
        <span>${message}</span>
    `;

    // Add toast styles if not already present
    if (!document.querySelector('#toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .stud-prof-toast {
                position: fixed;
                bottom: 20px;
                right: 20px;
                padding: 12px 20px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 0.95rem;
                font-weight: 500;
                z-index: 9999;
                animation: slideIn 0.3s ease;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
            .stud-prof-toast.success {
                background: #dcfce7;
                color: #16a34a;
            }
            .stud-prof-toast.error {
                background: #fee2e2;
                color: #dc2626;
            }
            .stud-prof-toast.info {
                background: #dbeafe;
                color: #2563eb;
            }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(toast);

    // Remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// INITIALIZE PROFILE EVENTS
// ============================================

function initializeProfileEvents() {
    // Profile avatar upload
    const profileAvatarWrapper = document.getElementById('profileAvatarWrapper');
    const profileAvatarInput = document.getElementById('profileAvatarInput');
    const profileAvatar = document.getElementById('profileAvatar');

    if (profileAvatarWrapper && profileAvatarInput && profileAvatar) {
        profileAvatarWrapper.addEventListener('click', () => {
            profileAvatarInput.click();
        });

        profileAvatarInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (file) {
                // Validate file size (max 5MB)
                if (file.size > 5 * 1024 * 1024) {
                    showToast('Image size must be less than 5MB', 'error');
                    return;
                }

                // Validate file type
                if (!file.type.startsWith('image/')) {
                    showToast('Please select a valid image file', 'error');
                    return;
                }

                const reader = new FileReader();
                reader.onload = async (e) => {
                    const newAvatarSrc = e.target.result;
                    
                    // Update profile avatar
                    profileAvatar.src = newAvatarSrc;
                    
                    // Update all instances of user avatar on the page (header avatars)
                    document.querySelectorAll('.student-user-avatar, .student-dropdown-avatar').forEach(img => {
                        img.src = newAvatarSrc;
                    });

                    // Upload to server
                    const serverUrl = await uploadAvatar(file);
                    if (serverUrl) {
                        // Update with server URL if available
                        profileAvatar.src = serverUrl;
                        document.querySelectorAll('.student-user-avatar, .student-dropdown-avatar').forEach(img => {
                            img.src = serverUrl;
                        });
                        showToast('Avatar updated successfully!', 'success');
                    } else {
                        showToast('Avatar preview updated (save pending)', 'info');
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Header card edit/save toggle functionality
    const headerToggleBtn = document.getElementById('headerToggleBtn');
    const headerToggleIcon = document.getElementById('headerToggleIcon');
    const headerToggleText = document.getElementById('headerToggleText');

    if (headerToggleBtn && headerToggleIcon && headerToggleText) {
        let isHeaderEditing = false;

        headerToggleBtn.addEventListener('click', () => {
            const headerName = document.getElementById('headerName');
            const headerNameInput = document.getElementById('headerNameInput');
            const headerEmail = document.getElementById('headerEmail');
            const headerEmailInput = document.getElementById('headerEmailInput');
            const headerPhone = document.getElementById('headerPhone');
            const headerPhoneInput = document.getElementById('headerPhoneInput');

            if (!isHeaderEditing) {
                // Switch to Save mode
                headerToggleIcon.textContent = 'check';
                headerToggleText.textContent = 'Save';
                headerToggleBtn.style.background = '#16a34a';
                headerToggleBtn.style.borderColor = '#16a34a';

                // Show input fields
                if (headerName && headerNameInput) {
                    headerName.style.display = 'none';
                    headerNameInput.style.display = 'block';
                    clearError(headerNameInput);
                }
                if (headerEmail && headerEmailInput) {
                    headerEmail.style.display = 'none';
                    headerEmailInput.style.display = 'block';
                    clearError(headerEmailInput);
                }
                if (headerPhone && headerPhoneInput) {
                    headerPhone.style.display = 'none';
                    headerPhoneInput.style.display = 'block';
                    clearError(headerPhoneInput);
                }

                isHeaderEditing = true;
            } else {
                // Validate fields before saving
                let allValid = true;

                // Validate name
                if (headerNameInput) {
                    const nameValidation = validateName(headerNameInput.value);
                    if (!nameValidation.valid) {
                        allValid = false;
                        showError(headerNameInput, nameValidation.message);
                    } else {
                        clearError(headerNameInput);
                    }
                }

                // Validate email
                if (headerEmailInput) {
                    const emailValidation = validateEmail(headerEmailInput.value);
                    if (!emailValidation.valid) {
                        allValid = false;
                        showError(headerEmailInput, emailValidation.message);
                    } else {
                        clearError(headerEmailInput);
                    }
                }

                // Validate phone
                if (headerPhoneInput) {
                    const phoneValidation = validatePhone(headerPhoneInput.value);
                    if (!phoneValidation.valid) {
                        allValid = false;
                        showError(headerPhoneInput, phoneValidation.message);
                    } else {
                        clearError(headerPhoneInput);
                    }
                }

                if (!allValid) {
                    return;
                }

                // Switch to Edit mode
                headerToggleIcon.textContent = 'edit';
                headerToggleText.textContent = 'Edit';
                headerToggleBtn.style.background = '';
                headerToggleBtn.style.borderColor = '';

                // Collect data for saving
                const formData = {};

                // Save values and hide inputs
                if (headerName && headerNameInput) {
                    headerName.textContent = headerNameInput.value;
                    headerName.style.display = 'block';
                    headerNameInput.style.display = 'none';
                    clearError(headerNameInput);
                    formData.name = headerNameInput.value;
                }
                if (headerEmail && headerEmailInput) {
                    headerEmail.textContent = headerEmailInput.value;
                    headerEmail.style.display = 'block';
                    headerEmailInput.style.display = 'none';
                    clearError(headerEmailInput);
                    formData.email = headerEmailInput.value;
                }
                if (headerPhone && headerPhoneInput) {
                    headerPhone.textContent = headerPhoneInput.value;
                    headerPhone.style.display = 'block';
                    headerPhoneInput.style.display = 'none';
                    clearError(headerPhoneInput);
                    formData.phone = headerPhoneInput.value;
                }

                // Save to server
                saveProfileData(formData);

                isHeaderEditing = false;
            }
        });
    }

    // Personal Information card toggle functionality
    initializeCardToggle('personal', 'fullName', 'dob', 'gender', 'bloodGroup');

    // Contact Information card toggle functionality
    initializeCardToggle('contact', 'email', 'phone', 'address');

    // Parent/Guardian Information card toggle functionality
    initializeCardToggle('parent', 'fatherName', 'fatherOccupation', 'fatherPhone', 'motherName', 'motherOccupation', 'motherPhone');

    // Additional Information card toggle functionality
    initializeCardToggle('additional', 'nationality', 'religion', 'category', 'previousSchool');

    // Emergency Contact card toggle functionality
    initializeCardToggle('emergency', 'emergencyName', 'emergencyRelation', 'emergencyPhone');
}

// ============================================
// EXPORT FUNCTIONS FOR EXTERNAL USE
// ============================================
window.studentProfile = {
    validateField,
    showError,
    clearError,
    showToast,
    saveProfileData,
    uploadAvatar
};

console.log('Student Profile JS fully initialized');

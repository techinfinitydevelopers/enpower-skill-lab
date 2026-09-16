// Student List Page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize DataTable after a short delay to ensure jQuery is loaded
    setTimeout(initializeDataTable, 100);
});

// Initialize DataTable with custom configuration
function initializeDataTable() {
    if (typeof $ !== 'undefined' && $.fn.DataTable) {
        // Check if already initialized
        if ($.fn.DataTable.isDataTable('#studentTable')) {
            return;
        }
        
        $('#studentTable').DataTable({
            paging: true,
            pageLength: 10,
            lengthMenu: [5, 10, 25, 50],
            order: [[1, 'asc']],
            columnDefs: [
                { orderable: false, targets: [0, -1] } // Disable sorting on last column (Actions)
            ],
            language: {
                search: 'Search students:',
                lengthMenu: 'Show _MENU_ entries',
                info: 'Showing _START_ to _END_ of _TOTAL_ students',
                infoEmpty: 'No students to show',
                infoFiltered: '(filtered from _MAX_ total)',
                zeroRecords: 'No matching students found',
                paginate: {
                    next: 'Next',
                    previous: 'Previous'
                }
            },
            dom: '<"datatable-header"lfr>t<"datatable-footer"ip>'
        });
    }
}

// Generate initials from name
function getInitials(name) {
    if (!name) return '??';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
}

// Generate random color for initial badge
function getRandomColor() {
    const colors = [
        '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', 
        '#ef4444', '#06b6d4', '#ec4899', '#a855f7'
    ];
    return colors[Math.floor(Math.random() * colors.length)];
}

// Get status class based on status value
function getStatusClass(status) {
    switch (status.toLowerCase()) {
        case 'active':
            return 'status-active';
        case 'pending':
            return 'status-pending';
        case 'inactive':
            return 'status-inactive';
        default:
            return 'status-pending';
    }
}

// View student details
function viewStudent(studentId) {
    window.location.href = `/super-admin/student/${studentId}/`;
}

// Edit student
function editStudent(studentId) {
    window.location.href = `/super-admin/student/${studentId}/edit/`;
}

// Download sample CSV
function downloadSampleCSV() {
    // Create sample CSV content
    const csvContent = `student_id,first_name,middle_name,last_name,gender,date_of_birth,class,division,roll_number,status
S001,Rahul,,Kumar,male,2010-05-15,9,A,1,active
S002,Priya,,Sharma,female,2009-08-22,10,B,5,active
S003,Amit,,Verma,male,2010-11-03,9,C,12,pending`;

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'student_sample.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// Handle CSV upload
function handleCSVUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.csv')) {
        alert('Please upload a CSV file');
        return;
    }

    const formData = new FormData();
    formData.append('csv_file', file);

    // Submit to backend
    fetch('/super-admin/students/upload-csv/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Students uploaded successfully!');
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Upload error:', error);
        alert('An error occurred during upload');
    });
}

// Get CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

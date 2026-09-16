/* ============================================
   PROGRAM COORDINATOR LIST PAGE JAVASCRIPT
   Prefix: pcl- to avoid conflicts
   ============================================ */

$(function () {
    $('#pcl-coordinator-table').DataTable({
        paging: true,
        pageLength: 10,
        lengthMenu: [5, 10, 25, 50],
        order: [[1, 'asc']],
        columnDefs: [
            { orderable: false, targets: [0, 5, 9] }
        ],
        language: {
            search: 'Search coordinators:',
            lengthMenu: 'Show _MENU_ entries',
            info: 'Showing _START_ to _END_ of _TOTAL_ coordinators',
            infoEmpty: 'No coordinators to show',
            infoFiltered: '(_MAX_ total)',
            zeroRecords: 'No matching coordinators found',
            paginate: {
                next: 'Next',
                previous: 'Previous'
            }
        },
        dom: '<"pcl-datatable-header d-flex flex-column flex-lg-row align-items-start align-items-lg-center justify-content-between gap-3 p-3 border-bottom"l<"w-100"f>><"pcl-table-scroll-wrapper"t><"pcl-datatable-footer d-flex flex-column flex-lg-row align-items-start align-items-lg-center justify-content-between gap-3 p-3 border-top"ip>'
    });
});

function handlePCEdit(coordinatorId) {
    window.location.href = `/super-admin/coordinators/${coordinatorId}/edit/`;
}

function handlePCView(coordinatorId) {
    window.location.href = `/super-admin/coordinators/${coordinatorId}/`;
}

function handlePCDelete(coordinatorId, coordinatorName) {
    if (confirm(`Are you sure you want to delete "${coordinatorName}"?\n\nThis action cannot be undone.`)) {
        // Submit delete form
        const form = document.getElementById(`pcl-delete-form-${coordinatorId}`);
        if (form) {
            form.submit();
        }
    }
}

// CSV Download Sample function
function downloadSampleCSV() {
    // Sample CSV data
    const csvContent = [
        ['Employee ID', 'Full Name', 'Email', 'Mobile', 'Designation', 'Program Assigned', 'Zone', 'Joining Date', 'Status'],
        ['PC001', 'John Doe', 'john.doe@example.com', '+91 9876543210', 'Program Coordinator', 'CSL', 'North Zone', '2024-01-15', 'Active'],
        ['PC002', 'Jane Smith', 'jane.smith@example.com', '+91 9876543211', 'Project Coordinator', 'CSL+', 'South Zone', '2024-02-20', 'Active']
    ];

    const csv = csvContent.map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'coordinator_sample.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// CSV Upload function
function handleCSVUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const csv = e.target.result;
        console.log('CSV uploaded:', csv);
        // TODO: Implement CSV parsing and upload logic
        alert('CSV upload functionality will be implemented soon');
    };
    reader.readAsText(file);
}

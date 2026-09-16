// School Admin List JavaScript

$(function () {
  $('#adminTable').DataTable({
    paging: true,
    pageLength: 10,
    lengthMenu: [5, 10, 25, 50],
    order: [[1, 'asc']],
    columnDefs: [
      { orderable: false, targets: [0, 6] }  // Actions column not sortable
    ],
    language: {
      search: 'Search admins:',
      lengthMenu: 'Show _MENU_ entries',
      info: 'Showing _START_ to _END_ of _TOTAL_ admins',
      infoEmpty: 'No admins to show',
      infoFiltered: '(_MAX_ total)',
      zeroRecords: 'No matching admins found',
      paginate: {
        next: 'Next',
        previous: 'Previous'
      }
    },
    dom: '<"datatable-header d-flex flex-column flex-lg-row align-items-start align-items-lg-center justify-content-between gap-3 p-3 border-bottom"l<"w-100"f>><"table-scroll-wrapper"t><"datatable-footer d-flex flex-column flex-lg-row align-items-start align-items-lg-center justify-content-between gap-3 p-3 border-top"ip>'
  });
});

// Generate random color for initial badge
function getInitialBadgeColor(name) {
  const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4'];
  const index = name.charCodeAt(0) % colors.length;
  return colors[index];
}

// Get initials from admin name
function getInitials(name) {
  const words = name.trim().split(' ');
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
}

/**
 * Teacher List JavaScript
 * Handles DataTable initialization and functionality
 */

$(document).ready(function() {
    // Initialize DataTable
    var teacherTable = $('#teacherTable');
    
    if (teacherTable.length) {
        // Check if table has data rows (not just the empty message)
        var hasData = teacherTable.find('tbody tr').length > 0 && 
                      teacherTable.find('tbody tr td[colspan]').length === 0;
        
        if (hasData) {
            var table = teacherTable.DataTable({
                paging: true,
                searching: true,
                ordering: true,
                info: true,
                pageLength: 10,
                lengthMenu: [[5, 10, 25, 50, 100], [5, 10, 25, 50, 100]],
                order: [[1, 'asc']],
                columnDefs: [
                    { orderable: false, targets: [0, 6] }
                ],
                language: {
                    search: 'Search teachers:',
                    searchPlaceholder: 'Type to search...',
                    lengthMenu: 'Show _MENU_ entries',
                    info: 'Showing _START_ to _END_ of _TOTAL_ teachers',
                    infoEmpty: 'No teachers to show',
                    infoFiltered: '(filtered from _MAX_ total entries)',
                    zeroRecords: 'No matching teachers found',
                    paginate: {
                        next: 'Next',
                        previous: 'Previous'
                    }
                },
                initComplete: function() {
                    // Ensure search input is properly accessible
                    var searchInput = $('.dataTables_filter input');
                    searchInput.attr('type', 'text');
                    searchInput.css({
                        'pointer-events': 'auto',
                        'opacity': '1'
                    });
                }
            });
        }
    }
});

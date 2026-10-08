/**
 * ========================================
 * CLASS LIST PAGE FUNCTIONALITY
 * ========================================
 */

$(document).ready(function() {
    /**
     * ========================================
     * UTILITY FUNCTION: Extract Plain Text from HTML
     * ========================================
     */
    function extractPlainText(html) {
        if (!html) return '';
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        return tempDiv.textContent.trim().replace(/\s+/g, ' ');
    }

    /**
     * ========================================
     * CUSTOM FILTER FUNCTION FOR DATATABLES
     * ========================================
     */
    $.fn.dataTable.ext.search.push(
        function(settings, data, dataIndex) {
            if (settings.nTable.id !== 'classTable') {
                return true;
            }

            const locationFilter = $('#locationFilter').val();
            const schoolFilter = $('#schoolFilter').val();
            const yearFilter = $('#yearFilter').val();
            const statusFilter = $('#statusFilter').val();

            const schoolNameText = extractPlainText(data[0]);
            const yearText = extractPlainText(data[2]);
            const statusText = extractPlainText(data[5]);

            if (locationFilter && schoolNameText.indexOf(locationFilter) === -1) {
                return false;
            }

            if (schoolFilter && schoolNameText.indexOf(schoolFilter) === -1) {
                return false;
            }

            if (yearFilter && yearText.indexOf(yearFilter) === -1) {
                return false;
            }

            if (statusFilter && statusText.indexOf(statusFilter) === -1) {
                return false;
            }

            return true;
        }
    );

    /**
     * ========================================
     * DATATABLE INITIALIZATION
     * ========================================
     */
    let table;

    const updatePaginationInfo = function() {
        if (!table) return;
        const info = table.page.info();
        $('#startEntry').text(info.start + 1);
        $('#endEntry').text(info.end);
        $('#totalEntries').text(info.recordsDisplay);
        generatePaginationButtons(info);
    }

    const generatePaginationButtons = function(info) {
        if (!table) return;
        const container = $('#paginationButtons');
        container.empty();

        const totalPages = info.pages;
        const currentPage = info.page;

        // Previous button
        const prevBtn = $('<button class="page-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg></button>');
        if (currentPage === 0 || totalPages === 0) prevBtn.attr('disabled', true);
        prevBtn.on('click', function() {
            table.page('previous').draw('page');
        });
        container.append(prevBtn);

        // Page number buttons
        if (totalPages > 0) {
            for (let i = 0; i < totalPages; i++) {
                if (i === 0 || i === totalPages - 1 || (i >= currentPage - 1 && i <= currentPage + 1)) {
                    const pageBtn = $('<button class="page-btn">' + (i + 1) + '</button>');
                    if (i === currentPage) pageBtn.addClass('active');
                    pageBtn.on('click', function() {
                        table.page(i).draw('page');
                    });
                    container.append(pageBtn);
                } else if (i === currentPage - 2 || i === currentPage + 2) {
                    container.append('<span class="page-ellipsis">...</span>');
                }
            }
        }

        // Next button
        const nextBtn = $('<button class="page-btn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></button>');
        if (currentPage === totalPages - 1 || totalPages === 0) nextBtn.attr('disabled', true);
        nextBtn.on('click', function() {
            table.page('next').draw('page');
        });
        container.append(nextBtn);
    }

    // Initialize DataTable
    table = $('#classTable').DataTable({
        pageLength: 10,
        order: [[0, 'asc'], [1, 'asc']],
        autoWidth: false,
        columnDefs: [
            { orderable: false, targets: [6], className: 'text-center' },
            { className: 'text-center', targets: [4, 6] }
        ],
        drawCallback: function() {
            updatePaginationInfo();
        }
    });

    /**
     * ========================================
     * FILTER EVENT HANDLERS
     * ========================================
     */

    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });

    $('#locationFilter').on('change', function() {
        table.draw();
    });

    $('#schoolFilter').on('change', function() {
        table.draw();
    });

    $('#yearFilter').on('change', function() {
        table.draw();
    });

    $('#statusFilter').on('change', function() {
        table.draw();
    });

    $('#resetFiltersBtn').on('click', function(e) {
        e.preventDefault();
        $('#locationFilter').val('');
        $('#schoolFilter').val('');
        $('#yearFilter').val('');
        $('#statusFilter').val('');
        $('#globalSearch').val('');
        table.search('').draw();
    });

    $('#rowsPerPage').on('change', function() {
        table.page.len(parseInt($(this).val())).draw();
    });

    updatePaginationInfo();
});

/**
 * ========================================
 * EDIT DRAWER FUNCTIONALITY
 * ========================================
 *
 * The three buttons in the Actions column were markup only. Edit opened the
 * drawer with every field blank -- its handler carried a comment saying the
 * data "would typically be fetched from the server" and then opened it
 * anyway -- Update Class closed the drawer and saved nothing, and View and
 * Delete had no handler at all. The server has had edit_class and
 * delete_class the whole time; nothing was wired to them.
 */

function openEditDrawer() {
    $('#drawerOverlay').addClass('active');
    $('#editDrawer').addClass('active');
    $('body').css('overflow', 'hidden');
}

function closeEditDrawer() {
    $('#drawerOverlay').removeClass('active');
    $('#editDrawer').removeClass('active');
    $('body').css('overflow', '');
}

/* A toggle that only flips a CSS class tells the reader one thing and the
   form another. Each switch owns a hidden input; this keeps them equal. */
function setToggle($toggle, $input, on) {
    $toggle.toggleClass('active', !!on);
    $input.val(on ? 'true' : 'false');
}

/* Fill the drawer from the row. Everything comes from data-* attributes the
   template writes, so there is no second request to get out of step with
   what the page is showing. */
function fillDrawerFrom($row) {
    const d = $row.data();

    $('#editClassId').val(d.classId);
    $('#editingClassName').text(d.className || `Std ${d.grade}${d.division}`);
    $('#editGrade').val(String(d.grade));
    $('#editDivision').val(d.division);
    $('#editClassName').val(d.className);
    $('#editClassCode').val(d.classCode);
    $('#editSchool').val(String(d.schoolId));
    /* A class older than the generated range has no option to select,
       and a select falls back to its first option without saying so --
       which would quietly move the class to a different year on save.
       Give it its own option instead. */
    const $year = $('#editAcademicYear');
    if (d.academicYear && !$year.find(`option[value='${d.academicYear}']`).length) {
        $year.append($('<option>', {value: d.academicYear, text: d.academicYear}));
    }
    $year.val(d.academicYear);
    $('#editCoach').val(d.coachId ? String(d.coachId) : '');
    $('#editSessions').val(d.totalSessions);

    setToggle($('#editClassStatus'), $('#editIsActive'), d.isActive === true || d.isActive === 'true');
    setToggle($('#editStudentVisibility'), $('#editStudentVisibilityInput'),
              d.studentVisibility === true || d.studentVisibility === 'true');
    setToggle($('#editParentVisibility'), $('#editParentVisibilityInput'),
              d.parentVisibility === true || d.parentVisibility === 'true');

    $('#editClassForm').attr('action', `/super-admin/class/${d.classId}/edit/`);
}

/* View is the same drawer with nothing to press. There is no read-only class
   page on the server, and showing the details is what the eye icon promises. */
function setReadOnly(readOnly) {
    const $form = $('#editClassForm');
    $form.find('select, input, textarea').prop('disabled', readOnly);
    $form.find('.drawer-toggle-switch').css('pointer-events', readOnly ? 'none' : '');
    $('#updateClassBtn').toggle(!readOnly);
    $('#cancelDrawerBtn').text(readOnly ? 'Close' : 'Cancel');
    $('#editDrawer').find('.drawer-header-content h2')
        .text(readOnly ? 'Class Details' : 'Edit Class');
}

$(document).ready(function() {
    $('#drawerOverlay').on('click', function() {
        closeEditDrawer();
    });

    $('#closeDrawerBtn').on('click', function() {
        closeEditDrawer();
    });

    $('#cancelDrawerBtn').on('click', function() {
        closeEditDrawer();
    });

    $(document).on('keydown', function(e) {
        if (e.key === 'Escape' && $('#editDrawer').hasClass('active')) {
            closeEditDrawer();
        }
    });

    $('.drawer-toggle-switch').on('click', function() {
        const $toggle = $(this);
        const $input = $('#' + $toggle.attr('id') + 'Input');
        const $target = $input.length ? $input : $('#editIsActive');
        setToggle($toggle, $target, !$toggle.hasClass('active'));
    });

    /* The class name follows grade and division, as the field's own hint
       says it does. It was read-only and never updated. */
    $('#editGrade, #editDivision').on('input change', function() {
        const grade = $('#editGrade').val();
        const division = ($('#editDivision').val() || '').toUpperCase();
        $('#editDivision').val(division);
        if (grade && division) {
            $('#editClassName').val(`Std ${grade}${division}`);
        }
    });

    $(document).on('click', '.edit-class-btn', function() {
        setReadOnly(false);
        fillDrawerFrom($(this).closest('tr'));
        openEditDrawer();
    });

    $(document).on('click', '.view-class-btn', function() {
        fillDrawerFrom($(this).closest('tr'));
        setReadOnly(true);
        openEditDrawer();
    });

    $('#updateClassBtn').on('click', function() {
        const $form = $('#editClassForm');
        if (!$form.attr('action')) return;          // nothing was opened
        if (!$('#editGrade').val() || !$('#editDivision').val()) {
            alert('Grade and Division are both required.');
            return;
        }
        $form.trigger('submit');
    });

    $(document).on('click', '.delete-class-btn', function() {
        const $btn = $(this);
        const name = $btn.data('class-name') || 'this class';
        if (!window.confirm(
                `Delete ${name}? Its attendance and sessions go with it. ` +
                `This cannot be undone.`)) {
            return;
        }
        $('#deleteClassForm')
            .attr('action', $btn.data('delete-url'))
            .trigger('submit');
    });
});

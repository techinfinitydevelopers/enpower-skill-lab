/*
 * Select rows on a list and delete them together.
 *
 *   initBulkDelete({ key: 'students', table: '#studentTable' });
 *
 * Selection is held in a Set of ids, not in the checkboxes, because these
 * tables are DataTables -- rows on other pages are not in the DOM, so a
 * checkbox that scrolled off the page would take its state with it. The Set
 * survives paging, searching and sorting; the checkboxes are re-checked from
 * it on every redraw.
 *
 * Nothing is deleted without the preview first. It asks the server what the
 * selection takes with it and shows the answer, because deleting a school
 * also deletes its classes, its admins, its coaches and every student in it,
 * and no screen said so before.
 */
(function () {
  'use strict';

  function csrf() {
    var name = 'csrftoken=';
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (part.indexOf(name) === 0) return decodeURIComponent(part.slice(name.length));
    }
    var field = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return field ? field.value : '';
  }

  function post(url, ids, signal) {
    var body = new FormData();
    ids.forEach(function (id) { body.append('ids', id); });
    return fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' },
      body: body,
      signal: signal
    }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  window.initBulkDelete = function (cfg) {
    var table = document.querySelector(cfg.table);
    if (!table) return;

    var selected = new Set();
    var busy = false;

    // ── the bar that appears once something is ticked ──────────────────
    var bar = document.createElement('div');
    bar.className = 'bd-bar';
    bar.innerHTML =
      '<span class="bd-count"></span>' +
      '<button type="button" class="bd-clear">Clear selection</button>' +
      '<button type="button" class="bd-delete">' +
      '<span class="material-symbols-outlined">delete</span>Delete selected</button>';
    document.body.appendChild(bar);

    var countEl = bar.querySelector('.bd-count');
    var deleteBtn = bar.querySelector('.bd-delete');

    // ── the confirmation ───────────────────────────────────────────────
    var modal = document.createElement('div');
    modal.className = 'bd-modal';
    modal.innerHTML =
      '<div class="bd-dialog" role="dialog" aria-modal="true" aria-labelledby="bdTitle">' +
      '  <h3 id="bdTitle">Delete <span class="bd-what"></span>?</h3>' +
      '  <div class="bd-body"></div>' +
      '  <div class="bd-actions">' +
      '    <button type="button" class="bd-cancel">Cancel</button>' +
      '    <button type="button" class="bd-confirm">Delete</button>' +
      '  </div>' +
      '</div>';
    document.body.appendChild(modal);

    var what = modal.querySelector('.bd-what');
    var body = modal.querySelector('.bd-body');
    var confirmBtn = modal.querySelector('.bd-confirm');

    function closeModal() {
      if (busy) return;
      modal.classList.remove('bd-open');
    }
    modal.querySelector('.bd-cancel').addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('bd-open')) closeModal();
    });

    // ── selection ──────────────────────────────────────────────────────
    function paint() {
      var n = selected.size;
      bar.classList.toggle('bd-visible', n > 0);
      countEl.textContent = n + (n === 1 ? ' row selected' : ' rows selected');

      table.querySelectorAll('.bd-row').forEach(function (box) {
        box.checked = selected.has(box.dataset.id);
        box.closest('tr').classList.toggle('bd-picked', box.checked);
      });

      // The header box reflects only what is on screen: on a paged table
      // "all" can only sensibly mean the rows you can see.
      var onPage = Array.prototype.slice.call(table.querySelectorAll('.bd-row'));
      var head = table.querySelector('.bd-all');
      if (head) {
        var ticked = onPage.filter(function (b) { return b.checked; }).length;
        head.checked = onPage.length > 0 && ticked === onPage.length;
        head.indeterminate = ticked > 0 && ticked < onPage.length;
      }
    }

    table.addEventListener('change', function (e) {
      var box = e.target;
      if (box.classList.contains('bd-row')) {
        if (box.checked) selected.add(box.dataset.id);
        else selected.delete(box.dataset.id);
        paint();
      } else if (box.classList.contains('bd-all')) {
        table.querySelectorAll('.bd-row').forEach(function (row) {
          if (box.checked) selected.add(row.dataset.id);
          else selected.delete(row.dataset.id);
        });
        paint();
      }
    });

    // A click on the checkbox cell should not open the row or sort the column.
    table.addEventListener('click', function (e) {
      if (e.target.closest('.bd-cell')) e.stopPropagation();
    }, true);

    bar.querySelector('.bd-clear').addEventListener('click', function () {
      selected.clear();
      paint();
    });

    // DataTables detaches rows when paging; re-tick from the Set afterwards.
    if (window.jQuery && jQuery.fn.dataTable) {
      jQuery(table).on('draw.dt', paint);
    }

    // ── preview, then delete ───────────────────────────────────────────
    deleteBtn.addEventListener('click', function () {
      if (!selected.size) return;
      var ids = Array.from(selected);
      what.textContent = ids.length + ' row' + (ids.length === 1 ? '' : 's');
      body.innerHTML = '<p class="bd-loading">Checking what this removes...</p>';
      confirmBtn.disabled = true;
      modal.classList.add('bd-open');

      post('/bulk-delete/' + cfg.key + '/preview/', ids)
        .then(function (data) {
          what.textContent = data.count + ' ' + data.label;

          var html = '';
          if (data.names && data.names.length) {
            html += '<ul class="bd-names">';
            data.names.forEach(function (n) {
              html += '<li>' + escapeHtml(n) + '</li>';
            });
            if (data.more) html += '<li class="bd-more">and ' + data.more + ' more</li>';
            html += '</ul>';
          }

          if (data.impact && data.impact.length) {
            html += '<p class="bd-warn-head">This also removes permanently:</p>' +
                    '<ul class="bd-impact">';
            data.impact.forEach(function (row) {
              var noun = row.what + (row.count === 1 ? '' : 's');
              html += '<li><b>' + row.count + '</b> ' + escapeHtml(noun) + '</li>';
            });
            html += '</ul>';
          }
          html += '<p class="bd-final">This cannot be undone.</p>';
          body.innerHTML = html;
          confirmBtn.disabled = data.count === 0;
          confirmBtn.textContent = 'Delete ' + data.count + ' ' + data.label;
        })
        .catch(function (err) {
          body.innerHTML = '<p class="bd-error">Could not check the selection: ' +
            escapeHtml(err.message) + '</p>';
        });
    });

    confirmBtn.addEventListener('click', function () {
      var ids = Array.from(selected);
      if (!ids.length || busy) return;
      busy = true;
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Deleting...';

      post('/bulk-delete/' + cfg.key + '/', ids)
        .then(function (data) {
          busy = false;
          if (data.failed) {
            var html = '<p class="bd-result">' + escapeHtml(data.message) + '</p>' +
                       '<ul class="bd-failures">';
            data.failures.forEach(function (f) {
              html += '<li><b>' + escapeHtml(f.name) + '</b> - ' +
                      escapeHtml(f.reason) + '</li>';
            });
            html += '</ul>';
            body.innerHTML = html;
            confirmBtn.textContent = 'Reload the list';
            confirmBtn.disabled = false;
            confirmBtn.onclick = function () { window.location.reload(); };
            return;
          }
          window.location.reload();
        })
        .catch(function (err) {
          busy = false;
          body.innerHTML = '<p class="bd-error">The delete did not go through: ' +
            escapeHtml(err.message) + '</p>';
          confirmBtn.textContent = 'Close';
          confirmBtn.disabled = false;
          confirmBtn.onclick = closeModal;
        });
    });

    paint();
  };
})();

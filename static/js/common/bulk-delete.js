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
 * The header checkbox ticks the page you are looking at. Selecting past it
 * is a separate, deliberate click ("Select all 1290 rows"), because "delete
 * everything on this list" should not be one checkbox away from "delete
 * these five". It respects the search box: after a search it means the rows
 * the search found, not the whole list.
 *
 * Ids go to the server as a JSON body rather than one form field each --
 * Django's DATA_UPLOAD_MAX_NUMBER_FIELDS is 1000, so a select-all on a big
 * list would otherwise be rejected outright. The delete is sent in batches
 * for the same class of reason: the worker timeout is 60s, and one request
 * carrying every row would be killed part-way through.
 *
 * Nothing is deleted without the preview first. It asks the server what the
 * selection takes with it and shows the answer, because deleting a school
 * also deletes its classes, its admins, its coaches and every student in it,
 * and no screen said so before.
 */
(function () {
  'use strict';

  var BATCH = 300;

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

  function post(url, ids) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf(),
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ ids: ids })
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

  function plural(n, word) {
    return n + ' ' + word + (n === 1 ? '' : 's');
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
      '<button type="button" class="bd-all-pages"></button>' +
      '<button type="button" class="bd-clear">Clear selection</button>' +
      '<button type="button" class="bd-delete">' +
      '<span class="material-symbols-outlined">delete</span>Delete selected</button>';
    document.body.appendChild(bar);

    var countEl = bar.querySelector('.bd-count');
    var allPagesBtn = bar.querySelector('.bd-all-pages');
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
    var cancelBtn = modal.querySelector('.bd-cancel');
    var confirmBtn = modal.querySelector('.bd-confirm');

    function closeModal() {
      if (busy) return;
      modal.classList.remove('bd-open');
    }
    cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('bd-open')) closeModal();
    });

    // ── every row, including the pages you cannot see ──────────────────
    function api() {
      if (!window.jQuery || !jQuery.fn.dataTable) return null;
      return jQuery.fn.dataTable.isDataTable(table) ? jQuery(table).DataTable() : null;
    }

    function allIds() {
      // These tables paginate in the browser, so DataTables holds every row
      // even when only one page is in the DOM. {search: 'applied'} is what
      // keeps a select-all honest: after a search it means the rows the
      // search found, not the whole list.
      var dt = api();
      var boxes;
      if (dt) {
        boxes = dt.rows({ search: 'applied' }).nodes().toArray()
          .map(function (tr) { return tr.querySelector('.bd-row'); });
      } else {
        boxes = Array.prototype.slice.call(table.querySelectorAll('.bd-row'));
      }
      return boxes.filter(Boolean).map(function (box) { return box.dataset.id; });
    }

    // ── selection ──────────────────────────────────────────────────────
    function paint() {
      var n = selected.size;
      var every = allIds();
      var onPage = Array.prototype.slice.call(table.querySelectorAll('.bd-row'));
      var beyondThisPage = every.length > onPage.length;

      bar.classList.toggle('bd-visible', n > 0);
      countEl.textContent = (n === every.length && beyondThisPage)
        ? 'All ' + plural(n, 'row') + ' selected'
        : plural(n, 'row') + ' selected';

      var missing = every.filter(function (id) { return !selected.has(id); }).length;
      if (n > 0 && missing > 0 && beyondThisPage) {
        allPagesBtn.style.display = '';
        allPagesBtn.textContent = 'Select all ' + plural(every.length, 'row');
      } else {
        allPagesBtn.style.display = 'none';
      }

      onPage.forEach(function (box) {
        box.checked = selected.has(box.dataset.id);
        box.closest('tr').classList.toggle('bd-picked', box.checked);
      });

      // The header box reflects only what is on screen: on a paged table it
      // is the page's checkbox, and selecting past it is the button above.
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

    allPagesBtn.addEventListener('click', function () {
      allIds().forEach(function (id) { selected.add(id); });
      paint();
    });

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
      what.textContent = plural(ids.length, 'row');
      body.innerHTML = '<p class="bd-loading">Checking what this removes...</p>';
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Delete';
      confirmBtn.onclick = null;
      cancelBtn.disabled = false;
      modal.classList.add('bd-open');

      post('/bulk-delete/' + cfg.key + '/preview/', ids)
        .then(function (data) {
          what.textContent = data.count + ' ' + data.label;

          var html = '';
          if (data.names && data.names.length) {
            html += '<ul class="bd-names">';
            data.names.forEach(function (name) {
              html += '<li>' + escapeHtml(name) + '</li>';
            });
            if (data.more) html += '<li class="bd-more">and ' + data.more + ' more</li>';
            html += '</ul>';
          }

          if (data.impact && data.impact.length) {
            html += '<p class="bd-warn-head">This also removes permanently:</p>' +
                    '<ul class="bd-impact">';
            data.impact.forEach(function (row) {
              html += '<li><b>' + row.count + '</b> ' +
                      escapeHtml(row.what + (row.count === 1 ? '' : 's')) + '</li>';
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

    function finish(deleted, failures) {
      busy = false;
      cancelBtn.disabled = false;
      if (!failures.length) {
        window.location.reload();
        return;
      }
      var html = '<p class="bd-result">' + plural(deleted, 'row') +
                 ' deleted, ' + failures.length + ' could not be.</p>' +
                 '<ul class="bd-failures">';
      failures.slice(0, 20).forEach(function (f) {
        html += '<li><b>' + escapeHtml(f.name) + '</b> - ' +
                escapeHtml(f.reason) + '</li>';
      });
      if (failures.length > 20) {
        html += '<li class="bd-more">and ' + (failures.length - 20) + ' more</li>';
      }
      html += '</ul>';
      body.innerHTML = html;
      confirmBtn.textContent = 'Reload the list';
      confirmBtn.disabled = false;
      confirmBtn.onclick = function () { window.location.reload(); };
    }

    confirmBtn.addEventListener('click', function () {
      if (busy || confirmBtn.onclick) return;
      var ids = Array.from(selected);
      if (!ids.length) return;

      busy = true;
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;

      // Batched, because the worker is killed at 60 seconds and a selection
      // of a few thousand rows will not finish inside one request. Each
      // batch is its own request, so progress is real rather than animated.
      var batches = [];
      for (var i = 0; i < ids.length; i += BATCH) batches.push(ids.slice(i, i + BATCH));

      var deleted = 0;
      var failures = [];
      var done = 0;

      function progress() {
        var pct = Math.round((done / ids.length) * 100);
        confirmBtn.textContent = 'Deleting... ' + pct + '%';
        body.innerHTML =
          '<p class="bd-result">Deleted ' + done + ' of ' + ids.length + '.</p>' +
          '<div class="bd-progress"><span style="width:' + pct + '%"></span></div>' +
          '<p class="bd-final">Do not close this page.</p>';
      }
      progress();

      batches.reduce(function (chain, batch) {
        return chain.then(function () {
          return post('/bulk-delete/' + cfg.key + '/', batch).then(function (data) {
            deleted += data.deleted;
            failures = failures.concat(data.failures || []);
            done += batch.length;
            progress();
          });
        });
      }, Promise.resolve())
        .then(function () { finish(deleted, failures); })
        .catch(function (err) {
          // Batches before this one are already gone; say so rather than
          // implying the whole thing rolled back.
          busy = false;
          cancelBtn.disabled = false;
          body.innerHTML =
            '<p class="bd-error">The delete stopped part-way: ' +
            escapeHtml(err.message) + '</p>' +
            '<p class="bd-result">' + plural(deleted, 'row') +
            ' were already deleted. The rest are still here.</p>';
          confirmBtn.textContent = 'Reload the list';
          confirmBtn.disabled = false;
          confirmBtn.onclick = function () { window.location.reload(); };
        });
    });

    paint();
  };
})();

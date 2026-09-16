/**
 * Bulk import: real progress, real row numbers, and a way to stop.
 *
 * What this replaces, and why:
 *
 *   The progress bar was a timer. It crept to 85% on random increments while
 *   one long POST was in flight, and the row count came from splitting the
 *   file on newlines -- a meaningless number for a binary .xlsx. On a
 *   1290-row upload the figures on screen had nothing to do with the import.
 *
 *   Failures only appeared at the end, and the row number was the position in
 *   the list rather than the row in the spreadsheet. "Row 1" meant row 3 of
 *   the file, so the record could not be found.
 *
 *   There was no way to stop a run once it had started.
 *
 * The server now streams one JSON object per row as it processes it, so the
 * numbers here are counted rather than guessed, failures are listed the moment
 * they happen, and Cancel abandons the response, which stops the server's loop.
 *
 * Cancelling does not undo what has already been written: each row commits as
 * it goes, which is what makes streaming possible at all. The summary says how
 * many were imported before stopping.
 *
 * Both the Super Admin and Coordinator modals call in here. They keep their own
 * markup and hand over their own elements, because their element ids differ --
 * the Coordinator's are suffixed per role so one page can hold a modal per
 * sheet.
 */
(function () {
  'use strict';

  function initBulkImport(cfg) {
    var els = cfg.els;
    var controller = null;      // live only while an import is running
    var cancelled = false;

    function show(el) { if (el) { el.classList.remove('d-none'); } }
    function hide(el) { if (el) { el.classList.add('d-none'); } }
    function setText(el, value) { if (el) { el.textContent = value; } }

    function escapeHtml(value) {
      var d = document.createElement('div');
      d.textContent = value == null ? '' : value;
      return d.innerHTML;
    }

    function resetProgress(total) {
      cancelled = false;
      hide(els.uploadSection);
      show(els.progressSection);
      show(els.cancelBtn);
      show(els.spinner);
      hide(els.cancelNotice);
      if (els.progressBar) {
        els.progressBar.style.width = '0%';
        els.progressBar.style.background = 'linear-gradient(90deg, #4F46E5, #7C3AED)';
      }
      setText(els.progressText, 'Importing...');
      if (els.progressText) { els.progressText.style.color = ''; }
      setText(els.progressSub, 'You can cancel at any time.');
      setText(els.progressPercent, '0%');
      setText(els.processedCount, '0 / ' + total + ' processed');
      if (els.liveFailures) { els.liveFailures.innerHTML = ''; }
      hide(els.liveFailuresBox);
    }

    function paint(done, total, success, failed) {
      var pct = total ? Math.round((done / total) * 100) : 0;
      if (els.progressBar) { els.progressBar.style.width = pct + '%'; }
      setText(els.progressPercent, pct + '%');
      setText(els.processedCount, done + ' / ' + total + ' processed');
      setText(els.progressSub, success + ' imported, ' + failed + ' failed so far.');
    }

    // Shown while the import is still running, so a bad sheet can be stopped
    // early instead of after every row has been attempted.
    function addLiveFailure(event) {
      if (!els.liveFailures) { return; }
      show(els.liveFailuresBox);
      var line = document.createElement('div');
      line.className = 'd-flex gap-2 py-1';
      line.style.fontSize = '0.8rem';
      line.innerHTML =
        '<span style="color:#DC2626;font-weight:600;white-space:nowrap;">Row ' +
        escapeHtml(event.row) + '</span>' +
        '<span style="font-weight:500;">' + escapeHtml(event.name) + '</span>' +
        '<span style="color:#DC2626;">' + escapeHtml(event.reason) + '</span>';
      els.liveFailures.appendChild(line);
      els.liveFailures.scrollTop = els.liveFailures.scrollHeight;
    }

    // A long failure list is unreadable inside a modal; this hands the admin
    // something they can open beside the sheet they uploaded.
    function downloadFailures(failures) {
      var lines = ['Row,Name,Reason'];
      failures.forEach(function (f) {
        lines.push([f.row, f.name || '', f.reason || ''].map(function (v) {
          return '"' + String(v).replace(/"/g, '""') + '"';
        }).join(','));
      });
      var blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'import-failures.csv';
      a.click();
      URL.revokeObjectURL(a.href);
    }

    function showResults(summary, failures, wasCancelled) {
      hide(els.progressSection);
      hide(els.cancelBtn);
      show(els.resultsSection);

      setText(els.successCount, summary.success);
      setText(els.failCount, summary.failed);
      setText(els.totalCount, summary.total);

      if (wasCancelled && els.cancelNotice) {
        show(els.cancelNotice);
        setText(els.cancelNotice,
          'Cancelled after ' + (summary.success + summary.failed) + ' of ' +
          summary.total + ' rows. The ' + summary.success +
          ' already imported have been kept.');
      }

      if (failures.length) {
        show(els.failedSection);
        hide(els.allSuccessMsg);
        if (els.failedBody) {
          els.failedBody.innerHTML = '';
          failures.forEach(function (f) {
            var tr = document.createElement('tr');
            tr.innerHTML =
              '<td style="padding:0.5rem;border-color:#F3F4F6;white-space:nowrap;">Row ' +
              escapeHtml(f.row) + '</td>' +
              '<td style="padding:0.5rem;border-color:#F3F4F6;font-weight:500;">' +
              escapeHtml(f.name) + '</td>' +
              '<td style="padding:0.5rem;border-color:#F3F4F6;color:#DC2626;">' +
              escapeHtml(f.reason) + '</td>';
            els.failedBody.appendChild(tr);
          });
        }
        if (els.downloadFailures) {
          show(els.downloadFailures);
          els.downloadFailures.onclick = function () { downloadFailures(failures); };
        }
      } else {
        hide(els.failedSection);
        hide(els.downloadFailures);
        show(els.allSuccessMsg);
      }
      if (cfg.onDone) { cfg.onDone(summary); }
    }

    function fail(message) {
      hide(els.spinner);
      hide(els.cancelBtn);
      setText(els.progressText, 'Import failed');
      if (els.progressText) { els.progressText.style.color = '#DC2626'; }
      setText(els.progressSub, message);
      if (els.progressBar) {
        els.progressBar.style.width = '100%';
        els.progressBar.style.background = '#DC2626';
      }
    }

    function consume(reader) {
      var decoder = new TextDecoder();
      var buffer = '';
      var total = 0, done = 0, success = 0, failed = 0;
      var failures = [];

      function handle(event) {
        if (event.type === 'start') {
          total = event.total;
          setText(els.processedCount, '0 / ' + total + ' processed');
          setText(els.progressText, 'Importing ' + total + ' rows...');
          return;
        }
        if (event.type === 'row') {
          done += 1;
          success = event.success;
          failed = event.failed;
          paint(done, total, success, failed);
          if (event.status === 'failed') {
            failures.push(event);
            addLiveFailure(event);
          }
          return;
        }
        if (event.type === 'done') {
          setText(els.progressText, 'Import complete');
          hide(els.spinner);
          setTimeout(function () { showResults(event, failures, false); }, 300);
        }
      }

      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) {
            // The stream ended without a summary: that is a cancel, or the
            // connection dropping. Report what actually got through.
            if (cancelled) {
              showResults({ total: total, success: success, failed: failed },
                failures, true);
            }
            return;
          }
          buffer += decoder.decode(chunk.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop();                 // keep the partial line
          lines.forEach(function (line) {
            if (!line.trim()) { return; }
            try { handle(JSON.parse(line)); } catch (e) { /* partial JSON */ }
          });
          return pump();
        });
      }

      return pump();
    }

    function start(file) {
      if (!file) { return; }
      resetProgress('?');

      var form = new FormData();
      form.append('csv_file', file);

      controller = ('AbortController' in window) ? new AbortController() : null;

      fetch(cfg.streamUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': cfg.csrfToken },
        body: form,
        signal: controller ? controller.signal : undefined
      }).then(function (res) {
        // A rejected upload answers with JSON, not a stream.
        var type = res.headers.get('Content-Type') || '';
        if (type.indexOf('ndjson') === -1) {
          return res.json().then(function (data) {
            fail(data.error || ('HTTP ' + res.status));
          });
        }
        if (!res.body || !res.body.getReader) {
          fail('This browser cannot show live progress. Please use a current browser.');
          return;
        }
        return consume(res.body.getReader());
      }).catch(function (err) {
        if (err && err.name === 'AbortError') { return; }   // handled in cancel()
        fail(err && err.message ? err.message : 'Network error');
      });
    }

    function cancel() {
      if (!controller) { return; }
      cancelled = true;
      controller.abort();
      hide(els.spinner);
      hide(els.cancelBtn);
      setText(els.progressText, 'Cancelling...');
    }

    if (els.cancelBtn) { els.cancelBtn.addEventListener('click', cancel); }

    return { start: start, cancel: cancel };
  }

  window.initBulkImport = initBulkImport;
})();

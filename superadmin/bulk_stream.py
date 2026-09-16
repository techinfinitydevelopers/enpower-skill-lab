"""
Shared parsing and streaming for bulk import.

Three problems this exists to fix:

  Row numbers were wrong. A failure reported "row 1", but the first data row of
  the Excel template is spreadsheet row 3 (row 1 is the display headers, row 2
  the field names). On a 1290-row upload that is the difference between finding
  the bad record and not.

  Progress was invented. The modal ran a timer that crept to 85% on random
  increments while one long POST was in flight, and counted rows by splitting
  the file on newlines -- which produces a meaningless number for a binary
  .xlsx. `stream_rows` reports what has actually been processed.

  There was no way to stop. A stream can be abandoned: the client drops the
  connection and the generator stops on its next yield.

superadmin and coordinator had two copies of the parse-and-process loop and two
copies of the modal. Both now call in here.
"""

import csv
import io
import json


def parse_upload(csv_file, role):
    """Read an uploaded file into (rows, row_numbers, error).

    `row_numbers` are the numbers the user sees in their spreadsheet, so a
    failure can be pointed at the actual line. Blank rows are skipped, which is
    exactly why the number cannot be derived from the position in the list.
    """
    from .bulk_import import EXCEL_CONFIG, SAMPLE_DATA, _cell_text

    if role not in SAMPLE_DATA:
        return None, None, 'Invalid role'

    if not csv_file:
        return None, None, 'No file uploaded'

    name = csv_file.name.lower()
    if not (name.endswith('.xlsx') or name.endswith('.csv')):
        return None, None, 'Please upload a CSV or Excel (.xlsx) file'

    rows, numbers = [], []
    try:
        if name.endswith('.xlsx'):
            from openpyxl import load_workbook
            ws = load_workbook(csv_file, data_only=True).active
            # Row 1 is the display headers, row 2 the field names.
            fields = [str(cell.value or '').strip() for cell in ws[2]]
            for offset, row in enumerate(ws.iter_rows(min_row=3, values_only=True)):
                if all(v is None or str(v).strip() == '' for v in row):
                    continue
                rows.append({
                    field: _cell_text(row[idx] if idx < len(row) else None)
                    for idx, field in enumerate(fields) if field
                })
                numbers.append(offset + 3)
        else:
            decoded = csv_file.read().decode('utf-8-sig')
            for offset, row in enumerate(csv.DictReader(io.StringIO(decoded))):
                if all(not str(v or '').strip() for v in row.values()):
                    continue
                rows.append(row)
                numbers.append(offset + 2)      # row 1 is the header
    except Exception as e:
        return None, None, f'Error reading file: {e}'

    if not rows:
        return None, None, 'File is empty or has no data rows'

    missing = set(EXCEL_CONFIG[role]['required_fields']) - set(rows[0].keys())
    if missing:
        return None, None, f'Missing required columns: {", ".join(sorted(missing))}'

    return rows, numbers, None


def stream_rows(rows, numbers, role, user):
    """Yield one NDJSON line per row as it is processed, then a summary.

    Each line is a complete JSON object followed by a newline, so the browser
    can act on a row the moment it arrives instead of waiting for the whole
    import. Abandoning the response stops this generator.
    """
    from .bulk_import import ROLE_PROCESSORS, _get_display_name

    processor = ROLE_PROCESSORS[role]
    success = failed = 0

    yield json.dumps({'type': 'start', 'total': len(rows)}) + '\n'

    for row, number in zip(rows, numbers):
        row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        name = _get_display_name(row, role)
        try:
            processor(row, user)
            success += 1
            record = {'type': 'row', 'row': number, 'name': name, 'status': 'success'}
        except Exception as e:
            failed += 1
            # str(e) on its own is often bare ("full_name is required"), so the
            # row number and name travel with it.
            record = {'type': 'row', 'row': number, 'name': name,
                      'status': 'failed', 'reason': str(e) or e.__class__.__name__}
        record['success'] = success
        record['failed'] = failed
        yield json.dumps(record) + '\n'

    yield json.dumps({'type': 'done', 'total': len(rows),
                      'success': success, 'failed': failed}) + '\n'


def streaming_response(generator):
    """Wrap a generator so proxies hand it through unbuffered."""
    from django.http import StreamingHttpResponse

    response = StreamingHttpResponse(generator, content_type='application/x-ndjson')
    # Without these a proxy may hold the whole body back, which would put the
    # progress bar right back where it started.
    response['Cache-Control'] = 'no-cache, no-store'
    response['X-Accel-Buffering'] = 'no'
    return response

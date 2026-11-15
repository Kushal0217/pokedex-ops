/**
 * Minimal RFC 4180 CSV parser: quoted fields, escaped quotes (""), commas and
 * line breaks inside quotes, CRLF or LF, optional UTF-8 byte-order mark.
 * Throws on an unterminated quoted field. Returns rows of strings.
 */
export function parseCsv(text) {
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  let quotedField = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"' && field === '' && !quotedField) {
      inQuotes = true;
      quotedField = true;
    } else if (ch === ',') {
      row.push(field);
      field = '';
      quotedField = false;
    } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i += 1;
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
      quotedField = false;
    } else {
      field += ch;
    }
  }
  if (inQuotes) throw new Error('CSV is malformed: a quoted field is never closed');
  if (field !== '' || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  // Drop completely blank lines.
  return rows.filter((r) => r.some((cell) => cell.trim() !== ''));
}

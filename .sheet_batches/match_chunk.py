#!/usr/bin/env python3
"""Match a read_range CSV (or MCP JSON dump) to backfill values. Writes chunk JSON."""
import json, csv, io, sys
from datetime import date, timedelta
from pathlib import Path

LOOKUP = json.load(open('/Users/vivienneyang/Projects/kotc-marketing/.sheet_batches/backfill_lookup.json'))
DEFAULT = ["", 0, 0, 0, 0, 0, 0, ""]
EPOCH = date(1899, 12, 30)

def serial_to_iso(serial):
    return (EPOCH + timedelta(days=int(float(serial)))).isoformat()

def is_45713(c):
    try:
        return float(str(c).strip()) == 45713.0
    except Exception:
        return str(c).strip() == '45713'

def lookup_cols(d, partner, campaign, platform):
    key = f"{d}|{partner}|{campaign}|{platform}"
    if key in LOOKUP:
        return LOOKUP[key], True
    if is_45713(campaign):
        key2 = f"{d}|{partner}|Feb-25|{platform}"
        if key2 in LOOKUP:
            return LOOKUP[key2], True
    return list(DEFAULT), False

def parse_content(content):
    return list(csv.reader(io.StringIO(content)))

def process(content, start_row):
    rows = parse_content(content)
    values, matched, missed, miss_samples = [], 0, 0, []
    for i, row in enumerate(rows):
        while len(row) < 4:
            row.append('')
        serial, partner, campaign, platform = row[0], row[1], row[2], row[3]
        try:
            d = serial_to_iso(serial)
        except Exception:
            d = str(serial)
            cols, ok = list(DEFAULT), False
        else:
            cols, ok = lookup_cols(d, partner, campaign, platform)
        if ok:
            matched += 1
        else:
            missed += 1
            if len(miss_samples) < 20:
                miss_samples.append({
                    'row': start_row + i,
                    'date': d,
                    'ad_partner': partner,
                    'campaign': campaign,
                    'platform': platform,
                })
        values.append(cols)
    end_row = start_row + len(rows) - 1
    return {
        'start': start_row,
        'end': end_row,
        'matched': matched,
        'missed': missed,
        'miss_samples': miss_samples,
        'values': values,
    }

if __name__ == '__main__':
    # args: mcp_json_path start_row out_path
    mcp_path, start_row, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    raw = json.loads(Path(mcp_path).read_text())
    content = raw['ranges'][0]['content']
    result = process(content, start_row)
    with open(out_path, 'w') as f:
        json.dump(result, f)
    print(json.dumps({k: result[k] for k in ('start','end','matched','missed')}))
    print('miss_samples', json.dumps(result['miss_samples'][:5]))

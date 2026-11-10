"""
Rebuild data.json from raw org62 SOQL query result files.
Run with: python -I rebuild_data.py <team1_file> <team2_file>
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

T1_FILE = sys.argv[1] if len(sys.argv) > 1 else None
T2_FILE = sys.argv[2] if len(sys.argv) > 2 else None
DATA_FILE = r'C:\Users\tshumway\capacity-dashboard\data.json'

TEAM1_META = {
    '0053y00000G0dOfAAJ': ('Tom Shumway',      'Senior Director, Business Strategy - Solutions', 'Tom Shumway'),
    '0053y00000GhmHMAAZ': ('Anita Sakhuja',    'Services Sales Solutions Director',              'Tom Shumway'),
    '0053y00000GekI9AAJ': ('Bryan Whyte',       'Engagement Senior Director',                    'Tom Shumway'),
    '00530000009NOv6AAG': ('Dan Nufer',         'Services Sales Solutions Sr. Director',          'Tom Shumway'),
    '0053y00000FUv9aAAD': ('David Flickinger',  'Services Sales Solutions Director',              'Tom Shumway'),
    '00530000009MZ2eAAG': ('Gagan Rastogi',     'Services Sales Solutions Director',              'Tom Shumway'),
    '0053y00000GEodCAAT': ('Kyle Hoffman',      'Services Sales Solutions Sr. Director',          'Tom Shumway'),
    '0053y00000GoyRXAAZ': ('Melissa Romero',    'Services Sales Solutions Director',              'Tom Shumway'),
    '0053y00000FUnViAAL': ('Prakash Alluri',    'Services Sales Solutions Sr. Director',          'Tom Shumway'),
    '0053y00000GZZlRAAX': ('Ravi Thenappan',    'Services Sales Solutions Director',              'Tom Shumway'),
}
TEAM2_META = {
    '0053y00000GBiiOAAT': ('Anita Chow',      'Senior Director, Services Sales Solutions',         'Anita Chow'),
    '00530000007QtfcAAC': ('Anurodh Agarwal', 'Services Sales Solutions Architect Sr. Director',   'Anita Chow'),
    '0050M00000C1TERQA3': ('Chris Petty',     'Services Sales Solutions Director',                 'Anita Chow'),
    '00530000007Pw2HAAS': ('Jason Ames',      'Services Sales Solutions Senior Director',          'Anita Chow'),
    '0053y00000Gshp1AAB': ('Marc Fischer',    'Services Sales Solutions Senior Director',          'Anita Chow'),
    '0053y00000G8xAZAAZ': ('Melissa Dunn',    'Services Sales Solutions Senior Director',          'Anita Chow'),
    '005ed000002EIFFAA4': ('Murali Sankaran', 'Services Sales Solutions Director',                 'Anita Chow'),
    '0050M00000ATZYOQA5': ('Noah Flower',     'Business Strategy Senior Director - Solutions',     'Anita Chow'),
    '0053y00000Bz6JVAAZ': ('Royall Du',       'Services Sales Solutions Director',                 'Anita Chow'),
    '0053y00000FyYJEAA3': ('Vamsi Velampati', 'Services Sales Solutions Director',                 'Anita Chow'),
}
ALL_META = {**TEAM1_META, **TEAM2_META}

INACTIVE = re.compile(r'booked|06|lost|dead', re.IGNORECASE)
ARI_RE   = re.compile(r'\bARI\b')
CLOSED_STATUSES = {
    'Closed - Duplicate', 'Closed - No Response',
    'Closed - Not Qualified', 'Closed - Resolved',
    'Not Qualified',
}

def is_closed(status):
    s = status or ''
    return s in CLOSED_STATUSES or s.startswith('Closed')

MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FY_Q = {2:'Q1',3:'Q1',4:'Q1',5:'Q2',6:'Q2',7:'Q2',
        8:'Q3',9:'Q3',10:'Q3',11:'Q4',12:'Q4',1:'Q4'}


def get_fy(ds):
    if not ds:
        return None
    parts = ds.split('-')
    m, y = int(parts[1]), int(parts[0])
    fy = y + 1 if m >= 2 else y
    return 'FY' + str(fy)[-2:]


def empty_stats():
    return {
        'activeDSRs': 0, 'estimatedHours': 0.0, 'spentHours': 0.0,
        'pipelineValue': 0.0, 'grossBookings': 0.0,
        'fy27': {'netPipeline': 0.0, 'grossPipeline': 0.0, 'ariCount': 0,
                 'activeDsrs': 0, 'investedHours': 0.0,
                 'netBooked': 0.0, 'grossBooked': 0.0},
        'fy28': {'netPipeline': 0.0, 'grossPipeline': 0.0, 'ariCount': 0,
                 'activeDsrs': 0, 'investedHours': 0.0,
                 'netBooked': 0.0, 'grossBooked': 0.0},
    }


def load_records(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return data.get('records', []), data.get('totalSize', 0)


def build(records):
    person_dsrs  = {pid: [] for pid in ALL_META}
    person_stats = {pid: empty_stats() for pid in ALL_META}
    seen_booked  = {pid: set() for pid in ALL_META}   # opp IDs already counted toward booked

    for record in records:
        pid = record.get('OwnerId', '')
        if pid not in ALL_META:
            continue
        stage    = record.get('Oppty_Stage__c') or ''
        status   = record.get('Status__c') or ''
        close    = record.get('Oppty_Close_Date__c') or ''
        est_h    = float(record.get('Estimated_Hours__c') or 0)
        spent_h      = float(record.get('Hours_spent__c') or 0)
        request_type = record.get('Request_Type__c') or ''
        opp          = record.get('Opportunity__r') or {}
        opp_url      = (opp.get('attributes') or {}).get('url') or ''
        opp_id       = opp_url.rsplit('/', 1)[-1] if opp_url else (opp.get('Id') or opp.get('Name') or '')
        amount       = float(opp.get('Amount') or 0)
        gross        = float(opp.get('Gross_Bookings__c') or 0)
        opp_name     = opp.get('Name') or ''

        person_dsrs[pid].append({
            'id': record['Id'], 'name': record.get('Name', ''), 'status': status,
            'account': record.get('Oppty_Account__c', ''), 'stage': stage,
            'closeDate': close, 'oppName': opp_name, 'oppId': opp_id,
            'estimatedHours': est_h, 'spentHours': spent_h,
            'dealValue': amount, 'grossBookings': gross,
            'requestType': request_type,
        })

        s = person_stats[pid]
        s['activeDSRs']    += 1
        s['spentHours']    += spent_h
        s['pipelineValue'] += amount
        s['grossBookings'] += gross
        if (not INACTIVE.search(stage) or request_type == 'Delivery Expertise') and not is_closed(status):
            s['estimatedHours'] += est_h

        fy = get_fy(close)
        if fy in ('FY27', 'FY28'):
            fb = s[fy.lower()]
            fb['netPipeline']   += amount
            fb['grossPipeline'] += gross
            fb['activeDsrs']    += 1
            fb['investedHours'] += spent_h
            if re.search(r'booked', stage, re.IGNORECASE) and opp_id not in seen_booked[pid]:
                seen_booked[pid].add(opp_id)
                fb['netBooked']   += amount
                fb['grossBooked'] += gross
            if ARI_RE.search(opp_name):
                fb['ariCount'] += 1

    return person_dsrs, person_stats


def monthly_pipeline(person_dsrs):
    monthly = defaultdict(float)
    for pid, dsrs in person_dsrs.items():
        for d in dsrs:
            if INACTIVE.search(d.get('stage', '')):
                continue
            if is_closed(d.get('status', '')):
                continue
            close = d.get('closeDate', '')
            if not close or close < '2026-02-01':
                continue
            monthly[close[:7]] += d.get('dealValue', 0) or 0

    result = []
    for ym in sorted(monthly.keys()):
        y, m = int(ym[:4]), int(ym[5:])
        fy = y + 1 if m >= 2 else y
        result.append({
            'label': MONTH_NAMES[m] + ' ' + str(y),
            'fiscal_label': f'FY{str(fy)[-2:]} {FY_Q[m]}',
            'pipeline_value': round(monthly[ym], 2),
        })
    return result


def monthly_booked(person_dsrs):
    """Monthly net/gross booked, deduplicated globally by opportunity ID."""
    seen = set()
    net_by_month   = defaultdict(float)
    gross_by_month = defaultdict(float)
    for pid, dsrs in person_dsrs.items():
        for d in dsrs:
            if not re.search(r'booked', d.get('stage', ''), re.IGNORECASE):
                continue
            close = d.get('closeDate', '')
            if not close or close < '2026-02-01':
                continue
            opp_key = d.get('oppId') or d.get('oppName') or d['id']
            if opp_key in seen:
                continue
            seen.add(opp_key)
            ym = close[:7]
            net_by_month[ym]   += d.get('dealValue', 0) or 0
            gross_by_month[ym] += d.get('grossBookings', 0) or 0

    result = []
    for ym in sorted(set(net_by_month) | set(gross_by_month)):
        y, m = int(ym[:4]), int(ym[5:])
        fy = y + 1 if m >= 2 else y
        net   = round(net_by_month[ym], 2)
        gross = round(gross_by_month[ym], 2)
        result.append({
            'label':       MONTH_NAMES[m] + ' ' + str(y),
            'fiscal_label': f'FY{str(fy)[-2:]} {FY_Q[m]}',
            'net_booked':   net,
            'gross_booked': gross,
        })
    return result


def weekly_capacity(person_dsrs, num_people):
    all_active = []
    for pid, dsrs in person_dsrs.items():
        for d in dsrs:
            if INACTIVE.search(d.get('stage', '')):
                continue
            if is_closed(d.get('status', '')):
                continue
            hrs   = d.get('estimatedHours', 0) or 0
            close = d.get('closeDate', '')
            if hrs <= 0 or not close:
                continue
            all_active.append({'hours': hrs, 'closeDate': close})

    today   = date.today()
    monday  = today - timedelta(days=today.weekday())
    avail   = num_people * 40
    weeks   = []
    for i in range(12):
        ws        = (monday + timedelta(weeks=i)).isoformat()
        committed = sum(d['hours'] for d in all_active if d['closeDate'] >= ws)
        weeks.append({
            'weekStart':      ws,
            'committedHours': round(committed, 1),
            'availableHours': avail,
            'utilization':    round(committed / avail * 100, 1) if avail > 0 else 0,
        })
    return weeks


def main():
    all_records = []
    sizes = []
    for path in [T1_FILE, T2_FILE]:
        if path:
            recs, sz = load_records(path)
            all_records.extend(recs)
            sizes.append(sz)

    person_dsrs, person_stats = build(all_records)

    team_list = []
    for pid, (name, title, group) in ALL_META.items():
        s = person_stats[pid]
        team_list.append({
            'id': pid, 'name': name, 'title': title, 'group': group,
            'activeDSRs':     s['activeDSRs'],
            'estimatedHours': round(s['estimatedHours'], 1),
            'spentHours':     round(s['spentHours'], 1),
            'pipelineValue':  round(s['pipelineValue'], 2),
            'grossBookings':  round(s['grossBookings'], 2),
            'fy27': {k: round(v, 2) if isinstance(v, float) else v
                     for k, v in s['fy27'].items()},
            'fy28': {k: round(v, 2) if isinstance(v, float) else v
                     for k, v in s['fy28'].items()},
        })

    data = {
        'lastRefreshed': datetime.now(timezone.utc).isoformat(),
        'seeded': False,
        'team': team_list,
        'monthlyPipeline': monthly_pipeline(person_dsrs),
        'monthlyBooked':   monthly_booked(person_dsrs),
        'personDSRs':      person_dsrs,
        'weeklyCapacity':  weekly_capacity(person_dsrs, len(ALL_META)),
    }

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total_pipe = sum(p['pipelineValue'] for p in team_list) / 1e6
    wk0 = data['weeklyCapacity'][0]
    print(f'Records loaded: {sizes}  (total {len(all_records)})')
    print(f'People: {len(team_list)}')
    print(f'Week 0: {wk0["committedHours"]}h / {wk0["availableHours"]}h = {wk0["utilization"]}%')
    print(f'Net pipeline total: ${total_pipe:.1f}M')
    print('data.json rebuilt OK')


if __name__ == '__main__':
    main()

from test_app import clients, project
from analysis import storage, main


def test_metrics_exclude_previous_day_and_include_pacific_midnight(clients, monkeypatch):
    owner, _ = clients
    p, v, _ = project(owner)
    monkeypatch.setattr(main, 'today_window', lambda: ('2026-10-25', '2026-10-25T07:00:00+00:00', '2026-10-26T07:00:00+00:00'))
    with storage.db() as con:
        for n, timestamp in enumerate(('2026-10-25T06:59:59Z','2026-10-25T07:00:00Z','2026-10-26T06:59:59Z','2026-10-26T07:00:00Z')):
            con.execute('INSERT INTO engagement_events(event_id,version_id,anonymous_session_id,type,occurred_at,server_received_at) VALUES(?,?,?,?,?,?)',
                        (str(n),v['id'],str(n),'page_view',timestamp,timestamp))
    response = owner.get('/api/projects/'+p['id']+'/analytics').json()
    assert response['metrics']['page_visitors'] == 2
    assert response['period'] == 'Today, Pacific time (2026-10-25)'

import json
import time
from types import SimpleNamespace
import pytest
from test_app import clients
from test_oauth import google
from analysis import youtube, storage, gemini_analyzer, worker, evidence


def linked_project(owner):
    p = owner.post('/api/projects', json={'title': 'Linked review test'}).json()
    v = owner.post('/api/projects/' + p['id'] + '/versions', json={
        'repository_url': 'https://github.com/test/project',
        'video_source_url': 'https://youtu.be/abcdefghijk'}).json()
    user = owner.get('/api/me').json()
    with storage.db() as con:
        con.execute('INSERT INTO youtube_connections VALUES(?,?,?,?,?)',
                    (user['id'], 'channel-A', 'A', 'encrypted', time.time()))
    return v, user


@pytest.mark.parametrize('privacy,duration,channel,error', [
    ('public', 'PT1M', 'channel-A', None),
    ('unlisted', 'PT1M', 'channel-A', 'public_url'),
    ('private', 'PT1M', 'channel-A', 'public_url'),
    ('public', 'PT3M', 'channel-A', 'duration_limit'),
    ('public', 'PT1M', 'channel-B', 'wrong_channel'),
])
def test_review_media_checks(clients, google, privacy, duration, channel, error):
    owner, _ = clients
    v, user = linked_project(owner)
    google.setattr(youtube, 'access_token', lambda conn: 'access')
    google.setattr(youtube, 'get', lambda *args, **kwargs: {'items': [{
        'snippet': {'channelId': channel}, 'status': {'privacyStatus': privacy},
        'contentDetails': {'duration': duration}}]})
    if error:
        with pytest.raises(ValueError, match=error):
            youtube.review_media(v, user['id'])
    else:
        media = youtube.review_media(v, user['id'])
        assert media['duration_ms'] == 60000
        assert media['has_audio'] is None
        assert media['url'] == 'https://www.youtube.com/watch?v=abcdefghijk'


def test_successful_reports_are_scoped_private_and_cached(clients, google):
    owner, stranger = clients
    v, _ = linked_project(owner)
    google.setattr(youtube, 'access_token', lambda conn: 'access')
    calls = []
    def get(client, path, params, token, analytics=False):
        calls.append((path, params))
        if path == 'videos':
            return {'items': [{'snippet': {'channelId': 'channel-A'}}]}
        return {'columnHeaders': [{'name': n} for n in ('day', 'views', 'estimatedMinutesWatched', 'averageViewDuration', 'averageViewPercentage')],
                'rows': [[youtube.today_window()[0], 12, 8, 40, 66.7]]}
    google.setattr(youtube, 'get', get)
    url = '/api/versions/' + v['id'] + '/youtube-analytics'
    report = owner.get(url).json()
    assert report['status'] == 'connected'
    assert report['daily'][0]['views'] == 12
    assert calls[1][1]['filters'] == 'video==abcdefghijk'
    assert calls[1][1]['ids'] == 'channel==MINE'
    assert calls[1][1]['startDate'] == calls[1][1]['endDate'] == youtube.today_window()[0]
    assert owner.get(url).json() == report
    assert len(calls) == 2
    assert stranger.get(url).status_code in (403, 404)


def test_linked_review_runs_without_upload_and_seals_source(clients, google, tmp_path):
    owner, _ = clients
    v, _ = linked_project(owner)
    for key, value in {'ENABLE_LIVE_ANALYSIS':'1', 'GEMINI_API_KEY':'test-key',
                       'INPUT_USD_PER_MILLION':'1', 'OUTPUT_USD_PER_MILLION':'1',
                       'MAX_ANALYSIS_USD':'1', 'MAX_DAILY_ANALYSES':'8'}.items():
        google.setenv(key, value)
    google.setattr(evidence, 'DATA', tmp_path)
    google.setattr(youtube, 'review_media', lambda *args: {
        'kind':'youtube_url', 'url':'https://www.youtube.com/watch?v=abcdefghijk',
        'duration_ms':60000, 'has_audio':None, 'content_hash_available':False})
    calls = []
    class Models:
        def count_tokens(self, **kwargs):
            assert kwargs['contents'][0].file_data.file_uri.endswith('abcdefghijk')
            return SimpleNamespace(total_tokens=1000)
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=json.dumps({'summary':'Controlled test response', 'claims':[
                {'text':'Booking displayed', 'video_start_ms':0, 'video_end_ms':1000,
                 'observation_or_assertion':'observation', 'source_modality':'visual',
                 'explanation':'Visible in supplied test response', 'evidence':[
                     {'file_path':'app.py', 'start_line':1, 'end_line':2, 'relation':'contradicts', 'explanation':'Mock return'}]}],
                'improvements':[]}), usage_metadata=None)
    class Client:
        def __init__(self, **kwargs): self.models = Models()
        def close(self): pass
        # Deliberately no Files API: linked review must not upload anything.
    google.setattr(gemini_analyzer.genai, 'Client', Client)
    result = owner.post('/api/versions/' + v['id'] + '/analyze', json={'consent':True})
    assert result.status_code == 200
    assert worker.once()
    r = owner.get('/api/analysis/' + result.json()['run_id']).json()
    assert r['run']['status'] == 'succeeded'
    assert r['result']['claims'][0]['evidence'][0]['url'].endswith('/app.py#L1-L2')
    assert 'not preserved' in r['result']['limitations'][-1]
    assert owner.get('/api/analysis/' + result.json()['run_id'] + '/evidence').json()['verified']
    assert len(calls) == 1

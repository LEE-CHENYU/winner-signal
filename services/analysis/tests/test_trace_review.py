import json
import pytest
from analysis.gemini_analyzer import validate_review


def test_trace_findings_require_exact_provenance_and_validate_code():
    version = {'snapshot_json': json.dumps({'files': {'app.py': {'text': 'return False\n', 'sha256': 'sourcehash'}}}),
               'repository_url': 'https://github.com/example/project', 'commit_sha': 'a'*40,
               'duration_ms': 1000, 'has_audio': False}
    history = {'id': 'history1', 'text': 'human: fix it\nagent: changed app.py\ntool: test failed', 'full_artifact_sha256': 'historyhash'}
    finding = {'artifact_id': 'history1', 'quote': 'tool: test failed', 'actor': 'tool',
               'action': 'Ran tests', 'outcome': 'Test failure', 'outcome_status': 'reported_failure',
               'assessment': 'Requires repair', 'evidence': [
                   {'file_path': 'app.py', 'start_line': 1, 'end_line': 1, 'relation': 'contextualizes', 'explanation': 'Implementation'},
                   {'file_path': 'invented.py', 'start_line': 1, 'end_line': 2, 'relation': 'supports', 'explanation': 'Invalid'}]}
    data = {'summary': 'Review', 'claims': [], 'improvements': [], 'trace_findings': [finding, {**finding, 'quote': 'Tests passed'}]}
    result = validate_review(data, version, [history])
    assert result['trace_status'] == 'reviewed'
    assert len(result['trace_findings']) == 1
    trace = result['trace_findings'][0]
    assert history['text'][trace['start_char']:trace['end_char']] == trace['quote']
    assert trace['artifact_sha256'] == 'historyhash'
    assert len(trace['evidence']) == 1
    assert trace['evidence'][0]['url'].endswith('/app.py#L1-L1')
    assert validate_review(data, version)['trace_findings'] == []
    assert validate_review(data, version)['trace_status'] == 'not_supplied'


def test_video_timestamp_validation_remains_strict():
    with pytest.raises(ValueError, match='invalid_video_timestamp'):
        validate_review({'summary':'x', 'improvements':[], 'claims':[
            {'text':'x','video_start_ms':0,'video_end_ms':2000,'observation_or_assertion':'observation',
             'source_modality':'visual','explanation':'x'}]},
            {'snapshot_json':'{}', 'duration_ms':1000, 'has_audio':False})

"""Offline synthetic viewer model. No participant data, API calls, or training export.
Unit: one viewer; terminal outcome: exit at one scene or complete all semantic sections.
Reactions and behavior are assumed probabilities, not fitted observations.
Run: python3 scripts/simulate_video_reactions.py
"""
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REACTIONS = ['Interested', 'Confused', 'Skeptical', 'Disengaged']
PERSONAS = {
    'Builder': {'weight': .45, 'reactions': [.60, .15, .15, .10]},
    'Evaluator': {'weight': .30, 'reactions': [.45, .10, .35, .10]},
    'Casual viewer': {'weight': .25, 'reactions': [.30, .20, .15, .35]},
}
SCENES = [{'id': 'intro',
  'time': '00:00–00:10',
  'end': 10,
  'title': 'Value proposition',
  'content': 'The fictional narrator promises to connect an AI-built artifact to evidence of what works.',
  'reaction_adjustment': [0, 0, 0, 0],
  'exit_friction': 0,
  'commit': '60183a2',
  'file': 'apps/web/src/components/app.tsx',
  'trajectory': 'The actual build replaced a fictional trace example with curated decisions, failures, tests, and '
                'commit references.',
  'experiment': 'Compare an abstract promise with one concrete evidence chain.',
  'meanings': ['Relevant to my workflow',
               'Unclear what is being evaluated',
               'Claims need evidence',
               'Not relevant to me']},
 {'id': 'connect',
  'time': '00:10–00:25',
  'end': 25,
  'title': 'Uploader identity and permissions',
  'content': 'The fictional builder switches to the account that owns the demo video.',
  'reaction_adjustment': [-0.1, 0.1, 0, 0],
  'exit_friction': 0.04,
  'commit': '6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95',
  'file': 'services/analysis/analysis/google_oauth.py',
  'trajectory': 'Recorded OAuth failures were followed by a repair and passing tests. The code supports same-account '
                'connection and a separate uploader fallback.',
  'experiment': 'Compare concise account guidance with a complete switch walkthrough; test ownership-task completion.',
  'meanings': ['Useful account flexibility',
               'Which account should I connect?',
               'Why are these permissions needed?',
               'Setup is too much effort']},
 {'id': 'claim',
  'time': '00:25–00:38',
  'end': 38,
  'title': 'Video claim extraction',
  'content': 'A fictional review isolates a narrated claim and marks its video timestamp and observation type.',
  'reaction_adjustment': [0.05, 0, -0.05, 0],
  'exit_friction': 0,
  'commit': '6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95',
  'file': 'services/analysis/analysis/gemini_analyzer.py',
  'trajectory': 'The analyzer classifies visible observations versus narrated assertions and validates video timestamp '
                'bounds.',
  'experiment': 'Test whether viewers distinguish a narrated promise from a demonstrated action.',
  'meanings': ['This makes the claim concrete',
               'What counts as an observation?',
               'Did the model invent this claim?',
               'Too much explanation']},
 {'id': 'evidence',
  'time': '00:38–00:53',
  'end': 53,
  'title': 'Source-code grounding',
  'content': 'The fictional builder opens the claim’s pinned source file and checks the cited lines.',
  'reaction_adjustment': [0.05, -0.05, 0, 0],
  'exit_friction': 0,
  'commit': '698857b',
  'file': 'services/analysis/analysis/gemini_analyzer.py',
  'trajectory': 'The implementation validates source-line ranges and constructs pinned source references; the build '
                'also added structured trace findings.',
  'experiment': 'Ask viewers to locate the cited code and explain what it supports without claiming execution.',
  'meanings': ['The claim is inspectable',
               'How does this code support it?',
               'Code existing does not prove it ran',
               'Code detail is too technical']},
 {'id': 'trace',
  'time': '00:53–01:10',
  'end': 70,
  'title': 'Agent-action attribution',
  'content': 'The fictional review expands an actor/action/outcome finding and its exact history quote.',
  'reaction_adjustment': [0, 0, 0.05, -0.05],
  'exit_friction': 0.01,
  'commit': '698857b',
  'file': 'services/analysis/analysis/gemini_analyzer.py',
  'trajectory': 'The agent added actor/action/outcome findings, exact trace-quote validation, character offsets, and '
                'supporting code references.',
  'experiment': 'Test whether viewers identify the actual action and separate quoted reports from independently '
                'verified outcomes.',
  'meanings': ['I can inspect the build decision',
               'Which actor caused the result?',
               'A reported outcome is not verification',
               'The history is too detailed']},
 {'id': 'recovery',
  'time': '01:10–01:30',
  'end': 90,
  'title': 'Failure recovery and result',
  'content': 'A fictional format error is followed by retry and a completed evidence report; this screen sequence was '
             'not observed.',
  'reaction_adjustment': [-0.1, 0.05, 0.05, 0],
  'exit_friction': 0.02,
  'commit': 'b53f633',
  'file': 'services/analysis/analysis/gemini_analyzer.py',
  'trajectory': 'After a recorded JSON parsing failure, the agent bounded output and added diagnostics. A subsequent '
                'live run returned five claims and six trace findings with a verified seal.',
  'experiment': 'Compare result-first and recovery-first edits; evaluate comprehension separately from retention.',
  'meanings': ['The recovery is useful',
               'What fixed the failure?',
               'Will this fail again?',
               'The payoff took too long']}]
EXIT = dict(zip(REACTIONS, [.04, .22, .14, .45]))
REPLAY = dict(zip(REACTIONS, [.18, .35, .12, .02]))


def simulate(seed, n=1000):
    if n < 1:
        raise ValueError('cohort must be positive')
    rng = random.Random(seed)
    viewers = []
    for i in range(n):
        persona = rng.choices(list(PERSONAS), [p['weight'] for p in PERSONAS.values()])[0]
        path = []
        for scene in SCENES:
            weights = [p + d for p, d in zip(PERSONAS[persona]['reactions'], scene['reaction_adjustment'])]
            assert min(weights) >= 0 and abs(sum(weights) - 1) < 1e-9
            reaction = rng.choices(REACTIONS, weights)[0]
            replay = rng.random() < REPLAY[reaction]
            leave = rng.random() < EXIT[reaction] + scene['exit_friction']
            path.append({'scene': scene['id'], 'reaction': reaction, 'replay': replay, 'exit': leave})
            if leave:
                break
        viewers.append({'id': f'sim-{seed}-{i + 1:04}', 'persona': persona,
                        'completed': not path[-1]['exit'], 'path': path})
    stages = []
    for scene in SCENES:
        events = [e for v in viewers for e in v['path'] if e['scene'] == scene['id']]
        reactions = Counter(e['reaction'] for e in events)
        stages.append({'id': scene['id'], 'reached': len(events),
                       'exits': sum(e['exit'] for e in events),
                       'replays': sum(e['replay'] for e in events),
                       'reactions': {r: reactions[r] for r in REACTIONS}})
    completed = sum(v['completed'] for v in viewers)
    personas = dict(Counter(v['persona'] for v in viewers))
    final_reactions = dict(Counter(v['path'][-1]['reaction'] for v in viewers))
    assert sum(personas.values()) == sum(final_reactions.values()) == n
    assert completed + sum(s['exits'] for s in stages) == n
    for i, stage in enumerate(stages):
        assert sum(stage['reactions'].values()) == stage['reached']
        assert 0 <= stage['replays'] <= stage['reached']
        assert stage['reached'] - stage['exits'] == (stages[i+1]['reached'] if i < len(SCENES) - 1 else completed)
    for v in viewers:
        assert [e['scene'] for e in v['path']] == [s['id'] for s in SCENES[:len(v['path'])]]
        assert not any(e['exit'] for e in v['path'][:-1])
        assert v['completed'] == (len(v['path']) == len(SCENES) and not v['path'][-1]['exit'])
    samples = []
    for persona in PERSONAS:
        for outcome in [True, False]:
            sample = next((v for v in viewers if v['persona'] == persona and v['completed'] == outcome), None)
            if sample:
                samples.append(sample)
    return {'seed': seed, 'n': n, 'completed': completed, 'personas': personas,
            'final_reactions': {r: final_reactions.get(r, 0) for r in REACTIONS},
            'stages': stages, 'samples': samples}


def main():
    runs = [simulate(20261025 + i) for i in range(100)]
    assert runs[0] == simulate(20261025), 'seed reproducibility'
    assert simulate(1, 1)['n'] == 1, 'single-viewer boundary'
    try:
        simulate(1, 0)
        raise AssertionError('empty cohort accepted')
    except ValueError:
        pass
    rates = sorted(r['completed'] / r['n'] * 100 for r in runs)
    section_ranges = {}
    for index, scene in enumerate(SCENES):
        section_ranges[scene['id']] = {}
        for reaction in REACTIONS:
            values = sorted(100 * r['stages'][index]['reactions'][reaction] / r['stages'][index]['reached'] for r in runs)
            section_ranges[scene['id']][reaction] = {'p10': round(values[9], 1), 'p90': round(values[89], 1)}
    result = {'version': 'synthetic-viewers-v2-semantic', 'synthetic': True, 'reactions': REACTIONS,
              'personas': PERSONAS, 'exit_probabilities': EXIT, 'replay_probabilities': REPLAY,
              'scenes': SCENES, 'runs': runs[:3], 'section_ranges': section_ranges,
              'distribution_check': {'runs': 100, 'viewers_per_run': 1000, 'seed_start': 20261025,
                  'completion_percent': {'min': rates[0], 'p10': rates[9], 'median': (rates[49]+rates[50])/2,
                                         'p90': rates[89], 'max': rates[-1]},
                  'checks': ['Seed reproducibility', 'Starts = exits + completions',
                             'Scene reactions = viewers reached', 'No events after exit',
                             'Replays bounded by reached viewers', 'Single-viewer and invalid-cohort boundaries'],
                  'status': 'passed'}}
    path = ROOT / 'apps/web/src/lib/viewer-simulation.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'distribution_check': result['distribution_check'], 'baseline': runs[0]}, indent=2))

if __name__ == '__main__':
    main()

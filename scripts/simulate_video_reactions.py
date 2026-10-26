"""Offline synthetic viewer model. No participant data, API calls, or training export.
Unit: one viewer; terminal outcome: exit at one scene or complete all four.
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
SCENES = [
    {'id': 'intro', 'time': '00:00–00:15', 'end': 15, 'title': 'Introduce the project',
     'content': 'A fictional builder shares a demo and repository. “What did the agent build, and what evidence supports it?”',
     'reaction_adjustment': [0, 0, 0, 0], 'exit_friction': 0,
     'commit': '60183a2', 'file': 'apps/web/src/components/app.tsx',
     'trajectory': 'The actual build replaced a fictional trace example with curated project decisions, failures, tests, and commit references.',
     'experiment': 'Compare a concrete evidence example with an abstract introduction; measure subsequent evidence-location success.'},
    {'id': 'connect', 'time': '00:15–00:30', 'end': 30, 'title': 'Connect the uploader account',
     'content': 'The fictional builder switches from their sign-in account to the account that uploaded the video.',
     'reaction_adjustment': [-.10, .10, 0, 0], 'exit_friction': .04,
     'commit': '6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95', 'file': 'services/analysis/analysis/google_oauth.py',
     'trajectory': 'Recorded OAuth failures were followed by a repair and passing tests. The code supports same-account connection and a separate uploader fallback.',
     'experiment': 'Compare a short explanation with a complete account-switch walkthrough; separately test task completion.'},
    {'id': 'evidence', 'time': '00:30–01:00', 'end': 60, 'title': 'Inspect a claim and its agent trace',
     'content': 'A fictional review opens a source citation and an exact quote from the coding-agent history.',
     'reaction_adjustment': [.05, -.05, 0, 0], 'exit_friction': 0,
     'commit': '698857b', 'file': 'services/analysis/analysis/gemini_analyzer.py',
     'trajectory': 'The agent added structured actor/action/outcome findings, exact trace quotations, character offsets, and source validation.',
     'experiment': 'Test whether viewers can locate supporting code and distinguish textual support from verified execution.'},
    {'id': 'recovery', 'time': '01:00–01:30', 'end': 90, 'title': 'Recover a failed review',
     'content': 'A fictional format error is followed by a retry and a completed evidence report. This on-screen sequence was not observed.',
     'reaction_adjustment': [-.10, .05, .05, 0], 'exit_friction': .02,
     'commit': 'b53f633', 'file': 'services/analysis/analysis/gemini_analyzer.py',
     'trajectory': 'After a recorded JSON parsing failure, the agent bounded output and added diagnostics. A subsequent live run returned five claims and six trace findings with a verified seal.',
     'experiment': 'Compare result-first and recovery-first edits, then measure understanding rather than treating retention as correctness.'},
]
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
        assert stage['reached'] - stage['exits'] == (stages[i+1]['reached'] if i < 3 else completed)
    for v in viewers:
        assert [e['scene'] for e in v['path']] == [s['id'] for s in SCENES[:len(v['path'])]]
        assert not any(e['exit'] for e in v['path'][:-1])
        assert v['completed'] == (len(v['path']) == 4 and not v['path'][-1]['exit'])
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
    result = {'version': 'synthetic-viewers-v1', 'synthetic': True, 'reactions': REACTIONS,
              'personas': PERSONAS, 'exit_probabilities': EXIT, 'replay_probabilities': REPLAY,
              'scenes': SCENES, 'runs': runs[:3],
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

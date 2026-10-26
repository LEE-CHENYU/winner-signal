"use client";

import { useState } from "react";
import simulation from "@/lib/viewer-simulation.json";

const percent = (count: number, total: number) => `${(100 * count / total).toFixed(1)}%`;
const colors = ["#27272a", "#71717a", "#a1a1aa", "#d4d4d8"];

export function ViewerSimulation() {
  const [runIndex, setRunIndex] = useState(0);
  const [sceneIndex, setSceneIndex] = useState(0);
  const run = simulation.runs[runIndex];
  const scene = simulation.scenes[sceneIndex];
  const stage = run.stages[sceneIndex];
  const ranges = simulation.distribution_check.completion_percent;
  const replayEvents = run.stages.reduce((sum, item) => sum + item.replays, 0);
  const largestExit = run.stages.reduce((best, item) => item.exits / item.reached > best.exits / best.reached ? item : best);
  const largestScene = simulation.scenes.find(item => item.id === largestExit.id)!;
  const repo = "https://github.com/LEE-CHENYU/winner-signal";
  return <section className="panel" aria-labelledby="viewer-simulation-heading">
    <div className="section-heading">
      <div><h2 id="viewer-simulation-heading">Semantic section reactions → agent trajectory</h2><p>Six meaning-based sections in a fictional 90-second walkthrough.</p></div>
      <span className="pill">SIMULATED SCENES + VIEWERS</span>
    </div>
    <p className="notice">All scenes, reactions, and viewing events here are invented. This offline probability model is not a human study, a YouTube report, or a prediction of real audiences. Code and build-history links are real; their scene mappings are curated.</p>
    <label htmlFor="simulation-seed">Inspect a reproducible cohort </label>
    <select id="simulation-seed" value={runIndex} onChange={event => setRunIndex(Number(event.target.value))}>
      {simulation.runs.map((item, index) => <option key={item.seed} value={index}>Seed {item.seed} · {item.n.toLocaleString()} synthetic viewers</option>)}
    </select>
    <div className="row" style={{ flexWrap: "wrap", gap: "2rem", marginBlock: "1.5rem" }}>
      <div><strong>{run.n.toLocaleString()}</strong><p className="muted">Simulated starts</p></div>
      <div><strong>{run.completed} · {percent(run.completed, run.n)}</strong><p className="muted">Completed all six sections</p></div>
      <div><strong>{run.n - run.completed}</strong><p className="muted">Exited before completion</p></div>
      <div><strong>{replayEvents}</strong><p className="muted">Replay events · not unique viewers</p></div>
    </div>
    <h3>Reaction distribution by semantic section</h3>
    <p>Sections are authored around a change in claim or action, not equal time bins. Select a section to inspect what each reaction means and the relevant agent trajectory. Percentages are conditional on reaching the section.</p>
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", minWidth: "720px" }}>
        <thead><tr><th scope="col">Semantic section</th><th scope="col">Reached</th>{simulation.reactions.map(reaction => <th scope="col" key={reaction}>{reaction}</th>)}</tr></thead>
        <tbody>{run.stages.map((item, index) => <tr key={item.id} style={{ borderTop: "1px solid #d4d4d8", background: index === sceneIndex ? "#f4f4f5" : undefined }}>
          <th scope="row" style={{ padding: ".75rem" }}><button type="button" className="secondary" aria-pressed={index === sceneIndex} onClick={() => setSceneIndex(index)}>{simulation.scenes[index].time} · {simulation.scenes[index].title}</button></th>
          <td>{item.reached}</td>{Object.entries(item.reactions).map(([name, count]) => <td key={name} style={{ padding: ".6rem" }}>{count}<br /><span className="muted">{percent(count, item.reached)}</span></td>)}
        </tr>)}</tbody>
      </table>
    </div>
    <details><summary>Retention and replay distribution</summary>
    <p>Select a scene to trace its simulated reaction back to an actual build change.</p>
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", minWidth: "640px" }}>
        <caption className="muted" style={{ textAlign: "left", marginBottom: ".7rem" }}>Exit and replay rates use viewers who reached that scene. Remaining uses all {run.n} starts.</caption>
        <thead><tr>{["Fictional scene", "Reached", "Exited", "Replayed", "Remaining"].map(label => <th key={label} scope="col" style={{ padding: ".6rem" }}>{label}</th>)}</tr></thead>
        <tbody>{run.stages.map((item, index) => <tr key={item.id} style={{ borderTop: "1px solid #d4d4d8", background: index === sceneIndex ? "#f4f4f5" : undefined }}>
          <th scope="row" style={{ padding: ".6rem" }}><button type="button" className="secondary" aria-pressed={index === sceneIndex} onClick={() => setSceneIndex(index)}>{simulation.scenes[index].time} · {simulation.scenes[index].title}</button></th>
          <td>{item.reached}</td><td>{item.exits} ({percent(item.exits, item.reached)})</td><td>{item.replays} ({percent(item.replays, item.reached)})</td><td>{percent(item.reached - item.exits, run.n)}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p><strong>Model observation:</strong> “{largestScene.title}” has the largest conditional exit rate in this cohort: {percent(largestExit.exits, largestExit.reached)}. This pattern follows the model’s assumed probabilities; it is not a discovered product defect.</p>
    </details>
    <article className="claim" aria-live="polite">
      <div className="row"><h3>{scene.time} · {scene.title}</h3><span className="pill">Fictional scene</span></div>
      <p>{scene.content}</p>
      <h4>What the simulated reactions refer to</h4>
      <p className="muted">Authored interpretations, not user quotations or inferred mental states. Each of the {stage.reached} reached viewers receives one simulated reaction in this section.</p>
      {Object.entries(stage.reactions).map(([reaction, count], index) => {
        const sectionRanges = simulation.section_ranges[scene.id as keyof typeof simulation.section_ranges];
        const range = sectionRanges[reaction as keyof typeof sectionRanges];
        return <div className="claim" key={reaction}>
          <div className="row"><strong>{reaction} · {count} / {stage.reached} ({percent(count, stage.reached)})</strong><span>{scene.meanings[index]}</span></div>
          <div style={{ background: "#f4f4f5", height: "12px", marginBlock: ".6rem" }}><div style={{ width: percent(count, stage.reached), height: "100%", background: colors[index] }} /></div>
          <p className="muted">100-cohort conditional distribution, empirical p10–p90: {range.p10.toFixed(1)}–{range.p90.toFixed(1)}%. Model variation only.</p>
        </div>;
      })}
      <p><strong>Actual agent trajectory:</strong> {scene.trajectory}</p>
      <p><a href={`${repo}/blob/${scene.commit}/${scene.file}`} target="_blank" rel="noreferrer">Inspect pinned code ↗</a> · <a href={`${repo}/commit/${scene.commit}`} target="_blank" rel="noreferrer">Inspect build change ↗</a></p>
      <p><strong>Candidate follow-up:</strong> {scene.experiment}</p>
      <p className="muted">The matched change implements behavior relevant to the invented scene. Viewing reactions do not establish causal agent credit or implementation correctness.</p>
    </article>
    <details><summary>Whole-video final reactions</summary>
    <h3>Final reaction distribution</h3>
    <p className="muted">One final reaction per viewer, at exit or completion. Earlier scene reactions are shown below.</p>
    {Object.entries(run.final_reactions).map(([reaction, count], index) => <div key={reaction} style={{ display: "grid", gridTemplateColumns: "7rem 1fr 7rem", gap: ".75rem", alignItems: "center", marginBlock: ".7rem" }}>
      <span>{reaction}</span><div style={{ background: "#f4f4f5", height: "14px" }}><div style={{ width: percent(count, run.n), background: colors[index], height: "100%" }} /></div><span>{count} · {percent(count, run.n)}</span>
    </div>)}
    </details>
    <details>
      <summary>Check the distribution · 100 cohorts × 1,000 viewers</summary>
      <p>Completion across seeds {simulation.distribution_check.seed_start}–{simulation.distribution_check.seed_start + 99}: median <strong>{ranges.median.toFixed(1)}%</strong>; empirical 10th–90th percentiles <strong>{ranges.p10.toFixed(1)}–{ranges.p90.toFixed(1)}%</strong>; minimum–maximum {ranges.min.toFixed(1)}–{ranges.max.toFixed(1)}%.</p>
      <p>This is Monte Carlo variation under fixed invented assumptions, not a confidence interval for real users. The 100 runs were all retained.</p>
      <p><strong>Checks passed:</strong> {simulation.distribution_check.checks.join("; ")}.</p>
      <p><strong>Selected cohort mix:</strong> {Object.entries(run.personas).map(([name, count]) => `${name}: ${count} (${percent(count, run.n)})`).join(" · ")}.</p>
    </details>
    <details>
      <summary>Inspect synthetic viewer paths</summary>
      <p className="muted">First completing and first exiting viewer per persona, where available. These examples illustrate paths; they are not a random sample.</p>
      {run.samples.map(viewer => <article className="claim" key={viewer.id}>
        <strong>{viewer.id} · {viewer.persona} · {viewer.completed ? "Completed" : "Exited"}</strong>
        <ol>{viewer.path.map(event => <li key={event.scene}>{simulation.scenes.find(item => item.id === event.scene)?.title}: {event.reaction.toLowerCase()}{event.replay ? " → replay" : ""} → {event.exit ? "exit" : event.scene === "recovery" ? "complete" : "continue"}</li>)}</ol>
      </article>)}
    </details>
    <details>
      <summary>Model assumptions and reproducibility</summary>
      <p>Version {simulation.version}. Each viewer is sampled independently: 45% builders, 30% evaluators, 25% casual viewers. Each reached scene gets one categorical reaction. Given that reaction, replay and exit are independent Bernoulli draws. At most one replay is counted per scene. A viewer stops immediately on exit.</p>
      <p>Base reaction weights in order interested / confused / skeptical / disengaged: builders 60/15/15/10%; evaluators 45/10/35/10%; casual viewers 30/20/15/35%.</p>
      <p>Section adjustments in percentage points (interested / confused / skeptical / disengaged): value proposition 0/0/0/0; uploader −10/+10/0/0; claim extraction +5/0/−5/0; source grounding +5/−5/0/0; agent attribution 0/0/+5/−5; recovery −10/+5/+5/0.</p>
      <p>Base exit probabilities: interested 4%, confused 22%, skeptical 14%, disengaged 45%. Uploader identity adds 4 percentage points, agent attribution adds 1, and recovery adds 2. Replay probabilities: interested 18%, confused 35%, skeptical 12%, disengaged 2%.</p>
      <p>Reactions are redrawn per scene given persona; the model does not represent memory, social influence, video length effects, or real comprehension. No probabilities have been calibrated against users. A longer section does not automatically increase its exit probability. Each section adds an exit opportunity, so changing the segmentation changes completion; do not compare this six-section model with the earlier four-section version as an improvement or regression.</p>
      <p>Run <code>python3 scripts/simulate_video_reactions.py</code> to regenerate and check the artifact. <a href={`${repo}/blob/main/scripts/simulate_video_reactions.py`} target="_blank" rel="noreferrer">Generator ↗</a> · <a href={`${repo}/blob/main/apps/web/src/lib/viewer-simulation.json`} target="_blank" rel="noreferrer">Aggregate artifact and sample paths ↗</a></p>
    </details>
    <p className="notice">Display-only simulation. No synthetic records are written to real reports, feedback totals, agent scores, or training datasets. No video file is generated.</p>
  </section>;
}

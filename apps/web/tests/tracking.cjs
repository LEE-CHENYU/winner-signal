/* eslint-disable @typescript-eslint/no-require-imports -- Node CommonJS test harness */
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");
const crypto = require("node:crypto");
function setup() {
  let clock = 0;
  const sent = [];
  const storage = new Map();
  const context = {
    exports: {},
    crypto,
    performance: { now: () => clock },
    sessionStorage: {
      getItem: (k) => storage.get(k),
      setItem: (k, v) => storage.set(k, v),
    },
    window: new EventTarget(),
    setTimeout: () => 1,
    clearTimeout: () => {},
    fetch: async (url, options) => {
      sent.push(...JSON.parse(options.body).events);
      return { ok: true };
    },
  };
  vm.runInNewContext(
    ts.transpileModule(fs.readFileSync("src/lib/tracking.ts", "utf8"), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    }).outputText,
    context,
  );
  class Video extends EventTarget {
    currentTime = 0;
    duration = 12;
    playbackRate = 1;
    paused = true;
    seeking = false;
  }
  const video = new Video();
  const player = new context.exports.InstrumentedPlayer(video, "v", "b", false);
  return {
    video,
    player,
    sent,
    advance: (time) => {
      clock += time;
      video.currentTime += (time / 1000) * video.playbackRate;
      video.dispatchEvent(new Event("timeupdate"));
    },
    flush: context.exports.flush,
    start: () => {
      video.paused = false;
      video.dispatchEvent(new Event("play"));
    },
    exports: context.exports,
  };
}
test("continuous playback accumulates coverage and flushes on end", async () => {
  const s = setup();
  s.start();
  await s.flush();
  for (let i = 0; i < 48; i++) s.advance(250);
  s.video.paused = true;
  s.video.dispatchEvent(new Event("ended"));
  await s.flush();
  s.player.destroy();
  assert.ok(
    s.sent.some((e) => e.type === "video_progress" && e.coverage_ms >= 10800),
  );
});
test("seek-to-end never credits the skipped interval", async () => {
  const s = setup();
  s.start();
  await s.flush();
  s.advance(250);
  s.video.seeking = true;
  s.video.currentTime = 11.8;
  s.video.dispatchEvent(new Event("seeking"));
  s.video.seeking = false;
  s.video.dispatchEvent(new Event("seeked"));
  s.advance(200);
  s.video.dispatchEvent(new Event("ended"));
  await s.flush();
  s.player.destroy();
  assert.ok(
    s.sent
      .filter((e) => e.type === "video_progress")
      .every((e) => e.coverage_ms < 1000),
  );
});
test("overlapping playback intervals are counted only once", () => {
  const s = setup();
  const c = new s.exports.Coverage();
  c.add(0, 4000);
  c.add(2000, 6000);
  c.add(0, 6000);
  assert.equal(c.total(), 6000);
  s.player.destroy();
});
test("paused media jumps do not accumulate coverage", async () => {
  const s = setup();
  s.start();
  await s.flush();
  s.advance(250);
  s.video.paused = true;
  s.video.dispatchEvent(new Event("pause"));
  s.advance(4000);
  await s.flush();
  s.player.destroy();
  assert.ok(
    s.sent
      .filter((e) => e.type === "video_progress")
      .every((e) => e.coverage_ms < 1000),
  );
});

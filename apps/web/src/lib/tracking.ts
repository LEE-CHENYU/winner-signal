/** First-party telemetry only. Coverage is sampled playback, never a claim of attention. */
export function sessionId(): string {
  const old = sessionStorage.getItem("ws_visitor");
  if (old) return old;
  const id = crypto.randomUUID();
  sessionStorage.setItem("ws_visitor", id);
  return id;
}
type Event = {
  event_id: string;
  version_id: string;
  anonymous_session_id: string;
  type: string;
  is_diagnostic: boolean;
  playback_session_id?: string;
  binding_id?: string;
  media_position_ms?: number;
  playback_rate?: number;
  coverage_ms?: number;
};
let buffer: Event[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;
let flushing = false;
export function track(
  version: string,
  type: string,
  diagnostic = false,
  extra: Partial<Event> = {},
) {
  buffer.push({
    event_id: crypto.randomUUID(),
    version_id: version,
    anonymous_session_id: sessionId(),
    type,
    is_diagnostic: diagnostic,
    ...extra,
  });
  if (!timer) timer = setTimeout(() => void flush(), 1000);
}
export async function flush() {
  if (flushing || !buffer.length) return;
  flushing = true;
  clearTimeout(timer);
  timer = undefined;
  const batch = buffer.splice(0, 100);
  try {
    const r = await fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events: batch }),
      keepalive: true,
    });
    if (!r.ok) throw Error("telemetry");
  } catch {
    buffer = [...batch, ...buffer].slice(0, 200);
  } finally {
    flushing = false;
    if (buffer.length && !timer) timer = setTimeout(() => void flush(), 2000);
  }
}
export class Coverage {
  intervals: [number, number][] = [];
  add(a: number, b: number) {
    if (b > a && Number.isFinite(a) && Number.isFinite(b))
      this.intervals.push([a, b]);
  }
  total() {
    const merged: [number, number][] = [];
    for (const [a, b] of [...this.intervals].sort((x, y) => x[0] - y[0])) {
      const last = merged.at(-1);
      if (last && a <= last[1]) last[1] = Math.max(last[1], b);
      else merged.push([a, b]);
    }
    this.intervals = merged;
    return merged.reduce((s, [a, b]) => s + b - a, 0);
  }
}
export class InstrumentedPlayer {
  private coverage = new Coverage();
  private last = 0;
  private wall = 0;
  private playing = false;
  private started = false;
  private pid = crypto.randomUUID();
  private lastReport = 0;
  constructor(
    private el: HTMLVideoElement,
    private version: string,
    private binding: string,
    private diagnostic: boolean,
  ) {
    el.addEventListener("play", this.play);
    el.addEventListener("timeupdate", this.tick);
    el.addEventListener("pause", this.pause);
    el.addEventListener("seeking", this.seek);
    el.addEventListener("seeked", this.seeked);
    el.addEventListener("ended", this.pause);
    window.addEventListener("pagehide", this.hide);
  }
  private payload() {
    return {
      playback_session_id: this.pid,
      binding_id: this.binding,
      media_position_ms: Math.round(this.el.currentTime * 1000),
      playback_rate: this.el.playbackRate,
      coverage_ms: Math.round(this.coverage.total()),
    };
  }
  private reset() {
    this.last = this.el.currentTime * 1000;
    this.wall = performance.now();
  }
  private play = () => {
    this.playing = true;
    this.reset();
    if (!this.started) {
      this.started = true;
      track(this.version, "video_start", this.diagnostic, this.payload());
      void flush();
    }
  };
  private tick = () => {
    const position = this.el.currentTime * 1000;
    const now = performance.now();
    const advance = position - this.last;
    const elapsed = now - this.wall;
    if (
      this.playing &&
      !this.el.seeking &&
      advance > 0 &&
      advance <= elapsed * this.el.playbackRate + 200 &&
      elapsed < 2500
    )
      this.coverage.add(this.last, position);
    this.last = position;
    this.wall = now;
    if (now - this.lastReport > 1000) this.report();
  };
  private report = () => {
    if (!this.started) return;
    this.lastReport = performance.now();
    track(this.version, "video_progress", this.diagnostic, this.payload());
  };
  private pause = () => {
    this.tick();
    this.playing = false;
    this.report();
    void flush();
  };
  private seek = () => {
    this.playing = false;
    this.reset();
  };
  private seeked = () => {
    this.playing = !this.el.paused;
    this.reset();
  };
  private hide = () => {
    this.tick();
    this.report();
    void flush();
  };
  destroy() {
    this.hide();
    this.el.removeEventListener("play", this.play);
    this.el.removeEventListener("timeupdate", this.tick);
    this.el.removeEventListener("pause", this.pause);
    this.el.removeEventListener("seeking", this.seek);
    this.el.removeEventListener("seeked", this.seeked);
    this.el.removeEventListener("ended", this.pause);
    window.removeEventListener("pagehide", this.hide);
  }
}

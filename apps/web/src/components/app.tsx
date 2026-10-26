"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useCallback } from "react";
import {
  api,
  post,
  upload,
  message,
  type Project,
  type Version,
  type Card,
  type Demo,
  type Analytics,
  type Review,
  type Binding,
} from "@/lib/api";
import { YouTubeConnection, YouTubeAnalytics } from "./google-connect";
import { InstrumentedPlayer, track, sessionId, flush } from "@/lib/tracking";

function OptimizationLandscape() {
  const point = (u: number, v: number) => {
    const height = (1 - Math.exp(-(u * u + v * v) / 100)) * 125;
    return `${250 + (u - v) * 7},${240 + (u + v) * 3.1 - height}`;
  };
  const route = Array.from({ length: 61 }, (_, i) => {
    const t = i / 60;
    return `${i ? "L" : "M"}${point(-13 * (1 - t), 9 * (1 - t) + Math.sin(t * Math.PI * 3) * 2 * (1 - t))}`;
  }).join(" ");
  return (
    <div className="optimization-landscape" aria-hidden="true">
      <div className="landscape-aura" />
      <svg viewBox="0 0 500 380" className="landscape-surface" focusable="false">
        <defs>
          <linearGradient id="terrain-fill" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#eceef0" stopOpacity=".88" />
            <stop offset="50%" stopColor="#aeb4bc" stopOpacity=".74" />
            <stop offset="100%" stopColor="#787f89" stopOpacity=".56" />
          </linearGradient>
          <filter id="point-glow" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        <ellipse cx="250" cy="308" rx="160" ry="30" fill="#626973" opacity=".09" />
        {Array.from({ length: 28 }, (_, i) => {
          const v = i - 14;
          const points = [
            ...Array.from({ length: 29 }, (_, j) => point(j - 14, v)),
            ...Array.from({ length: 29 }, (_, j) => point(14 - j, v + 1)),
          ].join(" ");
          return <polygon key={i} points={points} fill="url(#terrain-fill)" stroke="#ffffff" strokeOpacity=".45" strokeWidth=".65" />;
        })}
        {Array.from({ length: 15 }, (_, i) => (
          <polyline key={i} points={Array.from({ length: 29 }, (_, j) => point(i * 2 - 14, j - 14)).join(" ")}
            fill="none" stroke="#404853" strokeOpacity=".22" strokeWidth=".7" />
        ))}
        <path d={route} fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity=".9" />
        <circle r="11" fill="#fff" filter="url(#point-glow)" className="solver-dot" style={{ offsetPath: `path('${route}')` }} />
        <circle r="4.5" fill="#fff" stroke="#343a42" strokeWidth="1.5" className="solver-dot" style={{ offsetPath: `path('${route}')` }} />
      </svg>
    </div>
  );
}

export function Header() {
  return (
    <header>
      <Link className="brand" href="/">
        <span className="brand-icon">◔</span> Winner Signal
      </Link>
      <nav>
        <Link href="/">Discover</Link>
        <Link href="/dashboard">Your workspace</Link>
        <Link className="button compact" href="/submit">
          Share a demo
        </Link>
      </nav>
    </header>
  );
}
function ErrorBox({ error }: { error: string }) {
  return error ? (
    <p className="notice error" role="alert">
      {error}
    </p>
  ) : null;
}
function Loading() {
  return <p className="notice">Loading…</p>;
}
function UserGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<{ username: string } | null | undefined>();
  useEffect(() => {
    api<{ username: string } | null>("/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  if (user === undefined) return <Loading />;
  if (!user)
    return (
      <div className="empty">
        <h1>Your builder workspace</h1>
        <p>Sign in to manage demos, private reviews, and playback analytics.</p>
        <Link className="button" href="/login">
          Sign in or create account
        </Link>
      </div>
    );
  return (
    <>
      <div className="account">
        Signed in as {user.username}
        <button
          className="text-button"
          onClick={async () => {
            await post("/auth/logout");
            router.push("/");
          }}
        >
          Sign out
        </button>
      </div>
      {children}
    </>
  );
}
export function Player({
  version,
  binding,
  diagnostic = false,
}: {
  version: Version;
  binding: Binding | null;
  diagnostic?: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const bindingId = binding?.id;
  useEffect(() => {
    if (ref.current && bindingId) {
      const p = new InstrumentedPlayer(
        ref.current,
        version.id,
        bindingId,
        diagnostic,
      );
      return () => p.destroy();
    }
  }, [version.id, bindingId, diagnostic]);
  let youtubeId: string | null = null;
  try {
    const url = new URL(version.video_source_url || "");
    const host = url.hostname.toLowerCase();
    const candidate = host === "youtu.be" ? url.pathname.slice(1) :
      ["youtube.com", "www.youtube.com", "m.youtube.com"].includes(host) ?
        (url.pathname === "/watch" ? url.searchParams.get("v") : /^\/(?:shorts|embed)\/([^/]+)$/.exec(url.pathname)?.[1]) : null;
    if (candidate && /^[A-Za-z0-9_-]{11}$/.test(candidate)) youtubeId = candidate;
  } catch { /* Other hosted videos retain their original link. */ }
  if (!version.video_asset_id && youtubeId) return (
    <div>
      <iframe
        key={youtubeId}
        title="Demo video on YouTube"
        src={`https://www.youtube-nocookie.com/embed/${youtubeId}?playsinline=1`}
        style={{width: "100%", aspectRatio: "16 / 9", minHeight: 200, border: 0}}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
      />
      <p><a href={version.video_source_url!} target="_blank" rel="noreferrer">Open on YouTube ↗</a></p>
    </div>
  );
  if (!version.video_asset_id)
    return (
      <div className="unavailable">
        <p>Watch the demo on its original host.</p>
        {version.video_source_url && (
          <a
            className="button secondary"
            href={version.video_source_url}
            target="_blank"
            rel="noreferrer"
          >
            Open original video
          </a>
        )}
      </div>
    );
  return (
    <video
      ref={ref}
      className="player"
      src={"/api/videos/" + version.video_asset_id}
      controls
      preload="metadata"
      playsInline
      aria-label="Demo video"
    />
  );
}
export function Gallery() {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("discovery");
  useEffect(() => {
    api<Card[]>("/gallery?sort=" + sort + "&seed=" + sessionId())
      .then(setCards)
      .catch((e) => setError(message(e)));
  }, [sort]);
  return (
    <>
      <section className="hero">
        <div>
          <h1>
            Real-world signals.
            <br />Better AI.
          </h1>
          <p>
            Connect AI-assisted work to evidence that its outputs function, get
            used, and create value—developing better signals for AI evaluation
            and training beyond benchmark pass rates.
          </p>
          <Link className="button" href="/submit">
            Share your demo
          </Link>
        </div>
        <OptimizationLandscape />
      </section>
      <div className="section-heading">
        <h2>Discover demos</h2>
        <label className="sort">
          Browse{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="discovery">Rotating discovery</option>
            <option value="newest">Newest first</option>
          </select>
        </label>
      </div>
      <ErrorBox error={error} />
      {!cards && !error ? (
        <Loading />
      ) : cards?.length ? (
        <div className="gallery">
          {cards.map((c) => (
            <Link className="demo-card" href={"/d/" + c.slug} key={c.slug}>
              <div className="thumbnail">
                {c.version.video_asset_id ? (
                  <video
                    src={"/api/videos/" + c.version.video_asset_id + "#t=0.1"}
                    preload="metadata"
                    muted
                  />
                ) : (
                  <span className="video-placeholder">▶</span>
                )}
                <span className="watch">Watch demo ↗</span>
                {!!c.version.is_fixture && (
                  <span className="example">Controlled example</span>
                )}
              </div>
              <div className="card-body">
                <h3>{c.title}</h3>
                <p>{c.description}</p>
                <div className="card-meta">
                  <span>{c.builder_display_name}</span>
                  <span>Version {c.version.version_number}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        !error && (
          <div className="empty">
            <h3>The first demo starts here.</h3>
            <p>Share your demo link and code to start gathering feedback.</p>
            <Link href="/submit">Add your demo</Link>
          </div>
        )
      )}
    </>
  );
}
export function Login({
  nextPath = "/dashboard",
  oauthError = false,
}: {
  nextPath?: string;
  oauthError?: boolean;
}) {
  const router = useRouter();
  const [googleReady, setGoogleReady] = useState(false);
  useEffect(() => {
    api<{ configured: boolean }>("/auth/google/status")
      .then((r) => setGoogleReady(r.configured))
      .catch(() => {});
  }, []);
  const [mode, setMode] = useState("login");
  const [error, setError] = useState(
    oauthError
      ? "Google sign-in wasn’t completed. Try again or use a username below."
      : "",
  );
  const [busy, setBusy] = useState(false);
  return (
    <section className="form-panel">
      <h1>{mode === "login" ? "Welcome back." : "Make room for your demo."}</h1>
      <p>
        Sign in and connect YouTube analytics with the same Google account.
        You can decline analytics access or connect a different uploader later.
      </p>
      {googleReady ? (
        <a
          className="button"
          href={"/api/auth/google?next=" + encodeURIComponent(nextPath)}
        >
          Continue with Google
        </a>
      ) : (
        <p className="notice">
          Google sign-in is awaiting setup. You can use a username now.
        </p>
      )}
      <p>Or use a username and password</p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const f = new FormData(e.currentTarget);
          try {
            await post("/auth/" + mode, {
              username: f.get("username"),
              password: f.get("password"),
            });
            router.push(nextPath);
          } catch (err) {
            setError(message(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Username
          <input
            name="username"
            required
            minLength={3}
            maxLength={40}
            pattern="[a-zA-Z0-9_-]+"
            autoComplete="username"
          />
        </label>
        <label>
          Password
          <input
            name="password"
            required
            minLength={10}
            type="password"
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
          />
        </label>
        <ErrorBox error={error} />
        <button disabled={busy}>
          {busy
            ? "Please wait…"
            : mode === "login"
              ? "Sign in"
              : "Create account"}
        </button>
      </form>
      <button
        className="text-button"
        onClick={() => setMode(mode === "login" ? "register" : "login")}
      >
        {mode === "login"
          ? "New here? Create an account"
          : "Already have an account? Sign in"}
      </button>
    </section>
  );
}
export function Submit({ projectId }: { projectId?: string }) {
  return (
    <UserGate>
      <SubmissionForm projectId={projectId} />
    </UserGate>
  );
}
function SubmissionForm({ projectId }: { projectId?: string }) {
  const router = useRouter();
  const [originalLink, setOriginalLink] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState("");
  const draft = useRef<string | null>(projectId || null);
  const version = useRef<Version | null>(null);
  return (
    <section className="form-panel wide submission">
      <h1>
        {projectId
          ? "A new version. A fresh signal."
          : "Give your demo an audience."}
      </h1>
      <p>
        Add your video link and public code. No video upload needed.
      </p>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const f = new FormData(e.currentTarget);
          try {
            setStage("Creating your private draft…");
            if (!draft.current) {
              const p = await post<Project>("/projects", {
                title: f.get("title"),
                description: f.get("description"),
              });
              draft.current = p.id;
            }
            setStage("Pinning the public repository…");
            if (!version.current)
              version.current = await post<Version>(
                "/projects/" + draft.current + "/versions",
                {
                  repository_url: f.get("repository"),
                  video_source_url: f.get("original"),
                  live_demo_url: f.get("live"),
                },
              );
            router.push("/dashboard/" + draft.current);
          } catch (err) {
            setError(message(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label className="demo-link-field">
          Demo video link
          <input name="original" value={originalLink}
            onChange={(e) => setOriginalLink(e.target.value)}
            type="url" required placeholder="https://www.youtube.com/watch?v=…" />
          <span>Paste a YouTube or other hosted demo link.</span>
        </label>
        <div className="channel-connection">
          <YouTubeConnection
            next={projectId ? "/dashboard/" + projectId : "/submit"}
            onSelect={setOriginalLink}
          />
        </div>
        {!projectId && (
          <>
            <label>
              Project name
              <input
                name="title"
                required
                maxLength={120}
                placeholder="What did you build?"
              />
            </label>
            <label>
              One-line description
              <textarea
                name="description"
                required
                maxLength={4000}
                placeholder="Who is it for, and what does it do?"
              />
            </label>
          </>
        )}
        <label>
          Public GitHub repository
          <input
            name="repository"
            type="url"
            required
            placeholder="https://github.com/you/project"
          />
        </label>
        <label>
          Live app link <span>Optional</span>
          <input name="live" type="url" placeholder="https://…" />
        </label>
        <aside className="notice">
          <strong>Prompts &amp; agent session history <span className="muted">Optional</span></strong>
          <p>After saving your draft, open <strong>Private evidence review → Optional build history</strong> in your workspace. Copy the export prompt into your coding agent to find and export this project’s session, then upload JSON, JSONL, Markdown, or text.</p>
          <p>Your export can include the prompts, edits, tool results, and tests behind the build. Review it for secrets before uploading. History stays private and is included in a Gemini review only when you choose.</p>
        </aside>
        <ErrorBox error={error} />
        <button disabled={busy}>{busy ? stage : "Save private draft"}</button>
      </form>
      <p className="muted">
        Nothing is public until you choose Publish in your workspace.
      </p>
    </section>
  );
}
export function Workspace() {
  return (
    <UserGate>
      <Projects />
    </UserGate>
  );
}
function Projects() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Project[]>("/my-projects")
      .then(setProjects)
      .catch((e) => setError(message(e)));
  }, []);
  return (
    <>
      <div className="section-heading">
        <div>
          <h1>Your workspace</h1>
          <p>Bring the next version into focus.</p>
        </div>
        <div className="row">
          <button
            className="secondary"
            onClick={async () => {
              try {
                const r = await post<{ project_id: string }>("/examples");
                router.push("/dashboard/" + r.project_id);
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            Try a controlled example
          </button>
          <Link className="button" href="/submit">
            Add a demo
          </Link>
        </div>
      </div>
      <ErrorBox error={error} />
      {projects === null ? (
        <Loading />
      ) : projects.length ? (
        <div className="project-list">
          {projects.map((p) => (
            <Link key={p.id} href={"/dashboard/" + p.id}>
              <div>
                <h2>{p.title}</h2>
                <p>{p.description}</p>
              </div>
              <span className="pill">{p.visibility}</span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty">
          <h2>Your first demo is waiting.</h2>
          <p>Start with your video and public repository.</p>
        </div>
      )}
    </>
  );
}
function ShareDemoLink({ slug }: { slug: string }) {
  const [copied, setCopied] = useState(false);
  const [fallback, setFallback] = useState("");
  return <div>
    <button className="secondary" onClick={async () => {
      const url = new URL("/d/" + encodeURIComponent(slug), window.location.origin).href;
      try { await navigator.clipboard.writeText(url); setCopied(true); setFallback(""); }
      catch { setFallback(url); }
    }}>{copied ? "Link copied ✓" : "Copy demo link"}</button>
    <span className="muted" role="status">{copied ? " Ready to share" : ""}</span>
    {fallback && <label>Copy this public URL<input aria-label="Public demo URL" readOnly value={fallback} onFocus={(event) => event.currentTarget.select()} /></label>}
  </div>;
}

export function DemoPage({ slug }: { slug: string }) {
  const [demo, setDemo] = useState<Demo | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(
    () => api<Demo>("/demos/" + encodeURIComponent(slug)).then(setDemo),
    [slug],
  );
  useEffect(() => {
    let active = true;
    api<Demo>("/demos/" + encodeURIComponent(slug))
      .then((d) => {
        if (active) {
          setDemo(d);
          track(d.version.id, "page_view", d.is_owner);
        }
      })
      .catch((e) => setError(message(e)));
    return () => {
      active = false;
      void flush();
    };
  }, [slug]);
  if (!demo) return error ? <ErrorBox error={error} /> : <Loading />;
  return (
    <article className="demo-detail">
      <Link href="/" className="back">
        All demos
      </Link>
      <div className="section-heading">
        <div>
          <h1>{demo.title}</h1>
          <p>{demo.description}</p>
        </div>
        <div className="row"><span className="pill">Version {demo.version.version_number}</span><ShareDemoLink slug={slug} /></div>
      </div>
      {!!demo.version.is_fixture && (
        <p className="notice">
          Controlled example. This is fixture content; its traffic is excluded
          from audience metrics.
        </p>
      )}
      <Player
        version={demo.version}
        binding={demo.binding}
        diagnostic={demo.is_owner}
      />
      <div className="demo-actions">
        <span>Built by {demo.builder_display_name}</span>
        <a
          href={
            demo.version.is_fixture
              ? "/api/examples/source"
              : demo.version.repository_url + "/tree/" + demo.version.commit_sha
          }
          target="_blank"
          rel="noreferrer"
          onClick={() => track(demo.version.id, "github_click", demo.is_owner)}
        >
          Explore the code ↗
        </a>
        {demo.version.live_demo_url && (
          <a
            href={demo.version.live_demo_url}
            target="_blank"
            rel="noreferrer"
            onClick={() =>
              track(demo.version.id, "livedemo_click", demo.is_owner)
            }
          >
            Try the app ↗
          </a>
        )}
        <button
          className="secondary"
          onClick={async () => {
            try {
              await api("/versions/" + demo.version.id + "/feedback", {
                method: "POST",
                headers: { "X-Session-Id": sessionId() },
                body: JSON.stringify({ kind: "use_this" }),
              });
              setNotice("Interest recorded. Thanks for the signal.");
            } catch (e) {
              setError(message(e));
            }
          }}
        >
          I’d use this
        </button>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <section className="feedback">
        <h2>Help the next version</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const f = new FormData(form);
            try {
              await api("/versions/" + demo.version.id + "/feedback", {
                method: "POST",
                headers: { "X-Session-Id": sessionId() },
                body: JSON.stringify({
                  kind: f.get("kind"),
                  text: f.get("text"),
                }),
              });
              form.reset();
              await load();
            } catch (err) {
              setError(message(err));
            }
          }}
        >
          <label>
            Your feedback
            <select name="kind">
              <option value="feedback">Suggestion</option>
              <option value="question">Question</option>
            </select>
            <textarea
              name="text"
              required
              maxLength={2000}
              placeholder="What was clear? What would you like to see next?"
            />
          </label>
          <button>Post feedback</button>
        </form>
        {demo.feedback.map((f) => (
          <div className="feedback-row" key={f.id}>
            <span className="pill">{f.kind}</span>
            <p>{f.text}</p>
            <button
              className="text-button"
              onClick={async () => {
                await post("/feedback/" + f.id + "/report");
                await load();
              }}
            >
              Report
            </button>
          </div>
        ))}
      </section>
    </article>
  );
}

const exportPrompt = `Export only this project's current coding-agent conversation as JSON, JSONL, Markdown or text into a local winner-signal-export folder. Find the actual documented session location; do not guess or reconstruct messages. Preserve available timestamps, roles, edits, tool results and tests. Exclude hidden reasoning, internal instructions, credentials and unrelated conversations. Redact secrets in the copy, leave originals untouched, and do not upload anything. Include a README with source, session ID, date range, completeness and omissions. Show me the files so I can review before sharing.`;
export function Dashboard({ id }: { id: string }) {
  return (
    <UserGate>
      <DashboardBody id={id} />
    </UserGate>
  );
}
function DashboardBody({ id }: { id: string }) {
  const [project, setProject] = useState<Project | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [selected, setSelected] = useState("");
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<Review | null>(null);
  const [histories, setHistories] = useState<
    { id: string; preview: string; redaction_status: string }[]
  >([]);
  const [includeHistory, setIncludeHistory] = useState(false);
  const [historyText, setHistoryText] = useState("");
  const [health, setHealth] = useState<{
    analysis_configured: boolean;
    model: string;
  } | null>(null);
  const [newVersion, setNewVersion] = useState(false);
  const load = useCallback(async () => {
    const [p, v, h] = await Promise.all([
      api<Project>("/projects/" + id),
      api<Version[]>("/projects/" + id + "/versions"),
      api<{ analysis_configured: boolean; model: string }>("/health"),
    ]);
    setProject(p);
    setVersions(v);
    setHealth(h);
    setSelected((old) => old || v[0]?.id || "");
  }, [id]);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<Project>("/projects/" + id),
      api<Version[]>("/projects/" + id + "/versions"),
      api<{ analysis_configured: boolean; model: string }>("/health"),
    ])
      .then(([p, v, h]) => {
        if (active) {
          setProject(p);
          setVersions(v);
          setHealth(h);
          setSelected(v[0]?.id || "");
        }
      })
      .catch((e) => setError(message(e)));
    return () => {
      active = false;
    };
  }, [id]);
  const refresh = useCallback(async () => {
    if (!selected) return;
    const a = await api<Analytics>(
      "/projects/" + id + "/analytics?version_id=" + selected,
    );
    setData(a);
    setHistories(await api("/versions/" + selected + "/history"));
    if (a.latest_run) setReview(await api("/analysis/" + a.latest_run.id));
    else setReview(null);
  }, [id, selected]);
  useEffect(() => {
    let active = true;
    const run = () => {
      if (active) refresh().catch((e) => setError(message(e)));
    };
    run();
    const t = setInterval(run, 5000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [refresh]);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  const v = versions.find((x) => x.id === selected);
  if (!project) return error ? <ErrorBox error={error} /> : <Loading />;
  if (newVersion)
    return (
      <>
        <button className="text-button" onClick={() => setNewVersion(false)}>
          Back to dashboard
        </button>
        <SubmissionForm projectId={id} />
      </>
    );
  return (
    <>
      <div className="section-heading">
        <div>
          <h1>{project.title}</h1>
          <p>Your audience and evidence, side by side.</p>
        </div>
        <div className="row">
          <button className="secondary" onClick={() => setNewVersion(true)}>
            New version
          </button>
          {project.published_version_id ? (
            <><Link className="button" href={"/d/" + project.slug}>Public demo ↗</Link><ShareDemoLink slug={project.slug} /></>
          ) : <span className="muted">Publish your demo to get a shareable link.</span>}
        </div>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="version-bar">
        <label>
          Review version
          <select
            value={selected}
            onChange={(e) => {
              setSelected(e.target.value);
              setData(null);
              setReview(null);
            }}
          >
            {versions.map((x) => (
              <option key={x.id} value={x.id}>
                Version {x.version_number}
                {x.id === project.published_version_id
                  ? " · published"
                  : " · private"}
              </option>
            ))}
          </select>
        </label>
        <button className="text-button" onClick={() => void refresh()}>
          Refresh metrics
        </button>
      </div>
      {!v ? (
        <div className="empty">
          <p>Add a version with a public repository and demo video.</p>
          <button onClick={() => setNewVersion(true)}>Add version</button>
        </div>
      ) : (
        <>
          <div className="workspace-grid">
            <section>
              <h2>Preview and publish</h2>
              <Player
                key={v.id}
                version={v}
                binding={data?.binding || null}
                diagnostic
              />
              <p className="muted">
                Preview plays are diagnostic and excluded from audience counts.{" "}
                {v.is_fixture ? (
                  "Controlled source fixture."
                ) : (
                  <>
                    Code pinned to <code>{v.commit_sha?.slice(0, 8)}</code>.
                  </>
                )}
              </p>
              <div className="row">
                {v.video_asset_id && <button
                  className="secondary"
                  disabled={busy || !v.video_asset_id}
                  onClick={() =>
                    void act(async () => {
                      const r = await post<{ verified: boolean }>(
                        "/versions/" + v.id + "/analytics/verify",
                      );
                      setNotice(
                        r.verified
                          ? "Playback tracking verified from persisted preview events."
                          : "Play the preview for a few seconds, then verify again.",
                      );
                      await refresh();
                    })
                  }
                >
                  Verify tracking
                </button>}
                {v.id !== project.published_version_id && (
                  <button
                    disabled={
                      busy || (!v.video_asset_id && !v.video_source_url)
                    }
                    onClick={() =>
                      void act(async () => {
                        if (
                          !confirm(
                            "Publish this video, description and repository link? Your histories and reviews stay private.",
                          )
                        )
                          return;
                        await post("/projects/" + id + "/publish", {
                          version_id: v.id,
                          consent: true,
                        });
                        await load();
                        setNotice(
                          "Published. Share your public demo page to bring viewers here.",
                        );
                      })
                    }
                  >
                    Publish this version
                  </button>
                )}
              </div>
            </section>
            <section className="audience">
              <h2>Video audience</h2>
              <p className="muted">Today, Pacific time · Demo video data only</p>
              <YouTubeAnalytics key={v.id} versionId={v.id} projectId={id} />
            </section>
          </div>
          {project.slug === "winner-signal-19daa4" && <section className="panel" aria-labelledby="feedback-trace-heading">
            <div className="section-heading">
              <div><h2 id="feedback-trace-heading">Video response → agent trajectory</h2><p>Follow a viewing signal back to the implementation behind a demo claim.</p></div>
              <span className="pill">SIMULATED SCENES + VIEWING DATA</span>
            </div>
            <p className="notice">A fictional 90-second product walkthrough, with invented scenes, narration, retention, and replay events. This is a storyboard, not an uploaded or analyzed video. It is independent of our submitted recordings. Linked code and build checkpoints are real; the connections are illustrative hypotheses.</p>
            <div className="row" style={{ flexWrap: "wrap", gap: "2rem" }}>
              <div><strong>100</strong><p className="muted">Simulated starts</p></div>
              <div><strong>46 / 100</strong><p className="muted">Simulated viewers reaching the end</p></div>
              <div><strong>18</strong><p className="muted">Simulated replay events at 30–45s</p></div>
            </div>
            <h3>Fictional video · “From build to evidence” · 01:30</h3>
            <p><strong>00:00–00:15:</strong> Introduce a project and its demo. <strong>00:15–00:30:</strong> Connect the uploader account. <strong>00:30–01:00:</strong> Open a finding, its source code, and its agent trace. <strong>01:00–01:30:</strong> Show a review failure, retry, and the completed report.</p>
            <h3>Illustrative audience retention</h3>
            <p className="muted">Viewers remaining from 100 simulated starts; replay events are counted separately.</p>
            {[{time: "0s", value: 100}, {time: "15s", value: 92}, {time: "30s", value: 75}, {time: "45s", value: 71}, {time: "60s", value: 63}, {time: "75s", value: 51}, {time: "90s", value: 46}].map((point) => <div key={point.time} style={{ display: "grid", gridTemplateColumns: "3rem 1fr 3rem", gap: "1rem", alignItems: "center", marginBlock: ".6rem" }}>
              <span>{point.time}</span><div style={{ background: "#e5e7eb", height: "12px" }}><div style={{ width: `${point.value}%`, background: "#52525b", height: "100%" }} /></div><span>{point.value}%</span>
            </div>)}
            {[
              {
                title: "Replay cluster → inspect claim-to-code grounding",
                time: "00:30–00:45",
                metric: "SIMULATED · 18 replay events at 00:30–00:45; retention 75% → 71%",
                moment: "Scene: a builder opens a review finding, selects its source citation, and expands the agent’s original action. Narration: “Follow this claim into the code and the build step that produced it.”",
                action: "The actual build added timestamp and source-line validation. Commit 698857b added structured actor/action/outcome findings with exact trace quotations.",
                commit: "698857b",
                file: "services/analysis/analysis/gemini_analyzer.py",
                hypothesis: "Replays could reflect interest or confusion about the evidence chain. Compare a concise citation walkthrough with a longer one, then measure whether viewers can locate the supporting source.",
                boundary: "This scene is invented to illustrate the real trace-grounding implementation. No replay events were observed, and no causal contribution is assigned to the agent.",
              },
              {
                title: "Retention drop → inspect the account-to-report path",
                time: "00:15–00:30",
                metric: "SIMULATED · 17 of 100 starting viewers leave between 00:15 and 00:30",
                moment: "Scene: the builder signs in, sees that the video belongs to another account, and opens the optional uploader connection. Narration: “Use the account that owns this video.”",
                action: "The build history records OAuth failures followed by a repair and passing tests. The implementation connects the sign-in account, supports a different uploader, and requests video-scoped reports.",
                commit: "6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95",
                file: "services/analysis/analysis/google_oauth.py",
                hypothesis: "The account switch may interrupt the story. Inspect the existing connection fallback, then compare a shorter explanation with a full account-switch walkthrough.",
                boundary: "The depicted account mismatch and audience drop are fictional. This is a connection to relevant code, not evidence of a real OAuth defect or agent failure.",
              },
              {
                title: "Ending losses → inspect review recovery",
                time: "01:00–01:30",
                metric: "SIMULATED · 63% remain at 01:00; 46% reach the end at 01:30",
                moment: "Scene: a review shows a response-format failure, the builder retries, and a completed evidence report appears. Narration: “The recovered review links each finding to its source.”",
                action: "The actual coding history includes a combined live review failing JSON parsing. The agent bounded response size and added diagnostics; the recorded rerun produced five claims, six trace findings, and a verified seal.",
                commit: "b53f633",
                file: "services/analysis/analysis/gemini_analyzer.py",
                hypothesis: "The recovery sequence may delay the payoff. Compare a result-first edit with a failure-and-recovery edit under similar traffic, then check whether viewers understand the evidence.",
                boundary: "The on-screen recovery is a fictional storyboard inspired by real development history. It does not claim that a user encountered this sequence or that a production retry was observed.",
              },
            ].map((finding) => <article className="claim" key={finding.title}>
              <div className="row"><h3>{finding.title}</h3><span className="pill">Hypothesis · curated match</span></div>
              <p><strong>{finding.metric}</strong></p>
              <div className="notice"><span className="timestamp">{finding.time} · Fictional scene</span><p>{finding.moment}</p></div>
              <p><strong>Matched agent trajectory:</strong> {finding.action}</p>
              <p><a href={`https://github.com/LEE-CHENYU/winner-signal/blob/${finding.commit}/${finding.file}`} target="_blank" rel="noreferrer">Inspect pinned implementation ↗</a> · <a href={`https://github.com/LEE-CHENYU/winner-signal/commit/${finding.commit}`} target="_blank" rel="noreferrer">Inspect build change ↗</a></p>
              <p><strong>Next experiment:</strong> {finding.hypothesis}</p>
              <details><summary>Attribution boundary</summary><p>{finding.boundary}</p></details>
            </article>)}
            <p className="muted">Storyboard and viewing simulation only. No video file was generated. These examples never enter real reports, feedback totals, agent scores, or training datasets.</p>
          </section>}
          {project.slug === "winner-signal-19daa4" && <section className="panel" aria-labelledby="build-backtrace-heading">
            <div className="section-heading">
              <div><h2 id="build-backtrace-heading">This demo → our build trajectory</h2><p>Recorded decisions, implementation, failures, and follow-up fixes.</p></div>
              <span className="pill">Actual project history · curated</span>
            </div>
            <p>The video is pinned to <a href="https://github.com/LEE-CHENYU/winner-signal/tree/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95" target="_blank" rel="noreferrer">6f8aeb1</a>. Video times below come from the live Gemini review of the uploaded recording. History excerpts are selected from this project’s Codex session; they are not a complete replay.</p>
            <article className="claim">
              <div className="row"><a className="timestamp" href="https://youtu.be/m-gMjoL5yew?t=0" target="_blank" rel="noreferrer">00:00–00:31 · landing page</a><span className="pill">Visible in recording</span></div>
              <h3>Research goal and descending landscape</h3>
              <p>The recorded page follows the earlier requests to foreground real-world AI signals, use grey square-edged styling, and make the landscape descend.</p>
              <p><a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/apps/web/src/components/app.tsx" target="_blank" rel="noreferrer">Pinned landing-page implementation ↗</a></p>
              <details><summary>Recorded build checkpoint · 23:01:24 UTC</summary><blockquote>Live: Geist Sans, lighter headlines, grey palette, square corners, and an animation descending into a basin.</blockquote><p>Assistant status report, 2026-10-25. The recording visually supports the landing-page result; this is not an execution test of the backend.</p></details>
            </article>
            <article className="claim">
              <div className="row"><a className="timestamp" href="https://youtu.be/m-gMjoL5yew?t=6" target="_blank" rel="noreferrer">00:06–00:13.5 · Gemini reviews video + code</a><span className="pill">Narrated claim + implementation</span></div>
              <h3>A missing URL path became a working review pipeline</h3>
              <p>22:54 UTC: the audit found that new YouTube links could not trigger review. The agent added uploader/public-video checks and remote video input. At 22:59:10 UTC the recorded test output reported <strong>33 passed, 1 warning</strong>. A separate public-sample URL probe then succeeded.</p>
              <p><a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/services/analysis/analysis/gemini_analyzer.py#L97" target="_blank" rel="noreferrer">Pinned media review code ↗</a> · <a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/services/analysis/tests/test_linked_review.py" target="_blank" rel="noreferrer">Linked-review integration tests ↗</a></p>
              <details><summary>Recorded gap · 22:54:34 UTC</summary><blockquote>Gemini code review still requires an existing uploaded video asset—it doesn’t run on a new YouTube link yet.</blockquote><p>Assistant report from the original build session. The later integration test used a stubbed model; the live URL probe used Google’s public sample, not this recording.</p></details>
            </article>
            <article className="claim">
              <div className="row"><a className="timestamp" href="https://youtu.be/m-gMjoL5yew?t=13" target="_blank" rel="noreferrer">00:13.5–00:17.5 · claims compared with code</a><span className="pill">Code-supported; not shown running</span></div>
              <h3>Claims have timestamps and checked source references</h3>
              <p>The pinned validator rejects out-of-range video times and nonexistent source lines, constructs commit-specific links, and distinguishes visible observations from assertions. The demo narrates this capability but does not open a result.</p>
              <p><a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/services/analysis/analysis/gemini_analyzer.py#L45-L87" target="_blank" rel="noreferrer">Exact validator at the recorded revision ↗</a></p>
            </article>
            <article className="claim">
              <div className="row"><a className="timestamp" href="https://youtu.be/m-gMjoL5yew?t=17" target="_blank" rel="noreferrer">00:17.5–00:21 · audience response</a><span className="pill">Integration built; verification came later</span></div>
              <h3>Account connection was repaired before real reports were fetched</h3>
              <p>Recorded OAuth test output: <strong>3 failed, 23 passed</strong> at 22:49:11 UTC, followed by <strong>26 passed</strong> at 22:49:24 UTC. The same-account connection and separate-uploader fallback were then deployed. Real owner-authorized report retrieval was verified later, after this video was uploaded.</p>
              <p><a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/services/analysis/analysis/google_oauth.py" target="_blank" rel="noreferrer">Pinned OAuth implementation ↗</a> · <a href="https://github.com/LEE-CHENYU/winner-signal/blob/6f8aeb1c2c1d6abd42dabf457c4f7dbdac12fd95/services/analysis/analysis/youtube.py" target="_blank" rel="noreferrer">Video-scoped reports ↗</a></p>
            </article>
            <article className="claim">
              <div className="row"><span className="timestamp">After recording · 23:32–23:35 UTC</span><span className="pill">Later improvement</span></div>
              <h3>From history as context to cited agent actions</h3>
              <blockquote>what&apos;s important is video understanding and codebase and agent traces understanding make sure these are build</blockquote>
              <p>This human request at 23:32:12 UTC prompted an audit: history was only background text. Commit <a href="https://github.com/LEE-CHENYU/winner-signal/commit/698857b" target="_blank" rel="noreferrer">698857b</a> added structured actor/action/outcome findings and exact trace quotations.</p>
              <p>The first combined live run failed JSON parsing. After tightening the response, run <code>3772f476</code> succeeded at 23:35:35 UTC with <strong>5 video claims, 6 trace findings, and a verified evidence seal</strong>. It used this recording as an uploaded file, pinned code, and a curated build excerpt. The private receipt is retained locally.</p>
              <p><a href="https://github.com/LEE-CHENYU/winner-signal/commit/b53f633" target="_blank" rel="noreferrer">Follow-up response-size and failure-diagnostic fix ↗</a></p>
            </article>
            <p className="notice">The recording ends after “let me show you an example” (00:27.5–00:31). It does not show the review result. This backtrace connects recorded claims to build evidence; it does not establish that an agent action caused audience response.</p>
          </section>}
          <section className="panel">
            <h2>Private evidence review</h2>
            <p>
              Connect moments in your video to the exact code behind them.
              Source code supports a claim; it does not prove that code ran.
            </p>
            {!v.video_asset_id && (
              <p className="notice">Linked-video review requires a public YouTube demo up to two minutes and its uploader account connection. Private, unlisted, and other hosted links are not supported for review.</p>
            )}
            {!health?.analysis_configured && (
              <p className="notice">
                Live review is not enabled. Configure Gemini API access and cost
                limits on the server. Antigravity plan quota is not used by this
                app; the gallery and analytics work independently.
              </p>
            )}
            <section aria-labelledby="build-history-heading">
              <h3 id="build-history-heading">
                Build history <span className="muted">Optional · {histories.length} files</span>
              </h3>
              <p>
                Upload only selected, reviewed exports. Best-effort redaction is
                not a guarantee. Originals are not retained; the redacted text
                remains private.
              </p>
              <button
                className="secondary"
                onClick={() => {
                  navigator.clipboard
                    .writeText(exportPrompt)
                    .then(() => setNotice("Export prompt copied."))
                    .catch(() => setNotice(exportPrompt));
                }}
              >
                Copy agent export prompt
              </button>
              <label>
                Upload export
                <input
                  type="file"
                  accept=".json,.jsonl,.md,.txt"
                  disabled={busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file)
                      void act(async () => {
                        await upload("/versions/" + v.id + "/history", file);
                        await refresh();
                      });
                  }}
                />
              </label>
              <label>
                Or paste reviewed build history
                <textarea value={historyText} maxLength={1000000} onChange={(event) => setHistoryText(event.target.value)} placeholder="Paste selected prompts, agent messages, or tool results…" />
              </label>
              <button className="secondary" disabled={busy || !historyText.trim()} onClick={() => void act(async () => {
                await upload("/versions/" + v.id + "/history", new File([historyText], "pasted-build-history.txt", {type: "text/plain"}));
                setHistoryText("");
                await refresh();
                setNotice("Build history saved privately. Include it in a review only when you choose.");
              })}>Save pasted history</button>
              {histories.map((h) => (
                <div key={h.id}>
                  <p>{h.redaction_status}</p>
                  <pre className="history-preview">{h.preview}</pre>
                  <button
                    className="text-button"
                    onClick={() =>
                      void act(async () => {
                        await api("/versions/" + v.id + "/history/" + h.id, {
                          method: "DELETE",
                        });
                        await refresh();
                      })
                    }
                  >
                    Remove upload
                  </button>
                </div>
              ))}
              <p className="muted">
                Removing an upload stops future use; existing sealed reviews
                retain any snapshot you previously authorized.
              </p>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={includeHistory}
                  onChange={(e) => setIncludeHistory(e.target.checked)}
                />
                Include these redacted histories in the next Gemini review
              </label>
            </section>
            <button
              disabled={
                busy ||
                (!v.video_asset_id && !v.video_source_url) ||
                !health?.analysis_configured ||
                ["queued", "running"].includes(review?.run.status || "")
              }
              onClick={() =>
                void act(async () => {
                  if (
                    !confirm(
                      "Send this demo video (or its public YouTube URL), bounded public source snapshot" +
                        (includeHistory
                          ? " and selected redacted histories"
                          : "") +
                        " to Gemini for review?",
                    )
                  )
                    return;
                  await post("/versions/" + v.id + "/analyze", {
                    consent: true,
                    include_history: includeHistory,
                  });
                  await refresh();
                })
              }
            >
              Run evidence review
            </button>
            {review && (
              <div className="review">
                <p className="status">
                  {review.run.mode === "fixture" ? "Controlled fixture · " : ""}
                  {review.run.status} · {review.run.model_id}
                </p>
                {review.run.failure_code && (
                  <p className="notice error">
                    Review failed: {review.run.failure_code}. No successful
                    review was produced. Check provider access or quota, then
                    start a new attempt.
                  </p>
                )}
                {review.result && (
                  <>
                    <h3>{review.result.summary}</h3>
                    {review.result.claims.map((c, i) => (
                      <article className="claim" key={i}>
                        <div className="row">
                          <span className="timestamp">
                            {(c.video_start_ms / 1000).toFixed(1)}–
                            {(c.video_end_ms / 1000).toFixed(1)}s
                          </span>
                          <span className="pill">
                            {c.evidence_state.replaceAll("_", " ")}
                          </span>
                        </div>
                        <h3>{c.text}</h3>
                        <p>{c.explanation}</p>
                        {c.evidence.map((e, j) => (
                          <div className="source" key={j}>
                            <a href={e.url} target="_blank" rel="noreferrer">
                              {e.file_path}:{e.start_line}–{e.end_line} ↗
                            </a>
                            <span>{e.relation}</span>
                            <p>{e.explanation}</p>
                          </div>
                        ))}
                      </article>
                    ))}
                    <h3>Agent build trace</h3>
                    <p>Participant-supplied records. These show reported actions and outcomes, not independently verified execution.</p>
                    {!review.result.trace_findings?.length && <p>{review.result.trace_status === "no_supported_findings" ? "No trace findings with valid supporting excerpts were returned." : "No agent trace findings are available for this review. Upload build history and include it in a new review to assess the building process."}</p>}
                    {review.result.trace_findings?.map((t, i) => (
                      <article className="claim" key={i}>
                        <div className="row"><span className="pill">{t.actor}</span><span>{t.outcome_status.replaceAll("_", " ")}</span></div>
                        <h4>{t.action}</h4>
                        <p>{t.outcome}</p><p>{t.assessment}</p>
                        <details><summary>Trace evidence · {t.artifact_id.slice(0, 8)} · characters {t.start_char}–{t.end_char}</summary><blockquote style={{whiteSpace: "pre-wrap"}}>{t.quote}</blockquote><p>Artifact SHA-256: <code>{t.artifact_sha256}</code></p></details>
                        {t.evidence.map((e, j) => <div className="source" key={j}><a href={e.url} target="_blank" rel="noreferrer">{e.file_path}:{e.start_line}–{e.end_line} ↗</a><span>{e.relation}</span><p>{e.explanation}</p></div>)}
                      </article>
                    ))}
                    <h3>Make the next version stronger</h3>
                    {review.result.improvements.map((r, i) => (
                      <article className="recommendation" key={i}>
                        <h4>{r.action}</h4>
                        <p>{r.rationale}</p>
                        <p>
                          <strong>Verify:</strong> {r.proposed_verification}
                        </p>
                      </article>
                    ))}
                    <details>
                      <summary>Coverage and limitations</summary>
                      {review.result.limitations.map((l, i) => (
                        <p key={i}>{l}</p>
                      ))}
                    </details>
                    <button
                      className="secondary"
                      onClick={() =>
                        void act(async () => {
                          const r = await api<{ verified: boolean }>(
                            "/analysis/" + review.run.id + "/evidence",
                          );
                          setNotice(
                            r.verified
                              ? "Evidence seal verified against stored artifacts and recorded root."
                              : "Evidence verification failed",
                          );
                        })
                      }
                    >
                      Verify evidence integrity
                    </button>
                  </>
                )}
              </div>
            )}
          </section>
          <section className="panel">
            <h2>Optional exported video report</h2>
            <details>
              <summary>Import an owner-provided analytics report</summary>
              <p>
                Use the normalized JSON format below. This is a manual,
                participant-supplied export—not a verified host API connection.
                Set an original video link when creating the version.
              </p>
              <pre>
                {JSON.stringify(
                  {
                    provider: "Your video host",
                    video_url:
                      v.video_source_url || "https://original-video-url",
                    period_start: "2026-10-25",
                    period_end: "2026-10-25",
                    metrics: { views: 0 },
                  },
                  null,
                  2,
                )}
              </pre>
              <input
                aria-label="Analytics JSON report"
                type="file"
                accept=".json"
                disabled={busy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f)
                    void act(async () => {
                      if (f.size > 100000)
                        throw Error("Report must be under 100 KB");
                      await post(
                        "/versions/" + v.id + "/analytics/import",
                        JSON.parse(await f.text()),
                      );
                      await refresh();
                      setNotice(
                        "Report imported as participant-supplied analytics.",
                      );
                    });
                }}
              />
            </details>
            {data?.reports.length ? (
              data.reports.map((r) => (
                <article className="source" key={r.id}>
                  <h3>{r.provider} · manual export</h3>
                  <p>
                    {r.period_start} to {r.period_end}
                  </p>
                  <pre>
                    {JSON.stringify(JSON.parse(r.metrics_json), null, 2)}
                  </pre>
                  <small>Imported {r.created_at}</small>
                  <button
                    className="text-button"
                    onClick={() =>
                      void act(async () => {
                        await api(
                          "/versions/" + v.id + "/analytics/import/" + r.id,
                          { method: "DELETE" },
                        );
                        await refresh();
                      })
                    }
                  >
                    Remove report
                  </button>
                </article>
              ))
            ) : (
              <p className="muted">
                No owner-exported report imported. Connected YouTube reports
                appear separately above.
              </p>
            )}
          </section>
          <section className="panel">
            <h2>Viewer feedback</h2>
            {data?.feedback
              .filter((f) => f.kind !== "use_this")
              .map((f) => (
                <div className="feedback-row" key={f.id}>
                  <span className="pill">{f.kind}</span>
                  <p>{f.text}</p>
                  <button
                    className="text-button"
                    onClick={() =>
                      void act(async () => {
                        await post("/feedback/" + f.id + "/report");
                        await refresh();
                      })
                    }
                  >
                    Hide / report
                  </button>
                </div>
              ))}
            {!data?.feedback.length && (
              <p className="muted">
                Share your public demo page to invite the first questions.
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}

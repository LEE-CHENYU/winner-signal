"use client";
import { useEffect, useState } from "react";
import { api, message } from "@/lib/api";

type Connection = {
  configured: boolean;
  connection: { channel_id: string; channel_title: string } | null;
};
export function YouTubeConnection({
  next,
  onSelect,
  onChange,
}: {
  next: string;
  onSelect?: (url: string) => void;
  onChange?: () => void;
}) {
  const [status, setStatus] = useState<Connection | null>(null);
  const [videos, setVideos] = useState<{ id: string; title: string }[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Connection>("/integrations/youtube")
      .then(setStatus)
      .catch((e) => setError(message(e)));
  }, []);
  return (
    <section className="youtube-connection">
      <h3>
        {onSelect
          ? "YouTube analytics"
          : "YouTube account for analytics"}
      </h3>
      <p>
        {status?.connection
          ? "Your channel is connected. Reports appear in your demo dashboard."
          : "Google sign-in connects analytics when you grant access. You can still add a demo without it."}
      </p>
      {status?.connection && (
        <p>
          Connected channel: <strong>{status.connection.channel_title}</strong>
        </p>
      )}
      <details className="account-options">
        <summary>Connect or change account <span>Optional</span></summary>
        <p>Only needed if you skipped analytics access or your demo uses another YouTube account.</p>
      {!status ? <p>Checking your channel…</p> : status.configured ? (
        <a
          className="button secondary"
          href={
            "/api/integrations/youtube/connect?next=" + encodeURIComponent(next)
          }
        >
          {status.connection
            ? "Connect a different YouTube account"
            : "Connect or switch YouTube account"}
        </a>
      ) : (
        <p>
          YouTube connection is awaiting Google setup. Add a video link below; no channel connection is required.
        </p>
      )}
      {status?.connection && (
        <>
          {onSelect && (
            <button
              type="button"
              className="secondary"
              onClick={async () => {
                try {
                  setVideos(await api("/integrations/youtube/videos"));
                  setError("");
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              Find my recent videos
            </button>
          )}
          <button
            type="button"
            className="text-button"
            onClick={async () => {
              try {
                await api("/integrations/youtube", { method: "DELETE" });
                setStatus({ ...status, connection: null });
                onChange?.();
                setVideos([]);
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            Disconnect analytics
          </button>
        </>
      )}
      {videos.length > 0 && (
        <label>
          Your recent uploads
          <select
            defaultValue=""
            onChange={(e) => {
              if (e.target.value)
                onSelect?.("https://www.youtube.com/watch?v=" + e.target.value);
            }}
          >
            <option value="">Choose a demo</option>
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.title}
              </option>
            ))}
          </select>
        </label>
      )}
      </details>
      {error && (
        <p role="alert">{error} You can still add the demo manually.</p>
      )}
    </section>
  );
}

type YoutubeReport = {
  status: string;
  channel_title?: string;
  latest_available_day?: string;
  fetched_at?: string;
  message?: string;
  daily?: {
    day: string;
    views: number;
    estimatedMinutesWatched: number;
    averageViewDuration: number;
    averageViewPercentage: number;
  }[];
};
export function YouTubeAnalytics({
  versionId,
  projectId,
}: {
  versionId: string;
  projectId: string;
}) {
  const [revision, setRevision] = useState(0);
  const [report, setReport] = useState<YoutubeReport | null>(null);
  useEffect(() => {
    let active = true;
    api<YoutubeReport>("/versions/" + versionId + "/youtube-analytics")
      .then((r) => {
        if (active) setReport(r);
      })
      .catch(() => {
        if (active) setReport({ status: "connection_error" });
      });
    return () => {
      active = false;
    };
  }, [versionId, revision]);
  return (
    <>
      <YouTubeConnection
        next={"/dashboard/" + projectId}
        onChange={() => {
          setReport(null);
          setRevision((n) => n + 1);
        }}
      />
      {!report ? (
        <p>Checking YouTube report…</p>
      ) : report.status === "connected" ? (
        <div>
          <p>
            <strong>From YouTube Analytics API</strong> · {report.channel_title}
          </p>
          <p>
            Data through {report.latest_available_day}. Last fetched{" "}
            {report.fetched_at?.slice(0, 16).replace("T", " ")} UTC. Updates
            when you open this dashboard, at most once every six hours.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Views</th>
                  <th>Watch minutes</th>
                  <th>Avg. seconds watched</th>
                  <th>Avg. % watched</th>
                </tr>
              </thead>
              <tbody>
                {report.daily?.map((row) => (
                  <tr key={row.day}>
                    <td>{row.day}</td>
                    <td>{row.views}</td>
                    <td>{row.estimatedMinutesWatched}</td>
                    <td>{row.averageViewDuration}</td>
                    <td>{row.averageViewPercentage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            YouTube views and averages use YouTube’s definitions. They are
            separate from Winner Signal playback coverage and completion.
          </p>
        </div>
      ) : (
        <p>
          {report.status === "different_channel"
            ? "This demo belongs to another channel. Connect its uploader account above, or keep the demo and use Winner Signal analytics."
            : report.status === "pending_data"
              ? "YouTube is connected, but no report rows are available yet. Reporting can be delayed; this does not mean zero views."
              : report.status === "not_youtube"
                ? "Add the original YouTube URL to a demo version to fetch its YouTube analytics."
                : report.status === "not_connected"
                  ? "YouTube analytics is optional. Connect the uploader account to fetch it automatically."
                  : report.message ||
                    "YouTube analytics is temporarily unavailable. Your demo and Winner Signal analytics remain available."}
        </p>
      )}
    </>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import {
  askQuery,
  clearAlertHits,
  createAlert,
  createWebSocket,
  deleteAlertRule,
  getAlerts,
  getVideoStatus,
  listEvents,
  uploadVideo,
} from "./api/client";
import type { AlertHit, AlertRule, AlertsState, Event, QueryResult, Video, VideoStatus } from "./types";
import { useSpeechRecognition } from "./hooks/useSpeechRecognition";

/* ──────────────────────────────────────────────────────────
   Chat types
   ────────────────────────────────────────────────────────── */

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  fallback?: boolean;
  events?: Event[];
};

type DictationTarget = "query" | "alert";

/* ──────────────────────────────────────────────────────────
   App
   ────────────────────────────────────────────────────────── */

export default function App() {
  const [video, setVideo] = useState<Video | null>(null);
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [alerts, setAlerts] = useState<AlertsState>({ rules: [], hits: [] });
  const [chat, setChat] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Hello! I'm Memora — your visual memory assistant. Upload a video and I'll watch, remember, and answer your questions about everything that happens.",
    },
  ]);
  const [query, setQuery] = useState("");
  const [alertText, setAlertText] = useState("");
  const [location, setLocation] = useState("Main Office");
  const [recordingStart, setRecordingStart] = useState(new Date().toISOString().split(".")[0]);
  const [busy, setBusy] = useState(false);
  const [voiceTarget, setVoiceTarget] = useState<DictationTarget>("query");
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState(Notification.permission);

  const fileInput = useRef<HTMLInputElement | null>(null);
  const pollingRef = useRef<number | null>(null);
  const lastHitIdRef = useRef<string | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const speech = useSpeechRecognition();
  const canDictate = speech.supported;

  const streaming = useMemo(() => {
    if (!status) return false;
    return status.status === "queued" || status.status === "processing";
  }, [status]);

  /* ── Effects ─────────────────────────────────────────── */

  useEffect(() => {
    void refreshAlerts();
  }, []);

  // Set up WebSocket for real-time updates
  useEffect(() => {
    const ws = createWebSocket((type, data) => {
      if (type === "new_event" && video && data.video_id === video.id) {
        // Trigger a refresh when a new event comes in
        void listEvents(video.id).then((evts) => setEvents(evts.reverse()));
      }
    });
    return () => {
      ws?.close();
    };
  }, [video?.id]);

  useEffect(() => {
    if (!video) return;
    if (pollingRef.current) window.clearInterval(pollingRef.current);
    const poll = async () => {
      try {
        const [nextStatus, nextEvents, nextAlerts] = await Promise.all([
          getVideoStatus(video.id),
          listEvents(video.id),
          getAlerts(),
        ]);
        setStatus(nextStatus);
        setEvents(nextEvents.reverse());

        if (nextAlerts.hits.length > 0) {
          const latestHit = nextAlerts.hits[0];
          if (latestHit.id !== lastHitIdRef.current) {
            notifyUser(latestHit);
            lastHitIdRef.current = latestHit.id;
          }
        }

        setAlerts(nextAlerts);
      } catch {
        // Keep last known state
      }
    };
    void poll();
    pollingRef.current = window.setInterval(poll, 2000);
    return () => {
      if (pollingRef.current) window.clearInterval(pollingRef.current);
    };
  }, [video, notificationPermission]);

  useEffect(() => {
    if (!speech.transcript) return;
    if (voiceTarget === "query") {
      setQuery(speech.transcript);
    } else {
      setAlertText(speech.transcript);
    }
  }, [speech.transcript, voiceTarget]);

  /* ── Handlers ────────────────────────────────────────── */

  const requestNotificationPermission = async () => {
    const permission = await Notification.requestPermission();
    setNotificationPermission(permission);
  };

  const notifyUser = (hit: AlertHit) => {
    if (notificationPermission === "granted") {
      new Notification("Memora Vision Alert", { body: hit.message });
    }
  };

  async function refreshAlerts() {
    try {
      const nextAlerts = await getAlerts();
      setAlerts(nextAlerts);
      if (nextAlerts.hits.length > 0) lastHitIdRef.current = nextAlerts.hits[0].id;
    } catch {
      /* backend starting */
    }
  }

  async function handleUpload() {
    const file = fileInput.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const response = await uploadVideo(file, location, recordingStart || new Date().toISOString());
      setVideo(response.video);
      setStatus({
        video_id: response.video.id,
        status: response.video.status,
        progress: response.video.progress,
        current_time_seconds: 0,
        event_count: 0,
        alert_count: 0,
      });
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `I'm now watching ${file.name}. I'll analyze every frame and build a complete memory of everything that happens. You can start asking me questions at any time.`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function handleQuery() {
    const question = query.trim();
    if (!question || busy) return;

    setBusy(true);
    setIsThinking(true);
    setQuery("");
    setChat((prev) => [...prev, { role: "user", text: question }]);

    try {
      const response = await askQuery(question, video?.id, conversationId ?? undefined);
      if (response.conversation_id) setConversationId(response.conversation_id);
      appendAnswer(response);
      if (speechEnabled) speak(response.answer);
    } catch {
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "I'm sorry, I had trouble processing that. Please check that the backend and GPU server are running.",
        },
      ]);
    } finally {
      setBusy(false);
      setIsThinking(false);
    }
  }

  async function handleCreateAlert() {
    const text = alertText.trim();
    if (!text) return;
    setBusy(true);
    try {
      await createAlert(text);
      setAlertText("");
      await refreshAlerts();
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteRule(ruleId: string) {
    if (confirm("Remove this monitoring rule?")) {
      await deleteAlertRule(ruleId);
      await refreshAlerts();
    }
  }

  async function handleClearHits() {
    if (confirm("Clear all recorded incidents?")) {
      await clearAlertHits();
      await refreshAlerts();
    }
  }

  function handleExportLogs() {
    if (alerts.hits.length === 0) return;
    const headers = ["Timestamp", "Location", "Alert Message"];
    const rows = alerts.hits.map((hit) => [
      `"${formatTimestamp(hit.timestamp_iso)}"`,
      `"${location}"`,
      `"${hit.message.replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `memora-report-${new Date().toLocaleDateString().replace(/\//g, "-")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function appendAnswer(response: QueryResult) {
    setChat((prev) => [
      ...prev,
      {
        role: "assistant",
        text: response.answer,
        fallback: response.used_fallback,
        events: response.supporting_events,
      },
    ]);
    if (response.supporting_events.length > 0) {
      seekTo(response.supporting_events[0].timestamp_seconds);
    }
  }

  function seekTo(seconds: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.pause();
    }
  }

  function speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  }

  function startDictation(target: DictationTarget) {
    setVoiceTarget(target);
    speech.setTranscript("");
    speech.start();
  }

  function handleQueryKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  }

  /* ── Render ──────────────────────────────────────────── */

  return (
    <div className="app-shell">
      <div className="app-inner">
        {/* ── Header ──────────────────────────────────── */}
        <header className="topbar">
          <div className="brand">
            <div className="brand-icon">🧠</div>
            <div>
              <h1>Memora Vision</h1>
              <p className="brand-sub">AI Visual Memory Assistant</p>
            </div>
          </div>
          <div className={`status-pill ${streaming ? "live" : ""}`}>
            {streaming ? "Analyzing Video" : "Ready"}
          </div>
        </header>

        {/* ── Main Grid ──────────────────────────────── */}
        <main className="grid">
          {/* ── Left: Video + Timeline ──────────────── */}
          <section className="panel video-panel">
            <div className="panel-header">
              <h2>📹 Video Source</h2>
            </div>

            {video?.video_url && (
              <div className="video-preview">
                <video
                  ref={videoRef}
                  src={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}${video.video_url}`}
                  controls
                  className="main-video"
                />
              </div>
            )}

            <div className="upload-card">
              <input ref={fileInput} type="file" accept="video/*" className="custom-file-input" />
              <div className="field-row">
                <label>
                  Area
                  <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Front Desk" />
                </label>
                <label>
                  Time
                  <input value={recordingStart} onChange={(e) => setRecordingStart(e.target.value)} placeholder="YYYY-MM-DD HH:MM" />
                </label>
              </div>
              <button onClick={handleUpload} disabled={busy}>
                {busy ? "Analyzing..." : "Start Analysis"}
              </button>
            </div>

            {status && (
              <div className="progress-block">
                <div className="progress-meta">
                  <span>Progress</span>
                  <span>{Math.round(status.progress * 100)}%</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${Math.max(2, Math.round(status.progress * 100))}%` }} />
                </div>
                <div className="status-grid">
                  <Metric label="Events" value={String(status.event_count)} />
                  <Metric label="Alerts" value={String(status.alert_count)} />
                  <Metric label="File" value={video?.filename ?? "—"} />
                  <Metric label="Time" value={formatSeconds(status.current_time_seconds)} />
                </div>
                {status.error && <p className="error-copy">Error: {status.error}</p>}
              </div>
            )}
          </section>

          <section className="panel timeline-panel">
            <div className="panel-header">
              <h2>📋 Activity Timeline</h2>
              <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>{events.length} events</span>
            </div>
            <div className="timeline-list">
              {events.length === 0 ? (
                <EmptyState title="No activity yet" description="Upload a video to see the timeline." />
              ) : (
                events.map((event) => (
                  <article className="event-card" key={event.id} onClick={() => seekTo(event.timestamp_seconds)}>
                    <div className="event-topline">
                      <strong>{formatTimestamp(event.timestamp_iso)}</strong>
                      <span className="location-tag">{event.location}</span>
                    </div>
                    <p className="event-caption">{event.caption}</p>
                    <div className="tag-row">
                      {event.objects.map((obj) => (
                        <span className="tag" key={obj}>{obj}</span>
                      ))}
                      {event.activity_tags?.map((tag) => (
                        <span className="tag activity" key={tag}>{tag}</span>
                      ))}
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          {/* ── Center: Chat (Hero) ────────────────── */}
          <section className="panel chat-panel">
            <div className="panel-header">
              <h2>💬 Ask Memora</h2>
              <div className="toggle-row">
                <button className="secondary small" onClick={() => setSpeechEnabled((v) => !v)}>
                  🔊 {speechEnabled ? "On" : "Off"}
                </button>
                <button
                  className="secondary small"
                  onClick={() => {
                    setChat([{ role: "assistant", text: "Starting a new conversation. What would you like to know?" }]);
                    setConversationId(null);
                  }}
                >
                  New Chat
                </button>
              </div>
            </div>

            <div className="chat-log">
              {chat.map((message, index) => (
                <div className={`bubble ${message.role}`} key={`${message.role}-${index}`}>
                  <p>{message.text}</p>
                  {message.fallback && <span className="pill warn">Offline Mode</span>}
                  {message.events?.length ? (
                    <div className="supporting-events">
                      {message.events.slice(0, 3).map((event) => (
                        <span className="subtle-tag" key={event.id} onClick={() => seekTo(event.timestamp_seconds)}>
                          📍 {formatTimestamp(event.timestamp_iso)} — {event.caption.slice(0, 60)}...
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
              {isThinking && (
                <div className="typing-indicator">
                  <span /><span /><span />
                </div>
              )}
            </div>

            <div className="composer">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleQueryKeyDown}
                placeholder={"Ask anything... \"Where did I leave my bag?\" \"Summarize today's activities\""}
              />
              <div className="actions">
                <button className="secondary" onClick={() => startDictation("query")} disabled={!canDictate}>
                  {speech.listening && voiceTarget === "query" ? "🎙️ Listening..." : "🎤 Speak"}
                </button>
                <button onClick={handleQuery} disabled={busy || !query.trim()}>
                  Ask Memora
                </button>
              </div>
            </div>
          </section>

          {/* ── Right: Alerts ──────────────────────── */}
          <section className="panel alert-panel">
            <div className="panel-header">
              <h2>🔔 Alerts</h2>
              <div className="panel-actions">
                {notificationPermission !== "granted" && (
                  <button className="secondary small" onClick={requestNotificationPermission}>Enable</button>
                )}
                <button className="secondary small" onClick={handleClearHits} disabled={alerts.hits.length === 0}>Clear</button>
                <button className="secondary small" onClick={handleExportLogs} disabled={alerts.hits.length === 0}>CSV</button>
              </div>
            </div>

            <div className="composer compact">
              <textarea
                value={alertText}
                onChange={(e) => setAlertText(e.target.value)}
                placeholder="e.g. 'Alert me when someone enters' or 'Notify me if something unusual happens'"
              />
              <div className="actions">
                <button className="secondary" onClick={() => startDictation("alert")} disabled={!canDictate}>
                  {speech.listening && voiceTarget === "alert" ? "🎙️ Listening..." : "🎤 Speak"}
                </button>
                <button onClick={handleCreateAlert} disabled={busy || !alertText.trim()}>
                  Add Rule
                </button>
              </div>
            </div>

            <div className="alert-sections">
              <div className="alert-section">
                <h3>Active Rules</h3>
                <div className="stack">
                  {alerts.rules.length === 0 ? (
                    <EmptyState title="No rules" description="Create alert rules above." />
                  ) : (
                    alerts.rules.map((rule: AlertRule) => (
                      <div className="mini-card policy-card" key={rule.id}>
                        <div className="card-row">
                          <p>
                            {rule.text}
                            {rule.requires_llm && <span className="llm-badge">AI</span>}
                          </p>
                          <button className="text-btn danger" onClick={() => handleDeleteRule(rule.id)}>×</button>
                        </div>
                        <div className="tag-row">
                          {rule.object_keywords.map((kw) => (
                            <span className="tag" key={kw}>{kw}</span>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="alert-section">
                <h3>Incidents ({alerts.hits.length})</h3>
                <div className="stack">
                  {alerts.hits.length === 0 ? (
                    <EmptyState title="All clear" description="Matches will appear here." />
                  ) : (
                    alerts.hits.map((hit: AlertHit) => (
                      <div className="mini-card hit" key={hit.id}>
                        <p>{hit.message}</p>
                        <span className="mono">{formatTimestamp(hit.timestamp_iso)}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────── */

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

/* ── Formatters ──────────────────────────────────────────── */

function formatSeconds(value: number) {
  if (!Number.isFinite(value)) return "0s";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}m ${seconds}s`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
}

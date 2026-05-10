import type { AlertsState, Conversation, Event, QueryResult, SceneSummary, Video, VideoStatus } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadVideo(file: File, location: string, recordingStartTime: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("location", location);
  form.append("recording_start_time", recordingStartTime);
  return request<{ video: Video }>("/upload", { method: "POST", body: form });
}

export async function getVideoStatus(videoId: string) {
  return request<VideoStatus>(`/videos/${videoId}/status`);
}

export async function listEvents(videoId?: string) {
  const params = new URLSearchParams();
  if (videoId) params.set("video_id", videoId);
  return request<Event[]>(`/events?${params.toString()}`);
}

export async function askQuery(question: string, videoId?: string, conversationId?: string) {
  return request<QueryResult>("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      video_id: videoId ?? null,
      conversation_id: conversationId ?? null,
    }),
  });
}

export async function createAlert(text: string, cooldownSeconds?: number) {
  return request("/alert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, cooldown_seconds: cooldownSeconds ?? null }),
  });
}

export async function getAlerts() {
  return request<AlertsState>("/alerts");
}

export async function deleteAlertRule(ruleId: string) {
  return request(`/alerts/rules/${ruleId}`, { method: "DELETE" });
}

export async function clearAlertHits() {
  return request("/alerts/hits", { method: "DELETE" });
}

export async function listConversations() {
  return request<Conversation[]>("/conversations");
}

export async function listSummaries(videoId?: string) {
  const params = new URLSearchParams();
  if (videoId) params.set("video_id", videoId);
  return request<SceneSummary[]>(`/summaries?${params.toString()}`);
}

export type SeedResult = {
  video_id: string;
  created_events: number;
  created_rules: number;
  created_hits: number;
};

export async function seedDemo() {
  return request<SeedResult>("/seed", { method: "POST" });
}

// ── WebSocket ────────────────────────────────────────────────────────

export function createWebSocket(onMessage: (type: string, data: any) => void): WebSocket | null {
  const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws";
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed.type, parsed.data);
      } catch {
        // ignore malformed messages
      }
    };
    ws.onopen = () => {
      // Send ping every 30s to keep alive
      const interval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        } else {
          clearInterval(interval);
        }
      }, 30000);
    };
    return ws;
  } catch {
    return null;
  }
}

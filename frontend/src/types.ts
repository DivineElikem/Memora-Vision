export type Video = {
  id: string;
  filename: string;
  location: string;
  recording_start_time: string;
  status: string;
  progress: number;
  video_url?: string;
};

export type VideoStatus = {
  video_id: string;
  status: string;
  progress: number;
  current_time_seconds: number;
  event_count: number;
  alert_count: number;
  error?: string | null;
};

export type Event = {
  id: string;
  video_id: string;
  timestamp_seconds: number;
  timestamp_iso: string;
  objects: string[];
  track_ids: string[];
  caption: string;
  location: string;
  frame_path?: string | null;
  confidence_summary: Record<string, number>;
  activity_tags: string[];
  thumbnail_url?: string | null;
};

export type QueryResult = {
  answer: string;
  supporting_events: Event[];
  used_fallback: boolean;
  conversation_id?: string | null;
};

export type AlertRule = {
  id: string;
  text: string;
  object_keywords: string[];
  cooldown_seconds: number;
  enabled: boolean;
  requires_llm: boolean;
};

export type AlertHit = {
  id: string;
  rule_id: string;
  event_id: string;
  message: string;
  timestamp_iso: string;
};

export type AlertsState = {
  rules: AlertRule[];
  hits: AlertHit[];
};

export type Conversation = {
  id: string;
  video_id?: string | null;
  title: string;
  created_iso: string;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  timestamp_iso: string;
  supporting_event_ids: string[];
};

export type SceneSummary = {
  id: string;
  video_id: string;
  start_seconds: number;
  end_seconds: number;
  start_iso: string;
  end_iso: string;
  summary: string;
  event_count: number;
  key_objects: string[];
  key_activities: string[];
};

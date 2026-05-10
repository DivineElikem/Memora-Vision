# Vision Assistant Implementation Plan

## 1. Product Goal

Build a hackathon-friendly multimodal video understanding system that turns uploaded indoor CCTV-style footage into structured, searchable event memory.

The demo must support:

- Uploading an MP4 video.
- Processing the video incrementally so it feels like a stream.
- Detecting relevant objects and tracking them across frames.
- Creating concise timeline events.
- Asking natural-language questions by text or voice.
- Receiving answers in text and spoken voice.
- Creating natural-language alert rules.
- Showing in-app alert hits during processing.

The priority is a reliable end-to-end demo over perfect model accuracy.

## 2. Locked Scope

### In Scope

- Single-repo app with `backend/` and `frontend/`.
- FastAPI backend.
- React + Vite frontend.
- SQLite storage.
- Uploaded MP4 processing.
- Polling-based frontend updates.
- CPU-safe local object detection path.
- Remote OpenAI-compatible VLM endpoint for selective frame captions.
- OpenAI-compatible LLM endpoint for query answering.
- First-class mock mode for demos without model services.
- Seed sample events for demo fallback.
- Browser voice input for queries and alert creation.
- Browser text-to-speech for spoken answers.

### Out Of Scope For V1

- Live RTSP/webcam ingestion.
- Backend speech-to-text.
- Vector database.
- Model training.
- Docker requirement.
- Email, webhook, push, or browser notification delivery.
- Zone-level spatial reasoning.
- Multi-camera identity resolution.
- Production authentication.

## 3. Runtime Assumptions

- The app runs on one local laptop for the hackathon demo.
- Local detection should remain usable without an NVIDIA GPU.
- The VLM may run separately on an AMD GPU machine.
- The VLM exposes an OpenAI-compatible API.
- LLM and VLM configuration is provided through `.env`.
- The system must degrade gracefully if model APIs are unavailable.

## 4. Repository Structure

```text
Agentic_Vision/
  backend/
    app/
      api/
      core/
      models/
      services/
      storage/
    tests/
    pyproject.toml
  frontend/
    src/
      api/
      components/
      hooks/
    package.json
  data/
    uploads/
    keyframes/
    vision_assistant.sqlite3
  .env.example
  README.md
  IMPLEMENTATION_PLAN.md
```

`data/` should be gitignored because it stores uploaded videos, keyframes, and the local SQLite database.

## 5. Backend Design

### Framework And Tooling

- Use FastAPI for API routes.
- Use `uv` for Python dependency management.
- Use SQLite through the standard `sqlite3` module for low setup overhead.
- Use background tasks for video processing jobs.

### Core Backend Modules

- `core/config.py`: environment configuration.
- `storage/database.py`: SQLite connection, schema initialization, JSON helpers.
- `services/repository.py`: database read/write abstraction.
- `services/video_processor.py`: frame sampling, detection, tracking, captioning, event creation.
- `services/detector.py`: YOLO adapter plus mock detector.
- `services/captioner.py`: OpenAI-compatible VLM adapter plus template fallback.
- `services/query_engine.py`: retrieval plus LLM answer generation.
- `services/alert_engine.py`: natural-language rule compilation and event matching.
- `api/routes.py`: FastAPI endpoints.

## 6. Data Model

### `videos`

Stores upload and processing state.

Important fields:

- `id`
- `filename`
- `location`
- `recording_start_time`
- `status`
- `progress`
- `current_time_seconds`
- `error`

### `events`

Stores structured video memory.

Important fields:

- `id`
- `video_id`
- `timestamp_seconds`
- `timestamp_iso`
- `objects_json`
- `track_ids_json`
- `caption`
- `location`
- `frame_path`
- `confidence_json`

### `alert_rules`

Stores user-defined rules.

Important fields:

- `id`
- `text`
- `object_keywords_json`
- `cooldown_seconds`
- `enabled`

### `alert_hits`

Stores triggered alerts.

Important fields:

- `id`
- `rule_id`
- `event_id`
- `message`
- `timestamp_iso`

## 7. Video Processing Pipeline

### Upload Flow

1. User uploads an MP4 from the frontend.
2. Backend stores the file under `data/uploads/`.
3. Backend creates a `videos` row with `queued` status.
4. Backend starts a background processing job.
5. Frontend polls status and events every 1-2 seconds.

### Frame Sampling

- Default sample interval: 1-2 seconds.
- Store only selected keyframes.
- Do not store every extracted frame.

### Detection

Use YOLO with a curated COCO security subset:

- `person`
- `backpack`
- `handbag`
- `suitcase`
- `cell phone`
- `laptop`
- `chair`
- `bottle`
- `cup`
- `book`

Normalize `backpack`, `handbag`, and `suitcase` into the user-facing object label `bag`.

### Tracking

Use lightweight object tracking IDs so the system can answer last-seen questions more convincingly.

V1 tracking can be simple:

- Match detections frame-to-frame by object class and bounding-box proximity.
- Keep track IDs stable while objects remain near previous positions.
- Do not attempt strong re-identification.

### Captioning

Use selective VLM captioning:

- Caption frames when important objects appear.
- Caption frames when tracked objects disappear.
- Caption frames when alert rules match.
- Caption periodic keyframes if needed for timeline richness.

If the VLM is unavailable, generate template captions from detections, for example:

```text
person and bag detected in office
```

### Event Grouping

Use moderate grouping:

- Merge repeated same-object observations within a short time window.
- Create new events for object appearances.
- Create new events for object disappearances.
- Create new events for tracker changes.
- Create new events for meaningful caption changes.

## 8. Query Engine

### Query Flow

1. User submits a typed or browser-transcribed question.
2. Backend extracts simple hints:
   - object keywords
   - latest/last-seen intent
   - broad time hints like afternoon, morning, today
3. Backend retrieves relevant events from SQLite.
4. Backend sends the question and compact event context to the configured LLM.
5. Backend returns:
   - final answer
   - supporting events
   - whether fallback mode was used

### Fallback Behavior

If the LLM is unavailable:

- For “where was my bag last seen?”, return the latest matching event.
- For “did anyone enter?”, return yes/no based on matching person events.
- For broad summaries, return a concise deterministic summary of recent events.

The fallback must be good enough for a live demo.

## 9. Alert Engine

### Rule Creation

Users enter natural-language alert rules, for example:

```text
notify me when someone enters
notify me when a person is detected
tell me when a bag appears
```

V1 compiles these into structured object matchers.

Examples:

- `someone`, `person`, `anyone` -> `person`
- `bag`, `backpack`, `handbag`, `suitcase` -> `bag`
- `phone`, `cell phone` -> `cell phone`

### Matching

During video processing:

1. Each new event is checked against enabled alert rules.
2. If event objects match a rule, create an alert hit.
3. Apply cooldown to avoid repeated spam.
4. Persist alert hits in SQLite.
5. Frontend shows alert hits through polling.

### Delivery

V1 alerts are in-app only.

No email, webhook, push notification, or browser notification is required.

## 10. Voice Interaction

### Voice Input

Use browser Web Speech API for v1.

Supported voice actions:

- Dictate a query.
- Dictate an alert rule.

Typed input must always remain available as a fallback.

Backend STT is intentionally deferred for v1, but the frontend should isolate speech recognition logic so a future `/transcribe` endpoint can be added cleanly.

### Voice Output

Use browser `SpeechSynthesis`.

Behavior:

- Show the text answer in the chat.
- Read the answer aloud when speech output is enabled.
- Provide a simple toggle or button to replay the spoken answer.

## 11. API Surface

### `POST /upload`

Uploads a video and starts processing.

Request:

- multipart `file`
- optional `location`
- optional `recording_start_time`

Response:

- `video_id`
- `filename`
- `location`
- `recording_start_time`
- `status`
- `progress`

### `GET /videos/{video_id}/status`

Returns processing state.

Response:

- `video_id`
- `status`
- `progress`
- `current_time_seconds`
- `event_count`
- `alert_count`
- `error`

### `GET /events`

Lists timeline events.

Filters:

- `video_id`
- `object`
- optional time filters later if needed

### `POST /query`

Submits a natural-language question.

Request:

- `question`
- optional `video_id`

Response:

- `answer`
- `supporting_events`
- `used_fallback`

### `POST /alert`

Creates an alert rule.

Request:

- `text`
- optional `cooldown_seconds`

Response:

- `id`
- `text`
- `object_keywords`
- `cooldown_seconds`
- `enabled`

### `GET /alerts`

Returns alert rules and hits.

Response:

- `rules`
- `hits`

### `POST /seed`

Development/demo-only endpoint or script.

Loads sample events, alert rules, and alert hits so the UI can be demonstrated without video/model processing.

## 12. Frontend Design

### Main Screens

The frontend can be one dashboard-style page with four areas:

- Upload and processing status.
- Timeline.
- Query chat with voice input and spoken answers.
- Alert rules and alert hits.

### Upload Experience

The uploaded video should feel like it is being streamed:

- Show processing state immediately.
- Show current processed timestamp.
- Show progress bar.
- Append timeline events as polling discovers them.
- Append alert hits as they fire.

### Timeline

Each event card should show:

- timestamp
- objects
- caption
- room/location
- keyframe thumbnail if available
- track IDs if useful for debugging

### Query Chat

Must support:

- typed questions
- microphone dictation
- answer display
- supporting event references
- spoken answer playback

### Alerts

Must support:

- typed alert creation
- microphone dictation for alert creation
- compiled object keywords display
- triggered alert list

## 13. Configuration

Use `.env.example` with:

```env
VISION_MOCK_MODE=true
DATABASE_PATH=data/vision_assistant.sqlite3
UPLOAD_DIR=data/uploads
KEYFRAME_DIR=data/keyframes
FRAME_SAMPLE_SECONDS=1.5
ALERT_COOLDOWN_SECONDS=20

LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=gpt-4.1-mini

VLM_BASE_URL=
VLM_API_KEY=
VLM_MODEL=qwen-vl
```

If `VISION_MOCK_MODE=true`, the backend should not require YOLO, VLM, or LLM services.

## 14. Testing Plan

### Backend Unit Tests

- Event timestamp conversion.
- Object label normalization.
- Event grouping.
- Alert rule compilation.
- Alert rule matching.
- Alert cooldown suppression.
- Query fallback logic.

### API Tests

- Upload creates video job.
- Status endpoint returns progress.
- Events endpoint returns seeded and processed events.
- Query endpoint returns answer and support events.
- Alert endpoint creates compiled rule.
- Alerts endpoint returns rules and hits.

### Manual Demo Test

1. Start backend and frontend.
2. Enable mock mode.
3. Load seed data.
4. Confirm timeline renders.
5. Ask “Where was my bag last seen?”
6. Confirm text answer and spoken answer.
7. Create “notify me when someone enters.”
8. Upload a short MP4.
9. Confirm timeline updates during processing.
10. Confirm alert hits appear during processing.

## 15. Implementation Order

1. Backend project scaffold and config.
2. SQLite schema and repository layer.
3. Alert compiler and matcher.
4. Query fallback engine.
5. Mock video processor that emits incremental events.
6. FastAPI routes.
7. React frontend scaffold.
8. API client and polling hooks.
9. Upload/status/timeline UI.
10. Query chat UI.
11. Voice input and speech synthesis.
12. Alert rule and alert hit UI.
13. Seed data path.
14. Real YOLO adapter.
15. OpenAI-compatible LLM/VLM adapters.
16. README and final demo instructions.

## 16. Acceptance Criteria

The implementation is demo-ready when:

- A user can start the backend and frontend from documented commands.
- A user can upload an MP4.
- Events appear incrementally while processing runs.
- A timeline shows structured events.
- A user can ask a typed question and get an answer.
- A user can speak a question and get an answer.
- The answer can be read aloud by the browser.
- A user can create a typed or spoken alert rule.
- Alert hits appear in the UI during processing.
- The app still works in mock mode without YOLO, VLM, or LLM services.


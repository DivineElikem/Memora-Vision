class Video {
  final String id;
  final String filename;
  final String location;
  final String recordingStartTime;
  final String status;
  final double progress;

  Video({
    required this.id,
    required this.filename,
    required this.location,
    required this.recordingStartTime,
    required this.status,
    required this.progress,
  });

  factory Video.fromJson(Map<String, dynamic> json) {
    return Video(
      id: json['id'],
      filename: json['filename'],
      location: json['location'],
      recordingStartTime: json['recording_start_time'],
      status: json['status'],
      progress: (json['progress'] as num).toDouble(),
    );
  }
}

class VideoStatus {
  final String videoId;
  final String status;
  final double progress;
  final double currentTimeSeconds;
  final int eventCount;
  final int alertCount;
  final String? error;

  VideoStatus({
    required this.videoId,
    required this.status,
    required this.progress,
    required this.currentTimeSeconds,
    required this.eventCount,
    required this.alertCount,
    this.error,
  });

  factory VideoStatus.fromJson(Map<String, dynamic> json) {
    return VideoStatus(
      videoId: json['video_id'],
      status: json['status'],
      progress: (json['progress'] as num).toDouble(),
      currentTimeSeconds: (json['current_time_seconds'] as num).toDouble(),
      eventCount: json['event_count'],
      alertCount: json['alert_count'],
      error: json['error'],
    );
  }
}

class Event {
  final String id;
  final String videoId;
  final double timestampSeconds;
  final String timestampIso;
  final List<String> objects;
  final List<String> trackIds;
  final String caption;
  final String location;
  final String? framePath;

  Event({
    required this.id,
    required this.videoId,
    required this.timestampSeconds,
    required this.timestampIso,
    required this.objects,
    required this.trackIds,
    required this.caption,
    required this.location,
    this.framePath,
  });

  factory Event.fromJson(Map<String, dynamic> json) {
    return Event(
      id: json['id'],
      videoId: json['video_id'],
      timestampSeconds: (json['timestamp_seconds'] as num).toDouble(),
      timestampIso: json['timestamp_iso'],
      objects: List<String>.from(json['objects']),
      trackIds: List<String>.from(json['track_ids']),
      caption: json['caption'],
      location: json['location'],
      framePath: json['frame_path'],
    );
  }
}

class AlertRule {
  final String id;
  final String text;
  final List<String> objectKeywords;
  final int cooldownSeconds;
  final bool enabled;

  AlertRule({
    required this.id,
    required this.text,
    required this.objectKeywords,
    required this.cooldownSeconds,
    required this.enabled,
  });

  factory AlertRule.fromJson(Map<String, dynamic> json) {
    return AlertRule(
      id: json['id'],
      text: json['text'],
      objectKeywords: List<String>.from(json['object_keywords']),
      cooldownSeconds: json['cooldown_seconds'],
      enabled: json['enabled'],
    );
  }
}

class AlertHit {
  final String id;
  final String ruleId;
  final String eventId;
  final String message;
  final String timestampIso;

  AlertHit({
    required this.id,
    required this.ruleId,
    required this.eventId,
    required this.message,
    required this.timestampIso,
  });

  factory AlertHit.fromJson(Map<String, dynamic> json) {
    return AlertHit(
      id: json['id'],
      ruleId: json['rule_id'],
      eventId: json['event_id'],
      message: json['message'],
      timestampIso: json['timestamp_iso'],
    );
  }
}

class QueryResult {
  final String answer;
  final List<Event> supportingEvents;
  final bool usedFallback;

  QueryResult({
    required this.answer,
    required this.supportingEvents,
    required this.usedFallback,
  });

  factory QueryResult.fromJson(Map<String, dynamic> json) {
    return QueryResult(
      answer: json['answer'],
      supportingEvents: (json['supporting_events'] as List)
          .map((e) => Event.fromJson(e))
          .toList(),
      usedFallback: json['used_fallback'],
    );
  }
}

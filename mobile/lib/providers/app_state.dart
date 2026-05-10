import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_service.dart';

class ChatMessage {
  final String role;
  final String text;
  final List<Event>? events;
  final bool fallback;

  ChatMessage({required this.role, required this.text, this.events, this.fallback = false});
}

class AppState extends ChangeNotifier {
  final ApiService api;
  Video? currentVideo;
  VideoStatus? currentStatus;
  List<Event> events = [];
  List<AlertRule> alertRules = [];
  List<AlertHit> alertHits = [];
  List<ChatMessage> chatHistory = [
    ChatMessage(role: 'assistant', text: 'Upload a video, ask a question, or seed demo data to start.')
  ];
  bool isBusy = false;
  Timer? _pollingTimer;

  AppState({required this.api}) {
    refreshAlerts();
  }

  void setCurrentVideo(Video video) {
    currentVideo = video;
    startPolling();
    notifyListeners();
  }

  void startPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      if (currentVideo == null) return;
      try {
        currentStatus = await api.getVideoStatus(currentVideo!.id);
        events = await api.listEvents(videoId: currentVideo!.id);
        events = events.reversed.toList();
        await refreshAlerts();
        notifyListeners();
      } catch (e) {
        debugPrint('Polling error: $e');
      }
    });
  }

  Future<void> refreshAlerts() async {
    try {
      final data = await api.getAlerts();
      alertRules = (data['rules'] as List).map((e) => AlertRule.fromJson(e)).toList();
      alertHits = (data['hits'] as List).map((e) => AlertHit.fromJson(e)).toList();
      notifyListeners();
    } catch (e) {
      debugPrint('Error refreshing alerts: $e');
    }
  }

  Future<void> uploadVideo(File file, String location, String recordingStartTime) async {
    isBusy = true;
    notifyListeners();
    try {
      currentVideo = await api.uploadVideo(file, location, recordingStartTime);
      chatHistory.add(ChatMessage(role: 'assistant', text: 'Processing ${currentVideo!.filename}. The timeline will update as the video is analyzed.'));
      startPolling();
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> askQuery(String question) async {
    isBusy = true;
    chatHistory.add(ChatMessage(role: 'user', text: question));
    notifyListeners();
    try {
      final result = await api.askQuery(question, videoId: currentVideo?.id);
      chatHistory.add(ChatMessage(
        role: 'assistant',
        text: result.answer,
        events: result.supportingEvents,
        fallback: result.usedFallback,
      ));
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> createAlert(String text) async {
    isBusy = true;
    notifyListeners();
    try {
      await api.createAlert(text);
      await refreshAlerts();
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  Future<void> seedDemo() async {
    isBusy = true;
    notifyListeners();
    try {
      final videoId = await api.seedDemo();
      currentVideo = Video(
        id: videoId,
        filename: 'seed-demo.mp4',
        location: 'office',
        recordingStartTime: DateTime.now().toIso8601String(),
        status: 'completed',
        progress: 1.0,
      );
      startPolling();
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _pollingTimer?.cancel();
    super.dispose();
  }
}

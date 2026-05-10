import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path/path.dart';
import '../models/models.dart';

class ApiService {
  final String baseUrl;

  ApiService({required this.baseUrl});

  Future<Video> uploadVideo(File file, String location, String recordingStartTime) async {
    var request = http.MultipartRequest('POST', Uri.parse('$baseUrl/upload'));
    request.fields['location'] = location;
    request.fields['recording_start_time'] = recordingStartTime;
    request.files.add(await http.MultipartFile.fromPath('file', file.path, filename: basename(file.path)));

    var response = await request.send();
    if (response.statusCode == 200) {
      var body = await response.stream.bytesToString();
      return Video.fromJson(jsonDecode(body)['video']);
    } else {
      throw Exception('Upload failed');
    }
  }

  Future<VideoStatus> getVideoStatus(String videoId) async {
    final response = await http.get(Uri.parse('$baseUrl/videos/$videoId/status'));
    if (response.statusCode == 200) {
      return VideoStatus.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to get status');
    }
  }

  Future<List<Event>> listEvents({String? videoId}) async {
    String url = '$baseUrl/events';
    if (videoId != null) {
      url += '?video_id=$videoId';
    }
    final response = await http.get(Uri.parse(url));
    if (response.statusCode == 200) {
      Iterable l = jsonDecode(response.body);
      return List<Event>.from(l.map((model) => Event.fromJson(model)));
    } else {
      throw Exception('Failed to list events');
    }
  }

  Future<QueryResult> askQuery(String question, {String? videoId}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/query'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'question': question, 'video_id': videoId}),
    );
    if (response.statusCode == 200) {
      return QueryResult.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Query failed');
    }
  }

  Future<AlertRule> createAlert(String text, {int? cooldownSeconds}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/alert'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'text': text, 'cooldown_seconds': cooldownSeconds}),
    );
    if (response.statusCode == 200) {
      return AlertRule.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to create alert');
    }
  }

  Future<Map<String, dynamic>> getAlerts() async {
    final response = await http.get(Uri.parse('$baseUrl/alerts'));
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to get alerts');
    }
  }

  Future<String> seedDemo() async {
    final response = await http.post(Uri.parse('$baseUrl/seed'));
    if (response.statusCode == 200) {
      return jsonDecode(response.body)['video_id'];
    } else {
      throw Exception('Seed failed');
    }
  }
}

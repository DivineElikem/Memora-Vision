import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/app_state.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      appBar: AppBar(title: const Text('Agentic Vision')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildHeader(),
            const SizedBox(height: 20),
            _buildUploadCard(context, state),
            const SizedBox(height: 20),
            if (state.currentVideo != null) _buildStatusCard(state),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Vision Assistant', style: TextStyle(color: Colors.indigoAccent, fontWeight: FontWeight.bold)),
        Text('Multimodal video memory with voice and timeline.', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w300)),
      ],
    );
  }

  Widget _buildUploadCard(BuildContext context, AppState state) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Text('Upload Video', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            ElevatedButton.icon(
              onPressed: state.isBusy ? null : () => _pickAndUpload(context, state),
              icon: const Icon(Icons.upload_file),
              label: Text(state.isBusy ? 'Uploading...' : 'Select Video'),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: state.isBusy ? null : () => state.seedDemo(),
              child: const Text('Load Demo Data'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard(AppState state) {
    final status = state.currentStatus;
    final progress = status?.progress ?? 0.0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Processing Status', style: TextStyle(fontWeight: FontWeight.bold)),
                Text('${(progress * 100).toInt()}%'),
              ],
            ),
            const SizedBox(height: 10),
            LinearProgressIndicator(value: progress),
            const SizedBox(height: 20),
            _buildMetric('Filename', state.currentVideo?.filename ?? 'N/A'),
            _buildMetric('Events', '${status?.eventCount ?? 0}'),
            _buildMetric('Alerts', '${status?.alertCount ?? 0}'),
          ],
        ),
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Future<void> _pickAndUpload(BuildContext context, AppState state) async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(type: FileType.video);
    if (result != null) {
      File file = File(result.files.single.path!);
      state.uploadVideo(file, 'mobile', DateTime.now().toIso8601String());
    }
  }
}

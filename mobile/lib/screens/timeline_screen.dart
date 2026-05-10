import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/app_state.dart';

class TimelineScreen extends StatelessWidget {
  const TimelineScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      appBar: AppBar(title: const Text('Timeline')),
      body: state.events.isEmpty
          ? _buildEmptyState()
          : ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: state.events.length,
              itemBuilder: (context, index) {
                final event = state.events[index];
                return Card(
                  margin: const EdgeInsets.symmetric(vertical: 8),
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              _formatTime(event.timestampIso),
                              style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.indigoAccent),
                            ),
                            Text(event.location, style: const TextStyle(color: Colors.grey, fontSize: 12)),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(event.caption, style: const TextStyle(fontSize: 16)),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 4,
                          children: event.objects.map((obj) => Chip(
                            label: Text(obj, style: const TextStyle(fontSize: 10)),
                            padding: EdgeInsets.zero,
                            visualDensity: VisualDensity.compact,
                          )).toList(),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  Widget _buildEmptyState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.history, size: 64, color: Colors.grey),
          SizedBox(height: 16),
          Text('No events detected yet.', style: TextStyle(color: Colors.grey)),
        ],
      ),
    );
  }

  String _formatTime(String iso) {
    try {
      final date = DateTime.parse(iso);
      return DateFormat('MMM d, y, h:mm:ss a').format(date);
    } catch (e) {
      return iso;
    }
  }
}

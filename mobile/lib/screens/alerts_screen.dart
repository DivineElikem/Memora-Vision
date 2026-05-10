import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/app_state.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      appBar: AppBar(title: const Text('Alerts')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: 'Notify me when...',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: state.isBusy ? null : () {
                    if (_controller.text.isNotEmpty) {
                      state.createAlert(_controller.text);
                      _controller.clear();
                    }
                  },
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
          ),
          Expanded(
            child: DefaultTabController(
              length: 2,
              child: Column(
                children: [
                  const TabBar(
                    tabs: [
                      Tab(text: 'Rules'),
                      Tab(text: 'Hits'),
                    ],
                  ),
                  Expanded(
                    child: TabBarView(
                      children: [
                        _buildRulesList(state),
                        _buildHitsList(state),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRulesList(AppState state) {
    return ListView.builder(
      itemCount: state.alertRules.length,
      itemBuilder: (context, index) {
        final rule = state.alertRules[index];
        return ListTile(
          title: Text(rule.text),
          subtitle: Text('Keywords: ${rule.objectKeywords.join(", ")}'),
          trailing: Icon(Icons.check_circle, color: rule.enabled ? Colors.green : Colors.grey),
        );
      },
    );
  }

  Widget _buildHitsList(AppState state) {
    return ListView.builder(
      itemCount: state.alertHits.length,
      itemBuilder: (context, index) {
        final hit = state.alertHits[index];
        return ListTile(
          leading: const Icon(Icons.warning, color: Colors.amber),
          title: Text(hit.message),
          subtitle: Text(_formatTime(hit.timestampIso)),
        );
      },
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

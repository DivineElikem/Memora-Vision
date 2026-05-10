import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:flutter_tts/flutter_tts.dart';
import '../providers/app_state.dart';

class VoiceConversationScreen extends StatefulWidget {
  const VoiceConversationScreen({super.key});

  @override
  State<VoiceConversationScreen> createState() => _VoiceConversationScreenState();
}

class _VoiceConversationScreenState extends State<VoiceConversationScreen> {
  final stt.SpeechToText _speech = stt.SpeechToText();
  final FlutterTts _tts = FlutterTts();
  bool _isListening = false;
  String _currentTranscript = "Tap the mic to start talking";
  String _assistantResponse = "";

  @override
  void initState() {
    super.initState();
    _initTts();
  }

  void _initTts() async {
    await _tts.setLanguage("en-US");
    await _tts.setSpeechRate(0.5);
    await _tts.setPitch(1.0);
  }

  void _toggleListening() async {
    if (!_isListening) {
      bool available = await _speech.initialize();
      if (available) {
        setState(() {
          _isListening = true;
          _currentTranscript = "Listening...";
        });
        _speech.listen(
          onResult: (val) {
            setState(() => _currentTranscript = val.recognizedWords);
            if (val.finalResult) {
              _handleUserInput(val.recognizedWords);
            }
          },
        );
      }
    } else {
      setState(() => _isListening = false);
      _speech.stop();
    }
  }

  void _handleUserInput(String text) async {
    if (text.isEmpty) return;
    setState(() => _isListening = false);
    
    final state = Provider.of<AppState>(context, listen: false);
    await state.askQuery(text);
    
    final lastMsg = state.chatHistory.last;
    if (lastMsg.role == 'assistant') {
      setState(() => _assistantResponse = lastMsg.text);
      await _tts.speak(lastMsg.text);
    }
  }

  @override
  void dispose() {
    _speech.stop();
    _tts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Voice Conversation'),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Spacer(),
              if (_assistantResponse.isNotEmpty)
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    _assistantResponse,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w400),
                  ),
                ),
              const SizedBox(height: 40),
              Text(
                _currentTranscript,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: _isListening ? Colors.indigoAccent : Colors.grey,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: _toggleListening,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  width: 120,
                  height: 120,
                  decoration: BoxDecoration(
                    color: _isListening ? Colors.red.withOpacity(0.2) : Colors.indigoAccent.withOpacity(0.1),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: _isListening ? Colors.red : Colors.indigoAccent,
                      width: 4,
                    ),
                    boxShadow: _isListening ? [
                      BoxShadow(
                        color: Colors.red.withOpacity(0.5),
                        blurRadius: 20,
                        spreadRadius: 5,
                      )
                    ] : [],
                  ),
                  child: Icon(
                    _isListening ? Icons.mic : Icons.mic_none,
                    size: 60,
                    color: _isListening ? Colors.red : Colors.indigoAccent,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                _isListening ? 'Listening...' : 'Tap to speak',
                style: const TextStyle(color: Colors.grey),
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}

import { useEffect, useMemo, useRef, useState } from "react";

export function useSpeechRecognition() {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);

  useEffect(() => {
    const ctor = getSpeechRecognition();
    setSupported(Boolean(ctor));
  }, []);

  const api = useMemo(() => {
    const start = () => {
      const Recognition = getSpeechRecognition();
      if (!Recognition) return false;
      const recognition = new Recognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event: BrowserSpeechRecognitionEvent) => {
        const result = event.results[0]?.[0]?.transcript ?? "";
        setTranscript(result);
      };
      recognition.onstart = () => setListening(true);
      recognition.onend = () => setListening(false);
      recognition.onerror = () => setListening(false);
      recognitionRef.current = recognition;
      recognition.start();
      return true;
    };
    const stop = () => {
      recognitionRef.current?.stop();
      setListening(false);
    };
    return { start, stop };
  }, []);

  return { supported, listening, transcript, setTranscript, ...api };
}

function getSpeechRecognition(): SpeechRecognitionLike | null {
  return (window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null) as SpeechRecognitionLike | null;
}

type SpeechRecognitionLike = new () => BrowserSpeechRecognition;

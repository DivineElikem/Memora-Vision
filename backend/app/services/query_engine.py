"""Conversational query engine for Memora Vision.

Supports multi-turn conversations where Memora speaks as an AI that personally
witnessed the events. Uses semantic search for event retrieval and scene
summaries for broad questions.
"""

import logging
import re

import httpx

from app.models.schemas import EventOut
from app.services.repository import Repository
from app.services.text import extract_object_keywords, format_human_time, parse_time_hint

logger = logging.getLogger(__name__)

MEMORA_SYSTEM_PROMPT = (
    "You are Memora, an AI visual memory assistant. "
    "You have been watching and remembering everything that happens in the monitored spaces. "
    "You speak naturally, as if you personally witnessed the events.\n\n"
    "Instead of saying 'According to the data...' or 'Based on the timeline...', "
    "say 'I saw...' or 'I remember...' or 'Earlier today...'\n"
    "Instead of listing event IDs, weave the information into a natural narrative.\n\n"
    "When answering:\n"
    "- Be specific about times, descriptions, and locations\n"
    "- If you are uncertain, say so honestly\n"
    "- Reference what you have seen as personal observations\n"
    "- For summary requests, create a narrative timeline, not a bullet list\n"
    "- Keep answers concise but informative (2-4 sentences for simple questions, more for summaries)\n\n"
    "CRITICAL: If you identify relevant events, list their IDs at the very end of your response "
    "in this exact format on its own line: REFS: [id1, id2, id3]\n"
    "This line will be hidden from the user, so do not refer to it in your answer."
)


class QueryEngine:
    def __init__(self, repo: Repository, base_url: str | None, api_key: str | None, model: str):
        self.repo = repo
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.model = model

    def answer(
        self,
        question: str,
        video_id: str | None = None,
        conversation_id: str | None = None,
    ) -> tuple[str, list[EventOut], bool, str | None]:
        """Answer a question with conversation context.

        Returns: (answer_text, supporting_events, used_fallback, conversation_id)
        """
        # Create or continue conversation
        if not conversation_id:
            conv = self.repo.create_conversation(video_id=video_id, title=question[:80])
            conversation_id = conv.id
        else:
            # Update title if it's still the default
            try:
                pass  # Keep existing title
            except Exception:
                pass

        # Store user message
        self.repo.add_chat_message(conversation_id, "user", question)

        # Retrieve relevant events using semantic search
        events = self._retrieve_events(question, video_id)

        if not events:
            answer = "I haven't observed any activity yet. Please upload a video so I can start watching and remembering."
            self.repo.add_chat_message(conversation_id, "assistant", answer)
            return answer, [], False, conversation_id

        if not self.base_url:
            answer, supporting = self._fallback_answer(question, events)
            self.repo.add_chat_message(
                conversation_id, "assistant", answer,
                supporting_event_ids=[e.id for e in supporting],
            )
            return answer, supporting, True, conversation_id

        # Build conversation history
        history = self.repo.get_conversation_messages(conversation_id, limit=20)
        # Exclude the message we just added (it's in the user prompt)
        history = [m for m in history if m.content != question or m.role != "user"][-10:]

        # Get scene summaries for broad questions
        summaries = self.repo.list_scene_summaries(video_id=video_id)

        answer_text = self._llm_answer(question, events, history, summaries)
        clean_answer, event_ids = self._parse_response(answer_text)

        # Find supporting events
        supporting_events = [e for e in events if e.id in event_ids]
        if not supporting_events and events:
            supporting_events = events[:2]

        # Store assistant response
        self.repo.add_chat_message(
            conversation_id, "assistant", clean_answer,
            supporting_event_ids=[e.id for e in supporting_events],
        )

        return clean_answer, supporting_events, False, conversation_id

    def _retrieve_events(self, question: str, video_id: str | None) -> list[EventOut]:
        """Retrieve relevant events using semantic search and intent detection."""
        # Try semantic search first
        events = self.repo.semantic_search_events(question, video_id=video_id, limit=30)

        # If semantic search finds few results, broaden to all recent events
        if len(events) < 5:
            all_events = self.repo.list_events(video_id=video_id, limit=50)
            seen_ids = {e.id for e in events}
            for e in all_events:
                if e.id not in seen_ids:
                    events.append(e)
                    if len(events) >= 30:
                        break

        return events

    def _llm_answer(
        self,
        question: str,
        events: list[EventOut],
        history: list,
        summaries: list,
    ) -> str:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Build event context
        events_sorted = sorted(events, key=lambda e: e.timestamp_seconds)
        context_lines = []
        for e in events_sorted[:30]:
            time_str = format_human_time(e.timestamp_iso)
            objects_str = ", ".join(e.objects) if e.objects else "none"
            activities_str = ", ".join(e.activity_tags) if e.activity_tags else ""
            line = f"ID:{e.id} | [{time_str}] {e.location} | Objects: {objects_str}"
            if activities_str:
                line += f" | Activities: {activities_str}"
            line += f" | Scene: {e.caption}"
            context_lines.append(line)
        event_context = "\n".join(context_lines)

        # Build summary context
        summary_context = ""
        if summaries:
            summary_lines = []
            for s in summaries[:5]:
                start = format_human_time(s.start_iso)
                end = format_human_time(s.end_iso)
                summary_lines.append(f"[{start}–{end}] {s.summary}")
            summary_context = "\n".join(summary_lines)

        # Build conversation history
        history_text = ""
        if history:
            history_lines = []
            for msg in history[-6:]:  # Last 6 messages for context
                role_label = "User" if msg.role == "user" else "Memora"
                history_lines.append(f"{role_label}: {msg.content}")
            history_text = "\n".join(history_lines)

        system = MEMORA_SYSTEM_PROMPT
        if history_text:
            system += f"\n\nConversation so far:\n{history_text}"

        user_content = f"What I've observed:\n{event_context}"
        if summary_context:
            user_content += f"\n\nScene summaries:\n{summary_context}"
        user_content += f"\n\nUser's question: {question}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    def _parse_response(self, text: str) -> tuple[str, list[str]]:
        """Parse the LLM response to extract clean answer and referenced event IDs."""
        # Look for REFS: [id1, id2] pattern
        uuid_pattern = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"

        refs_match = re.search(r"REFS:\s*\[([^\]]*)\]", text, re.IGNORECASE)
        if refs_match:
            refs_text = refs_match.group(1)
            found_ids = re.findall(uuid_pattern, refs_text)
            clean_text = re.sub(r"\n?REFS:\s*\[[^\]]*\]", "", text, flags=re.IGNORECASE).strip()
            return clean_text, found_ids

        # Fallback: look for the old format
        label_pattern = r"(?:Relevant\s+)?Event\s+IDs?:\s*"
        match = re.search(f"{label_pattern}(.*)", text, re.IGNORECASE | re.DOTALL)
        if match:
            remaining = match.group(1)
            found_ids = re.findall(uuid_pattern, remaining)
            clean_text = re.sub(f"{label_pattern}.*", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
            if found_ids:
                return clean_text, found_ids

        return text, []

    def _fallback_answer(
        self, question: str, events: list[EventOut]
    ) -> tuple[str, list[EventOut]]:
        """Generate an answer without an LLM using deterministic logic."""
        lowered = question.lower()
        keywords = extract_object_keywords(question)

        # Sort events chronologically
        events_sorted = sorted(events, key=lambda e: e.timestamp_seconds, reverse=True)

        # "Where" questions — find latest event with matching objects
        if "where" in lowered and keywords:
            for event in events_sorted:
                if any(k in event.objects or k in event.caption.lower() for k in keywords):
                    time_str = format_human_time(event.timestamp_iso)
                    return (
                        f"I last saw {', '.join(keywords)} at {time_str} in {event.location}. {event.caption}",
                        [event],
                    )

        # "Who" / person questions
        if any(w in lowered for w in ["who", "anyone", "someone", "person"]):
            person_events = [e for e in events_sorted if "person" in e.objects]
            if person_events:
                latest = person_events[0]
                return (
                    f"I saw someone at {format_human_time(latest.timestamp_iso)} in {latest.location}. {latest.caption}",
                    person_events[:3],
                )
            return "I haven't observed anyone in the recorded footage.", []

        # "How many" questions
        if "how many" in lowered:
            if keywords:
                matching = [e for e in events if any(k in e.objects for k in keywords)]
                return f"I observed {', '.join(keywords)} in {len(matching)} different moments.", matching[:3]

        # Summary / "what happened" questions
        if any(w in lowered for w in ["summarize", "summary", "what happened", "tell me about"]):
            if len(events_sorted) >= 2:
                first = events_sorted[-1]
                last = events_sorted[0]
                return (
                    f"Between {format_human_time(first.timestamp_iso)} and {format_human_time(last.timestamp_iso)}, "
                    f"I observed {len(events)} activities in {first.location}. "
                    f"Most recently: {last.caption}",
                    events_sorted[:3],
                )

        # Default: return latest events
        if events_sorted:
            latest = events_sorted[0]
            return (
                f"Based on my recent observations: {latest.caption} "
                f"(at {format_human_time(latest.timestamp_iso)} in {latest.location})",
                [latest],
            )

        return "I don't have enough observations to answer that question.", []

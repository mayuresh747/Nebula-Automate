"""
nebulaONE API Client

A Python client for programmatically interacting with the nebulaONE AI assistant API.
Uses session-based authentication (JWT token from browser) to send messages and receive responses.

The API uses Server-Sent Events (SSE) for streaming responses in real-time.
"""

import json
import requests
import base64
import uuid
from typing import Optional, Dict, Any, Callable, Iterator


class NebulaClient:
    """Client for interacting with nebulaONE API using session-based authentication."""
    
    def __init__(
        self,
        auth_token: str,
        config_state_id: str,
        gpt_system_id: str = "bd74d1b1-7ea5-4974-bdde-1ddf63cb8300",
        base_url: str = "https://nebulaone-pilot.uw.edu"
    ):
        """
        Initialize the nebulaONE client.
        
        Args:
            auth_token: JWT token (n1aiToken) from browser localStorage
            config_state_id: The agent's configuration state ID
            gpt_system_id: The GPT system ID (default: Aayushi_OpenAI's ID)
            base_url: Base URL for the API (default: nebulaONE pilot environment)
        """
        self.auth_token = auth_token
        self.config_state_id = config_state_id
        self.gpt_system_id = gpt_system_id
        self.base_url = base_url
        
        # Conversation state for multi-turn conversations
        self.conversation_id = None
        self.last_segment_id = None
        self.session_identifier = str(uuid.uuid4())
        
    def _get_headers(self) -> Dict[str, str]:
        """Get the required headers for API requests."""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
    
    def _parse_sse_line(self, line: str) -> tuple[Optional[str], Optional[str]]:
        """Parse a single SSE line into (event_type, data)."""
        line = line.strip()
        if line.startswith("event:"):
            return ("event", line[6:].strip())
        elif line.startswith("data:"):
            return ("data", line[5:].strip())
        return (None, None)
    
    def _decode_base64_data(self, data: str) -> str:
        """Decode base64-encoded SSE data."""
        try:
            return base64.b64decode(data).decode('utf-8')
        except Exception:
            return data  # Return as-is if not base64

    def _prepare_request(self, message: str, session_identifier: Optional[str] = None):
        """Prepare the URL and payload for a request."""
        # Use existing session identifier or provided one
        if session_identifier is None:
            session_identifier = self.session_identifier
        else:
            self.session_identifier = session_identifier
        
        # Determine endpoint and payload based on conversation state
        if self.conversation_id and self.last_segment_id:
            # Follow-up message in existing conversation
            # Use simplified payload with top-level parentId
            url = f"{self.base_url}/api/internal/configStates/{self.config_state_id}/conversations/{self.conversation_id}/segments"
            payload = {
                "question": message,
                "parentId": self.last_segment_id
            }
        else:
            # New conversation
            url = f"{self.base_url}/api/internal/configStates/{self.config_state_id}/conversations"
            payload = {
                "question": message,
                "visionImageIds": [],
                "attachmentIds": [],
                "session": {
                    "sessionIdentifier": session_identifier
                }
            }
        return url, payload

    def _parse_stream_events(self, response) -> Iterator[tuple[str, Any]]:
        """Parse SSE stream and yield high-level events."""
        current_event = None
        
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            
            field_type, field_value = self._parse_sse_line(line)
            
            if field_type == "event":
                current_event = field_value
            elif field_type == "data" and current_event:
                decoded_data = self._decode_base64_data(field_value)
                
                if current_event == "conversation-and-segment-id":
                    # Parse conversation and segment IDs
                    try:
                        ids = json.loads(decoded_data)
                        yield "conversation_ids", ids
                    except json.JSONDecodeError:
                        pass
                
                elif current_event == "step-update":
                    # Status update (e.g., "Thinking")
                    yield "status", decoded_data
                
                elif current_event == "response-updated":
                    # Response chunk
                    yield "chunk", decoded_data

    def stream_chat_generator(self, message: str, session_identifier: Optional[str] = None) -> Iterator[str]:
        """
        Send a message and yield response chunks as they arrive.
        Also handles internal state updates.
        """
        url, payload = self._prepare_request(message, session_identifier)
        
        try:
            # Make streaming request
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=True
            )
            
            response.raise_for_status()
            
            # Parse events and yield chunks
            for event_type, data in self._parse_stream_events(response):
                if event_type == "conversation_ids":
                    conversation_id = data.get("ConversationId")
                    segment_id = data.get("ConversationSegmentId")
                    if conversation_id:
                        self.conversation_id = conversation_id
                    if segment_id:
                        self.last_segment_id = segment_id
                
                elif event_type == "chunk":
                    yield data
                    
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error communicating with nebulaONE API: {str(e)}")

    
    def send_message_stream(
        self,
        message: str,
        session_identifier: Optional[str] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_response_chunk: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Send a message and stream the response in real-time.
        
        Args:
            message: The message to send to the assistant
            session_identifier: Optional session identifier (UUID). If not provided, a new one will be generated.
            on_status: Optional callback for status updates (e.g., "Thinking")
            on_response_chunk: Optional callback for each chunk of the response text
        
        Returns:
            Dictionary containing:
                - conversation_id: The conversation ID
                - segment_id: The conversation segment ID
                - response: The complete response text
                - status_updates: List of status updates received
        """
        url, payload = self._prepare_request(message, session_identifier)

        
        try:
            # Make streaming request
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=True
            )
            
            response.raise_for_status()
            
            # Parse SSE stream
            conversation_id = None
            segment_id = None
            full_response = ""
            status_updates = []
            
            # Iterate over the generator to process events
            for event_type, data in self._parse_stream_events(response):
                if event_type == "conversation_ids":
                    conversation_id = data.get("ConversationId")
                    segment_id = data.get("ConversationSegmentId")
                    
                    # Update local state
                    if conversation_id:
                        self.conversation_id = conversation_id
                    if segment_id:
                        self.last_segment_id = segment_id
                        
                elif event_type == "status":
                    status_updates.append(data)
                    if on_status:
                        on_status(data)
                        
                elif event_type == "chunk":
                    full_response += data
                    if on_response_chunk:
                        on_response_chunk(data)
            
            return {
                "conversation_id": conversation_id,
                "segment_id": segment_id,
                "response": full_response,
                "status_updates": status_updates
            }
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error communicating with nebulaONE API: {str(e)}")
    
    def send_message(
        self,
        message: str,
        session_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message and wait for the complete response (non-streaming).
        
        Args:
            message: The message to send to the assistant
            session_identifier: Optional session identifier (UUID). If not provided, a new one will be generated.
        
        Returns:
            Dictionary containing the conversation IDs and complete response
        """
        return self.send_message_stream(message, session_identifier)
    
    def chat(self, message: str) -> str:
        """
        Convenience method to send a message and get the text response.
        
        Args:
            message: The message to send
            
        Returns:
            The assistant's response as a string
        """
        result = self.send_message(message)
        return result.get("response", "")
    
    def chat_stream(
        self,
        message: str,
        on_status: Optional[Callable[[str], None]] = None,
        on_chunk: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Send a message and stream the response with callbacks.
        
        Args:
            message: The message to send
            on_status: Optional callback for status updates
            on_chunk: Optional callback for response chunks
            
        Returns:
            The complete response text
        """
        result = self.send_message_stream(message, on_status=on_status, on_response_chunk=on_chunk)
        return result.get("response", "")
    
    def new_conversation(self) -> None:
        """
        Start a new conversation, clearing the current conversation state.
        
        This will reset the conversation ID and segment ID, so the next message
        will start a fresh conversation without context from previous messages.
        """
        self.conversation_id = None
        self.last_segment_id = None
        self.session_identifier = str(uuid.uuid4())
    
    def get_conversation_id(self) -> Optional[str]:
        """
        Get the current conversation ID.
        
        Returns:
            The conversation ID if a conversation is active, None otherwise
        """
        return self.conversation_id
    
    def get_session_id(self) -> str:
        """
        Get the current session identifier.
        
        Returns:
            The session identifier UUID
        """
        return self.session_identifier

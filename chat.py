#!/usr/bin/env python3
"""
Interactive Conversation Script

Run this script to have a conversation with the nebulaONE AI.
The conversation continues automatically using the session_id.
"""

import requests

API_URL = "http://localhost:8000/chat"

def chat(message, session_id=None):
    """Send a message and return the response with session info."""
    payload = {"message": message}
    
    if session_id:
        payload["session_id"] = session_id
    
    response = requests.post(
        API_URL,
        headers={"Content-Type": "application/json"},
        json=payload
    )
    
    return response.json()


def main():
    print("=" * 60)
    print("🗣️  Interactive Conversation with nebulaONE")
    print("=" * 60)
    print("Type your messages below. Type 'quit' or 'exit' to end.")
    print("Type 'new' to start a fresh conversation.")
    print("=" * 60)
    print()
    
    session_id = None
    conversation_id = None
    message_count = 0
    
    while True:
        # Get user input
        try:
            user_input = input("👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break
        
        # Handle special commands
        if not user_input:
            continue
        
        if user_input.lower() in ['quit', 'exit']:
            print("\n👋 Goodbye!")
            break
        
        if user_input.lower() == 'new':
            session_id = None
            conversation_id = None
            message_count = 0
            print("\n🔄 Started new conversation!\n")
            continue
        
        # Send message to API
        message_count += 1
        
        try:
            result = chat(user_input, session_id)
            
            # Check for errors
            if 'error' in result:
                print(f"\n❌ Error: {result['error']}\n")
                continue
            
            # Extract response and session info
            response = result.get('response', 'No response')
            session_id = result.get('session_id')
            conversation_id = result.get('conversation_id')
            
            # Display response
            print(f"\n🤖 AI: {response}")
            print(f"\n   📊 [Message #{message_count} | Session: {session_id[:8]}... | Conv: {conversation_id[:8]}...]")
            print()
            
        except requests.exceptions.ConnectionError:
            print("\n❌ Error: Cannot connect to server. Is it running?")
            print("   Start the server with: ./start_server.sh\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()

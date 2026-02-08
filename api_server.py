"""
nebulaONE API Server

A simple Flask REST API wrapper around the nebulaONE Python client.
This allows you to interact with your AI assistant via HTTP requests from any application.
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from nebula_client import NebulaClient
import json
import os
import csv
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Load configuration from environment variables or config file
AUTH_TOKEN = os.getenv('NEBULA_AUTH_TOKEN', '')
CONFIG_STATE_ID = os.getenv('NEBULA_CONFIG_STATE_ID', '6752e690-6a81-417b-80f5-61b9e99c6c50')
GPT_SYSTEM_ID = os.getenv('NEBULA_GPT_SYSTEM_ID', 'bd74d1b1-7ea5-4974-bdde-1ddf63cb8300')
BASE_URL = os.getenv('NEBULA_BASE_URL', 'https://nebulaone-pilot.uw.edu')

# Optional API key for securing your wrapper API
API_KEY = os.getenv('API_KEY', None)

# Session storage for maintaining conversation state across requests
# Session storage for maintaining conversation state across requests
# Maps session_id -> NebulaClient instance
client_sessions = {}

# Token logging configuration
TOKEN_LOG_FILE = 'data_usage.csv'

def log_data_size(session_id, input_text, output_text):
    """
    Log data size (in characters) to a CSV file.
    """
    try:
        input_chars = len(input_text) if input_text else 0
        output_chars = len(output_text) if output_text else 0
        total_chars = input_chars + output_chars
        
        timestamp = datetime.now().isoformat()
        
        file_exists = os.path.isfile(TOKEN_LOG_FILE)
        
        with open(TOKEN_LOG_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'session_id', 'input_chars', 'output_chars', 'total_chars'])
            
            writer.writerow([timestamp, session_id, input_chars, output_chars, total_chars])
            
        print(f"Logged usage for session {session_id}: {total_chars} chars")
        
    except Exception as e:
        print(f"Error logging data size: {e}")



def require_api_key(f):
    """Decorator to require API key if configured."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if API_KEY:
            provided_key = request.headers.get('X-API-Key')
            if not provided_key or provided_key != API_KEY:
                return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_or_create_client(session_id=None):
    """Get existing client for session or create a new one."""
    import uuid
    
    # If no session_id provided, generate a new one
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Return existing client if session exists
    if session_id in client_sessions:
        return client_sessions[session_id], session_id
    
    # Create new client for this session
    token = request.headers.get('X-Nebula-Token', AUTH_TOKEN)
    if not token:
        raise ValueError("No authentication token provided")
    
    client = NebulaClient(
        auth_token=token,
        config_state_id=CONFIG_STATE_ID,
        gpt_system_id=GPT_SYSTEM_ID,
        base_url=BASE_URL
    )
    
    # Store client in session
    client_sessions[session_id] = client
    
    return client, session_id


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'nebulaONE API Wrapper'
    })


@app.route('/chat', methods=['POST'])
@require_api_key
def chat():
    """
    Simple chat endpoint - send a message and get the complete response.
    
    Request body:
    {
        "message": "Your question here"
    }
    
    Response:
    {
        "response": "AI assistant's response"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Missing "message" field in request body'}), 400
        
        message = data['message']
        session_id = data.get('session_id', None)
        
        client, session_id = get_or_create_client(session_id)
        
        response = client.chat(message)
        
        # Log data size
        log_data_size(session_id, message, response)
        
        return jsonify({
            'response': response,
            'session_id': session_id,
            'conversation_id': client.get_conversation_id()
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@app.route('/chat/stream', methods=['POST'])
@require_api_key
def chat_stream():
    """
    Streaming chat endpoint - get response chunks in real-time.
    
    Request body:
    {
        "message": "Your question here",
        "session_id": "optional-session-id"  // optional, for conversation continuation
    }
    
    Response: Server-Sent Events stream with chunks
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Missing "message" field in request body'}), 400
        
        message = data['message']
        session_id = data.get('session_id', None)
        
        client, session_id = get_or_create_client(session_id)
        
        def generate():
            """Generator function for streaming response."""
            chunks = []
            
            # Send the message and stream response
            for chunk in client.stream_chat_generator(message, session_identifier=session_id):
                chunks.append(chunk)
                # Send as Server-Sent Event
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            
            # Send completion event with session info
            # Note: client.conversation_id is updated by stream_chat_generator
            full_response = "".join(chunks)
            log_data_size(session_id, message, full_response)
            
            yield f"data: {json.dumps({'done': True, 'full_response': full_response, 'session_id': session_id, 'conversation_id': client.get_conversation_id()})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@app.route('/chat/full', methods=['POST'])
@require_api_key
def chat_full():
    """
    Full response endpoint - get complete response data including metadata.
    
    Request body:
    {
        "message": "Your question here",
        "session_id": "optional-session-id"  // optional, for conversation continuation
    }
    
    Response:
    {
        "conversation_id": "uuid",
        "segment_id": "uuid",
        "response": "AI assistant's response",
        "status_updates": ["Thinking", ...],
        "session_id": "session-id"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Missing "message" field in request body'}), 400
        
        message = data['message']
        session_id = data.get('session_id', None)
        
        client, session_id = get_or_create_client(session_id)
        result = client.send_message(message)
        
        # Log data size
        log_data_size(session_id, message, result.get('response', ''))
        
        # Add session_id to result
        result['session_id'] = session_id
        
        return jsonify(result)
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@app.route('/session/new', methods=['POST'])
@require_api_key
def new_session():
    """
    Start a new session (clears conversation history).
    
    Request body:
    {
        "session_id": "optional-existing-session-id"  // optional
    }
    
    Response:
    {
        "session_id": "new-or-existing-session-id",
        "message": "New conversation started"
    }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', None)
        
        client, session_id = get_or_create_client(session_id)
        client.new_conversation()
        
        return jsonify({
            'session_id': session_id,
            'message': 'New conversation started'
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Internal error: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET /health',
            'POST /chat',
            'POST /chat/stream',
            'POST /chat/full'
        ]
    }), 404


if __name__ == '__main__':
    # Auto-refresh token on startup
    # Only run token refresh in the main process, not in the reloader child process
    # This prevents the browser from opening twice
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print("\n🔄 Checking authentication token...")
        try:
            from refresh_token import get_fresh_token, update_env_file
            
            # Try to get fresh token
            token = get_fresh_token()
            if token:
                update_env_file(token)
                # Reload environment variables
                load_dotenv(override=True)
                AUTH_TOKEN = os.getenv('NEBULA_AUTH_TOKEN', '')
                print("✅ Token refreshed successfully!\n")
            else:
                print("⚠️  Using existing token from .env file\n")
        except ImportError:
            print("⚠️  refresh_token.py not found, using existing token\n")
        except Exception as e:
            print(f"⚠️  Token refresh failed: {e}")
            print("   Using existing token from .env file\n")
    else:
        # Reloader process - just reload the env vars in case they changed
        load_dotenv(override=True)
        AUTH_TOKEN = os.getenv('NEBULA_AUTH_TOKEN', '')
    
    # Check if token is configured
    if not AUTH_TOKEN:
        print("WARNING: NEBULA_AUTH_TOKEN not set. You must provide it via X-Nebula-Token header.")
    
    print("\n" + "="*60)
    print("nebulaONE API Server Starting")
    print("="*60)
    print(f"Config State ID: {CONFIG_STATE_ID}")
    print(f"GPT System ID: {GPT_SYSTEM_ID}")
    print(f"Base URL: {BASE_URL}")
    print(f"API Key Protection: {'Enabled' if API_KEY else 'Disabled'}")
    print("="*60)
    print("\nAvailable endpoints:")
    print("  GET  /health          - Health check")
    print("  POST /chat            - Simple chat")
    print("  POST /chat/stream     - Streaming chat")
    print("  POST /chat/full       - Full response data")
    print("  POST /session/new     - Start new conversation")
    print("="*60 + "\n")
    
    # Run the server
    app.run(
        host='0.0.0.0',
        port=8000,
        debug=False
    )

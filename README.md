# Nebula-Automate

This project provides an automated interface for interacting with the nebulaONE AI assistant via a local REST API. It includes tools for processing MMLU (Massive Multitask Language Understanding) datasets and logging conversation data.

## Prerequisites

- Python 3.8 or higher
- `pip` (Python package installer)

## Setup

1.  **Clone the repository** (if you haven't already).

2.  **Install Dependencies**:
    You can install the required Python packages using `pip`:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**:
    The application requires a `.env` file to store configuration and authentication tokens. A header for this file looks like this:

    ```env
    # .env file
    
    # Your nebulaONE JWT token (Required)
    # When run in Antigravity and have the browser tool, this isfetched automatically when you login. You can also obtain this from your browser's local storage when logged into nebulaONE:
    # JSON.parse(localStorage.getItem('persist:auth')).n1aiToken
    NEBULA_AUTH_TOKEN='your_jwt_token_here'

    # Configuration State ID (Can be fetched from a particular chat agent once we start a conversation with it. )
    # NEBULA_CONFIG_STATE_ID=your_config_id

    # GPT System ID (Optional - copy the same above config id here if this throws an error)
    # NEBULA_GPT_SYSTEM_ID=your_system_id

    # Base URL (Do not change)
    # NEBULA_BASE_URL=https://nebulaone-pilot.uw.edu
    ```

## Running the Project

The project consists of a local API server and client scripts that interact with it.

### 1. Start the API Server

The server acts as a bridge between your local scripts and the nebulaONE backend.

You can start the server using the provided helper script:

```bash
./start_server.sh
```

Another way, you can run it directly with Python:

```bash
python api_server.py
```

The server will start at `http://localhost:8000`.
It includes a health check endpoint at `http://localhost:8000/health`.


For testing conversation from terminal, you can run the python script chat.py in a new terminal.

```bash
python chat.py
```

This will start a conversation with the AI model in the terminal. You can type your messages and get responses from the AI model.


To run an experiement, we let Antigravity AI create a script and run the experiment. 

Take a look at the sample_command.txt file to understand the format we give to Antigravity AI sidebar.

Running that query generates the process_mmlu.py script, which Antigravity Ai automatically runs and records the results in mmlu_results_v2.csv file.



## API Endpoints

The local server exposes the following endpoints:

-   `GET /health`: Check if the server is running.
-   `POST /chat`: Send a message and get a complete response.
    ```json
    { "message": "Your question" }
    ```
-   `POST /chat/stream`: Stream the response in real-time (Server-Sent Events).
-   `POST /chat/full`: Get the full response object including metadata.
-   `POST /session/new`: Start a new conversation session.

## Logs

-   **Data Usage**: Token usage and character counts are logged to `data_usage.csv`.

## Troubleshooting

-   **Token Expiry**: If you receive authentication errors, your `NEBULA_AUTH_TOKEN` in `.env` may have expired. Update it with a fresh token from your browser or by restarting the servers.
-   **Port Conflicts**: If port 8000 is in use, modify the `port` argument in `api_server.py` or free up the port.

#!/usr/bin/env python
"""Test script for prep session SSE events."""

import requests
import sseclient
import time
from threading import Thread

API_URL = "http://localhost:8001"


def listen_to_events(prep_session_id):
    """Listen to SSE events for a prep session."""
    url = f"{API_URL}/api/prep-sessions/{prep_session_id}/events"
    print(f"🔌 Connecting to SSE: {url}")

    response = requests.get(url, stream=True, headers={"Accept": "text/event-stream"})
    client = sseclient.SSEClient(response)

    for event in client.events():
        print(f"📥 Event: {event.event}")
        print(f"   Data: {event.data}")

        if event.event == "PREP_STATUS_CHANGED":
            print("✅ Prep session status changed!")
            break


def main():
    # Get an existing prep session that's in preparing state
    print("🔍 Looking for a preparing prep session...")

    response = requests.get(f"{API_URL}/api/prep-sessions", params={"status": "preparing"})
    data = response.json()

    if not data["prepSessions"]:
        print("❌ No preparing prep sessions found. Please create a new deck first.")
        print("   You can upload a deck via the UI or run the deck creation flow.")
        return

    prep_session = data["prepSessions"][0]
    prep_session_id = prep_session["id"]
    print(f"✅ Found prep session: {prep_session_id} (status: {prep_session['status']})")

    # Start listening to events in background
    listener_thread = Thread(target=listen_to_events, args=(prep_session_id,), daemon=True)
    listener_thread.start()

    print("⏳ Listening for events... (waiting for analysis to complete)")
    print("   Press Ctrl+C to stop")

    try:
        listener_thread.join(timeout=300)  # Wait up to 5 minutes
    except KeyboardInterrupt:
        print("\n👋 Stopped listening")


if __name__ == "__main__":
    main()

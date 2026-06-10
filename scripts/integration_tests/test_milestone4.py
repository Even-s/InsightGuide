#!/usr/bin/env python3
"""
Test script for Milestone 4: Realtime Transcription Integration

This script tests:
1. Creating presentation sessions
2. Getting ephemeral tokens for Realtime API
3. Creating utterances
4. Session management
"""

import requests
import json
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8001/api"


def test_realtime_token():
    """Test 1: Create ephemeral token for Realtime API."""
    print("\n" + "="*60)
    print("TEST 1: Create Realtime API Ephemeral Token")
    print("="*60)

    response = requests.post(f"{API_BASE_URL}/realtime/session")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Ephemeral token created")
        print(f"   Model: {data.get('model')}")
        print(f"   Voice: {data.get('voice')}")
        print(f"   Token: {data.get('token')[:30]}...")
        print(f"   Expires at: {data.get('expiresAt')}")
        return True
    else:
        print(f"❌ Failed to create token: {response.status_code}")
        print(response.text)
        return False


def test_presentation_session(deck_id):
    """Test 2: Create and manage presentation session."""
    print("\n" + "="*60)
    print("TEST 2: Presentation Session Management")
    print("="*60)

    # Create session
    print("\n📝 Creating presentation session...")
    response = requests.post(
        f"{API_BASE_URL}/presentation-sessions/",
        json={"deckId": deck_id}
    )

    if response.status_code != 201:
        print(f"❌ Failed to create session: {response.status_code}")
        print(response.text)
        return None

    session = response.json()
    session_id = session["id"]
    print(f"✅ Session created: {session_id}")
    print(f"   Status: {session['status']}")
    print(f"   Deck ID: {session['deckId']}")

    # Get session
    print(f"\n📊 Retrieving session...")
    response = requests.get(f"{API_BASE_URL}/presentation-sessions/{session_id}")
    if response.status_code == 200:
        print(f"✅ Session retrieved successfully")
    else:
        print(f"❌ Failed to retrieve session")

    # Update session status to presenting
    print(f"\n▶️  Starting presentation...")
    response = requests.patch(
        f"{API_BASE_URL}/presentation-sessions/{session_id}",
        json={"status": "presenting"}
    )

    if response.status_code == 200:
        session = response.json()
        print(f"✅ Session status updated to: {session['status']}")
        print(f"   Started at: {session['startedAt']}")
    else:
        print(f"❌ Failed to update session")

    return session_id


def test_utterances(session_id):
    """Test 3: Create and retrieve utterances."""
    print("\n" + "="*60)
    print("TEST 3: Utterance Management")
    print("="*60)

    utterances_data = [
        {
            "transcript": "今天我們要介紹機器學習的三大類型",
            "slideId": None
        },
        {
            "transcript": "首先是監督式學習，它使用標記過的資料進行訓練",
            "slideId": None
        },
        {
            "transcript": "接下來是非監督式學習，用來找出資料中的隱藏模式",
            "slideId": None
        }
    ]

    created_utterances = []

    for i, utt_data in enumerate(utterances_data, 1):
        print(f"\n💬 Creating utterance {i}...")
        response = requests.post(
            f"{API_BASE_URL}/presentation-sessions/{session_id}/utterances",
            json=utt_data
        )

        if response.status_code == 201:
            utterance = response.json()
            created_utterances.append(utterance)
            print(f"✅ Utterance created: {utterance['id']}")
            print(f"   Transcript: {utterance['transcript'][:50]}...")
        else:
            print(f"❌ Failed to create utterance: {response.status_code}")
            print(response.text)

    # Get all utterances
    print(f"\n📜 Retrieving all utterances for session...")
    response = requests.get(
        f"{API_BASE_URL}/presentation-sessions/{session_id}/utterances"
    )

    if response.status_code == 200:
        utterances = response.json()
        print(f"✅ Retrieved {len(utterances)} utterances")
        for utt in utterances:
            print(f"   - {utt['transcript'][:50]}...")
    else:
        print(f"❌ Failed to retrieve utterances")

    return len(created_utterances) == len(utterances_data)


def test_card_states(session_id):
    """Test 4: Get card states for session."""
    print("\n" + "="*60)
    print("TEST 4: Card States")
    print("="*60)

    print(f"\n🎯 Retrieving card states for session...")
    response = requests.get(
        f"{API_BASE_URL}/presentation-sessions/{session_id}/card-states"
    )

    if response.status_code == 200:
        card_states = response.json()
        print(f"✅ Retrieved {len(card_states)} card states")

        # Group by status
        status_counts = {}
        for cs in card_states:
            status = cs['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"\n   Card states by status:")
        for status, count in status_counts.items():
            print(f"   - {status}: {count}")

        return len(card_states) > 0
    else:
        print(f"❌ Failed to retrieve card states")
        return False


def test_end_session(session_id):
    """Test 5: End presentation session."""
    print("\n" + "="*60)
    print("TEST 5: End Session")
    print("="*60)

    print(f"\n🛑 Ending presentation session...")
    response = requests.post(
        f"{API_BASE_URL}/presentation-sessions/{session_id}/end"
    )

    if response.status_code == 200:
        session = response.json()
        print(f"✅ Session ended successfully")
        print(f"   Status: {session['status']}")
        print(f"   Ended at: {session['endedAt']}")
        return True
    else:
        print(f"❌ Failed to end session")
        return False


def get_or_create_test_deck():
    """Get an existing analyzed deck or return None."""
    print("\n" + "="*60)
    print("SETUP: Finding Test Deck")
    print("="*60)

    # For testing, we'll use an existing deck from Milestone 2
    # In practice, you should upload and analyze a deck first
    print("\n📋 Please provide a deck ID from Milestone 2 test,")
    print("   or press Enter to skip (some tests will be limited)")

    deck_id = input("Deck ID: ").strip()

    if deck_id:
        # Verify deck exists and is analyzed
        response = requests.get(f"{API_BASE_URL}/decks/{deck_id}")
        if response.status_code == 200:
            deck = response.json()
            if deck['status'] == 'analyzed':
                print(f"✅ Using deck: {deck['title']}")
                print(f"   Status: {deck['status']}")
                return deck_id
            else:
                print(f"⚠️  Deck status is '{deck['status']}', not 'analyzed'")
        else:
            print(f"❌ Deck not found")

    print("⚠️  No deck provided - some tests will be skipped")
    return None


def main():
    """Run all Milestone 4 tests."""
    print("="*60)
    print("MILESTONE 4 TEST: Realtime Transcription Integration")
    print("="*60)

    results = []

    # Test 1: Realtime token
    results.append(("Realtime Token Creation", test_realtime_token()))

    # Get test deck
    deck_id = get_or_create_test_deck()

    if deck_id:
        # Test 2: Presentation session
        session_id = test_presentation_session(deck_id)

        if session_id:
            # Test 3: Utterances
            results.append(("Utterance Management", test_utterances(session_id)))

            # Test 4: Card states
            results.append(("Card States Retrieval", test_card_states(session_id)))

            # Test 5: End session
            results.append(("End Session", test_end_session(session_id)))
        else:
            print("\n⚠️  Session creation failed, skipping remaining tests")
    else:
        print("\n⚠️  No deck available, skipping session tests")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  Some tests failed")

    print(f"{'='*60}\n")

    return passed == total


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

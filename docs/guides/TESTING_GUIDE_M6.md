# 🧪 Milestone 6 Testing Guide

**Last Updated**: 2026-05-25  
**Purpose**: Step-by-step guide for testing the completed Presenter Mode UI

---

## 🚀 Quick Start

### 1. Start Backend

```bash
cd /Users/cfh00914977/Project/SlideCue

# Start infrastructure (if not already running)
docker-compose -f docker-compose.full.yml up -d

# Start backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

Verify backend is running:
```bash
curl http://localhost:8001/health
# Should return: {"status":"healthy","environment":"development"}
```

### 2. Start Frontend

```bash
cd /Users/cfh00914977/Project/SlideCue/frontend
npm run dev
```

Frontend will be available at: http://localhost:5173

### 3. Verify Setup

- Backend API Docs: http://localhost:8001/docs
- Frontend: http://localhost:5173
- MinIO Console: http://localhost:9001 (admin/minioadmin)

---

## 📝 Test Scenarios

### Scenario 1: Complete Presentation Flow

**Objective**: Test the full end-to-end presentation experience

#### Steps:

1. **Upload Deck**
   - Navigate to http://localhost:5173
   - Click upload area or drag-and-drop a PPTX file
   - Wait for upload to complete
   - Observe: Progress indicator shows upload status

2. **Wait for Analysis**
   - System processes PPTX
   - AI analyzes slides and generates topic cards
   - Wait until "開始演講" button appears
   - Expected: 30-60 seconds depending on deck size

3. **Enter Presenter Mode**
   - Click "開始演講" button
   - System creates new presentation session
   - Observe: Loads into presenter layout

4. **Grant Microphone Access**
   - Browser prompts for microphone permission
   - Click "Allow"
   - Observe: Microphone icon appears in browser tab

5. **Start Presentation**
   - Click "開始" button in control bar
   - Observe:
     - Button changes to "暫停"
     - Recording indicator appears (red dot)
     - Status shows "presenting"

6. **Speak and Observe Transcription**
   - Speak clearly into microphone
   - Observe:
     - Real-time transcript appears in TranscriptDisplay
     - Text streams as you speak (delta updates)
     - Completed sentences appear in main transcript area

7. **Watch Card Status Updates**
   - Speak keywords matching topic cards
   - Observe:
     - Cards change color when matched
     - Green checkmark (✓) for covered cards
     - Yellow for probably_covered
     - Red warning (⚠) for at_risk cards
     - Confidence score updates

8. **Navigate Slides**
   - Click "下一張" button OR press → key
   - Observe:
     - Slide image updates
     - Slide counter increments (e.g., 2 / 10)
     - Cards filter to current slide

9. **Test Pause/Resume**
   - Click "暫停" button OR press Space key
   - Observe:
     - Recording stops
     - Status changes to "paused"
   - Click "繼續" to resume
   - Observe:
     - Recording restarts
     - Status changes back to "presenting"

10. **Manual Card Override**
    - Find a pending card
    - Click "標記為已講" button
    - Observe:
      - Card immediately turns green with ✓
      - Backend updates via API
    - Click "重置" on the same card
    - Observe:
      - Card returns to pending state

11. **End Session**
    - Click "結束" button
    - Confirm in dialog (if prompted)
    - Observe:
      - Session report appears
      - Statistics shown:
        - Coverage rate
        - Cards by status
        - Performance metrics

12. **Review Report**
    - Check coverage statistics
    - Review cards by status
    - Click "返回編輯" or "重新開始"

**Expected Results**:
- ✅ All steps complete without errors
- ✅ Transcription appears in real-time
- ✅ Cards update automatically
- ✅ Visual feedback is clear and responsive
- ✅ Navigation works smoothly
- ✅ Report shows accurate statistics

---

### Scenario 2: Keyboard Shortcuts

**Objective**: Verify all keyboard shortcuts work correctly

#### Steps:

1. Enter presenter mode (start presentation)
2. Press → (right arrow)
   - Expected: Next slide
3. Press ← (left arrow)
   - Expected: Previous slide
4. Press Space
   - Expected: Toggle pause/resume
5. Verify shortcuts work consistently

**Expected Results**:
- ✅ All keyboard shortcuts respond instantly
- ✅ No conflicts with browser shortcuts

---

### Scenario 3: SSE Event Handling

**Objective**: Test real-time card status updates via SSE

#### Steps:

1. Start presentation
2. Open browser DevTools → Network tab
3. Filter for "EventSource" or search for "stream"
4. Speak to trigger card matches
5. Observe SSE events in network tab:
   - `CARD_COVERED`
   - `CARD_PROBABLY_COVERED`
   - `CARD_AT_RISK`
   - `CARD_SKIPPED`

6. Verify cards update in UI immediately after events

**Expected Results**:
- ✅ SSE connection established
- ✅ Events received in real-time
- ✅ UI updates match events
- ✅ Connection auto-reconnects if dropped

---

### Scenario 4: Error Handling

**Objective**: Verify error states are handled gracefully

#### Steps:

1. **Deny Microphone Permission**
   - Enter presenter mode
   - Deny microphone when prompted
   - Expected: Clear error message displayed
   - Should be able to retry

2. **Network Disconnection**
   - Start presentation
   - Disconnect network (turn off Wi-Fi)
   - Expected: SSE reconnection attempts
   - Reconnect network
   - Expected: Connection restores automatically

3. **Backend Down**
   - Stop backend server
   - Try to create new session
   - Expected: Error message with retry option

4. **Invalid Deck ID**
   - Navigate to `/presenter/invalid-id`
   - Expected: Error message, redirect to home

**Expected Results**:
- ✅ All errors show user-friendly messages
- ✅ Recovery options provided
- ✅ No crashes or white screens

---

### Scenario 5: Long Session

**Objective**: Test stale session detection

#### Steps:

1. Create a presentation session
2. Modify session `startedAt` to be > 1 hour ago (via API or DB)
3. Reload presenter page
4. Observe:
   - Warning dialog appears
   - Options to end or continue
5. Test both options

**Expected Results**:
- ✅ Warning appears for sessions > 1 hour
- ✅ "End" option works correctly
- ✅ "Continue" option allows proceeding (not recommended)

---

### Scenario 6: Multiple Cards Match

**Objective**: Verify handling of multiple simultaneous matches

#### Steps:

1. Start presentation
2. Speak a sentence that matches multiple topic cards
3. Observe:
   - Multiple cards update
   - Each shows appropriate status
   - Confidence scores vary
   - Evidence shown for each

**Expected Results**:
- ✅ All matched cards update
- ✅ No race conditions
- ✅ UI remains responsive

---

### Scenario 7: Edge Cases

**Objective**: Test unusual but valid scenarios

#### Test Cases:

1. **Empty Deck**
   - Upload PPTX with no text
   - Enter presenter mode
   - Expected: Works, but no cards

2. **Single Slide**
   - Upload 1-slide PPTX
   - Test navigation
   - Expected: Previous/Next disabled appropriately

3. **Many Cards (50+)**
   - Upload large deck
   - Check performance
   - Expected: Smooth scrolling, no lag

4. **Long Transcript**
   - Speak continuously for 5+ minutes
   - Check transcript display
   - Expected: Scrolls automatically, no overflow

5. **Rapid Slide Changes**
   - Press → key rapidly (10 times)
   - Expected: All changes register, no skips

6. **Simultaneous Actions**
   - Change slide while speaking
   - Expected: Both actions complete, no conflicts

**Expected Results**:
- ✅ All edge cases handled gracefully
- ✅ No performance degradation
- ✅ UI remains stable

---

## 🐛 Known Issues

### None Currently Identified

If you find issues during testing, document them with:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Browser/OS
- Screenshots if applicable

---

## 📊 Performance Benchmarks

### Target Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Initial Load | < 3s | DevTools → Performance |
| Transcription Latency | < 1s | Speak → see text |
| SSE Event Latency | < 500ms | Event → UI update |
| Slide Navigation | < 100ms | Click → image change |
| Card Status Update | < 200ms | SSE event → color change |

### How to Test Performance

1. **Initial Load Time**
```bash
# Open DevTools → Performance
# Start recording
# Navigate to http://localhost:5173
# Stop recording when page is interactive
# Check "Load" event timing
```

2. **Transcription Latency**
```bash
# Start presentation
# Use stopwatch or timer
# Speak a word
# Measure time until it appears in transcript
# Target: < 1 second
```

3. **SSE Latency**
```bash
# Open DevTools → Network → EventSource
# Speak a keyword that matches a card
# Check timestamp of SSE event vs UI update
# Target: < 500ms
```

---

## ✅ Test Checklist

### Basic Functionality
- [ ] Upload PPTX file
- [ ] View deck analysis
- [ ] Enter presenter mode
- [ ] Grant microphone permission
- [ ] Start presentation
- [ ] Real-time transcription works
- [ ] Cards update via SSE
- [ ] Navigate slides (buttons)
- [ ] Navigate slides (keyboard)
- [ ] Pause/resume works
- [ ] Manual card marking works
- [ ] End session
- [ ] View session report

### Error Handling
- [ ] Microphone denied → error message
- [ ] Network disconnect → reconnection
- [ ] Backend down → error message
- [ ] Invalid deck ID → error message

### Edge Cases
- [ ] Empty deck
- [ ] Single slide
- [ ] Many cards (50+)
- [ ] Long transcript
- [ ] Rapid slide changes
- [ ] Simultaneous actions

### Performance
- [ ] Initial load < 3s
- [ ] Transcription latency < 1s
- [ ] SSE latency < 500ms
- [ ] Slide navigation < 100ms
- [ ] No memory leaks (check DevTools)

### UI/UX
- [ ] All colors/states visible
- [ ] Animations smooth
- [ ] Responsive layout
- [ ] Loading indicators clear
- [ ] Error messages clear
- [ ] Keyboard shortcuts work

### Browser Compatibility
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

---

## 🔍 Debugging Tips

### Frontend Issues

1. **Check Console**
```bash
# Open DevTools → Console
# Look for errors or warnings
```

2. **Check Network**
```bash
# Open DevTools → Network
# Filter by "Fetch/XHR" for API calls
# Filter by "EventSource" for SSE
# Check for failed requests (red)
```

3. **Check React DevTools**
```bash
# Install React DevTools extension
# Open Components tab
# Inspect component state and props
```

### Backend Issues

1. **Check Backend Logs**
```bash
cd /Users/cfh00914977/Project/SlideCue/backend
tail -f logs/app.log  # if logging to file
# Or check terminal where uvicorn is running
```

2. **Check API Directly**
```bash
# Test specific endpoint
curl -X GET http://localhost:8001/api/presentation-sessions/SESSION_ID

# Check SSE endpoint
curl -N http://localhost:8001/api/events/sessions/SESSION_ID/stream
```

3. **Check Database**
```bash
# Connect to PostgreSQL
docker exec -it slidecue-postgres psql -U postgres -d slidecue

# Query session
SELECT * FROM presentation_sessions WHERE id = 'SESSION_ID';

# Query card states
SELECT * FROM presentation_card_states WHERE session_id = 'SESSION_ID';
```

---

## 📞 Support

If you encounter issues:

1. Check this testing guide
2. Review `MILESTONE_6_SUMMARY.md` for details
3. Check the Milestone 6 testing checklist in `MILESTONE_6_SUMMARY.md`
4. Review component implementation in `frontend/src/`
5. Check backend logs for API errors

---

## 🎉 Success Criteria

Milestone 6 testing is considered successful when:

- ✅ All test scenarios pass
- ✅ No critical bugs found
- ✅ Performance meets targets
- ✅ Error handling works correctly
- ✅ UI/UX is intuitive and responsive
- ✅ Works in all major browsers

---

**Happy Testing!** 🚀

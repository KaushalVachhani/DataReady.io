# DataReady.io - System Architecture

## Overview

DataReady.io is an AI-powered data engineering mock interview platform that simulates realistic technical interviews with adaptive questioning, real-time audio interaction, and comprehensive feedback.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (HTML/CSS/JS)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────────────────┐ │
│  │ Setup Page  │  │ Interview Room  │  │      Report Dashboard            │ │
│  │             │  │                 │  │                                  │ │
│  │ • Role      │  │ • Webcam View   │  │ • Score Radar                    │ │
│  │ • Experience│  │ • AI Avatar     │  │ • Skill Breakdown                │ │
│  │ • Skills    │  │ • Transcription │  │ • Recommendations                │ │
│  │ • Mode      │  │ • Progress      │  │ • Hiring Verdict                 │ │
│  └─────────────┘  └─────────────────┘  └──────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ WebSocket + REST API
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (Python FastAPI)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    INTERVIEW ORCHESTRATOR                           │    │
│  │  • State Machine Management                                         │    │
│  │  • Session Lifecycle                                                │    │
│  │  • Flow Control (Question → Response → Evaluation → Next)           │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                           │
│  ┌──────────────┬───────────────┼───────────────┬──────────────────────┐    │
│  │              │               │               │                      │    │
│  ▼              ▼               ▼               ▼                      │    │
│ ┌────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │    │
│ │   AI       │ │   Audio     │ │ Evaluation  │ │     Report          │ │    │
│ │ Reasoning  │ │ Processing  │ │   Engine    │ │   Generator         │ │    │
│ │   Layer    │ │   Layer     │ │             │ │                     │ │    │
│ ├────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────────────┤ │    │
│ │• Question  │ │• STT        │ │• Scoring    │ │• Overall Score      │ │    │
│ │  Generation│ │  (Whisper)  │ │  Rubric     │ │• Skill Radar        │ │    │
│ │• Follow-up │ │• TTS        │ │• Per-Q      │ │• Strengths          │ │    │
│ │  Logic     │ │  (Kokoro/   │ │  Feedback   │ │• Weaknesses         │ │    │
│ │• Difficulty│ │   Piper)    │ │• Red Flags  │ │• Hiring Verdict     │ │    │
│ │  Adapt     │ │             │ │             │ │• Study Roadmap      │ │    │
│ └────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘ │    │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    EXTERNAL AI SERVICES                             │    │
│  │  • Gemini 3 Pro (Databricks) - Deep reasoning, evaluation          │    │
│  │  • Gemini Flash (Databricks) - Fast conversational responses       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Interview Orchestrator

**Responsibility**: Manages the entire interview lifecycle using a state machine.

**States**:
```
SETUP → READY → ASKING → LISTENING → PROCESSING → EVALUATING → DECIDING → (ASKING | COMPLETE)
```

**State Transitions**:
- `SETUP`: User configures interview parameters
- `READY`: System initialized, waiting to start
- `ASKING`: AI is speaking the question
- `LISTENING`: Recording user's response
- `PROCESSING`: Transcribing audio to text
- `EVALUATING`: AI scoring the response
- `DECIDING`: Determining next action (follow-up, next question, or end)
- `COMPLETE`: Interview finished, generating report

### 2. AI Reasoning Layer

**Responsibilities**:
- Generate role-appropriate questions
- Determine follow-up questions based on response quality
- Adapt difficulty dynamically
- Evaluate responses against rubric

**Model Usage**:
| Task | Model | Reason |
|------|-------|--------|
| Question generation | Gemini 3 Pro | Deep reasoning required |
| Follow-up decision | Gemini Flash | Low-latency needed |
| Response evaluation | Gemini 3 Pro | Accurate scoring |
| Conversational flow | Gemini Flash | Fast responses |

### 3. Audio Processing Layer

**Components**:
- **STT (Speech-to-Text)**: Whisper Large V3
  - Transcribes user responses
  - Handles pauses, filler words, technical terms
  
- **TTS (Text-to-Speech)**: Kokoro TTS / Piper
  - Generates natural-sounding interviewer voice
  - Professional, calm tone

### 4. Evaluation Engine

**Per-Question Scoring** (0-10 each):
- Technical Correctness
- Depth of Understanding
- Practical Experience
- Communication Clarity
- Confidence

**Feedback Storage**:
```json
{
  "question_id": "q_001",
  "scores": { ... },
  "what_went_well": ["..."],
  "what_was_missing": ["..."],
  "red_flags": ["..."],
  "seniority_signals": ["..."]
}
```

### 5. Report Generator

**Output Sections**:
- Overall Performance Score (0-100)
- Skill-wise Radar Chart Data
- Role Readiness Verdict
- Strengths Summary
- Improvement Areas
- Suggested Next Steps
- Hiring Verdict (Strong Hire / Hire / Borderline / Needs Improvement)

---

## Data Flow

### Interview Flow Sequence

```
1. User completes setup form
   └─→ POST /api/interview/setup
       └─→ Creates InterviewSession
           └─→ Returns session_id

2. User starts interview
   └─→ WebSocket /ws/interview/{session_id}
       └─→ AI generates first question
           └─→ TTS converts to audio
               └─→ Audio streamed to frontend

3. User responds verbally
   └─→ Audio chunks sent via WebSocket
       └─→ Whisper transcribes
           └─→ Transcript stored

4. Response evaluated
   └─→ Gemini evaluates response
       └─→ Scores stored
           └─→ Follow-up decision made

5. Repeat until 10 questions completed or early termination

6. Interview ends
   └─→ GET /api/report/{session_id}
       └─→ Report Generator compiles data
           └─→ Full report returned
```

---

## API Design

### REST Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/interview/setup` | Create interview session |
| GET | `/api/interview/{id}/status` | Get session status |
| POST | `/api/interview/{id}/start` | Begin interview |
| POST | `/api/interview/{id}/end` | End interview early |
| GET | `/api/report/{id}` | Get final report |
| GET | `/api/skills` | List available skills |
| GET | `/api/roles` | List available roles |

### WebSocket

| Channel | Purpose |
|---------|---------|
| `/ws/interview/{session_id}` | Real-time interview communication |

**WebSocket Message Types**:
- `audio_chunk`: Binary audio data
- `transcript`: Transcribed text
- `question`: AI question (text + audio)
- `state_change`: Interview state update
- `evaluation_complete`: Per-question eval done

---

## Skill & Role Definitions

### Roles

```python
class Role(Enum):
    JUNIOR_DE = "junior_data_engineer"      # 0-2 years
    MID_DE = "mid_data_engineer"            # 2-5 years
    SENIOR_DE = "senior_data_engineer"      # 5-8 years
    STAFF_DE = "staff_data_engineer"        # 8+ years
    PRINCIPAL_DE = "principal_data_engineer" # 10+ years
```

### Skill Categories by Role

| Role | Focus Areas |
|------|-------------|
| Junior | SQL basics, ETL concepts, Git, Linux, Cloud fundamentals |
| Mid | Advanced SQL, Spark, Orchestration, Data quality |
| Senior | Platform design, Performance, Distributed systems, Streaming |
| Staff/Principal | Architecture, Governance, Multi-cloud, Org impact |

---

## Follow-up Decision Tree

```
User Response Received
        │
        ▼
┌───────────────────┐
│ Evaluate Response │
└─────────┬─────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│ Response Quality?                                │
├──────────────┬──────────────┬───────────────────┤
│   Shallow    │   Moderate   │      Strong       │
│              │              │                   │
▼              ▼              ▼
Ask for        Ask for        Increase
deeper         example/       difficulty
explanation    scenario       OR next topic
```

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML5, CSS3, Vanilla JS |
| Backend | Python 3.12, FastAPI, Uvicorn |
| AI Models | Gemini 3 Pro/Flash (via Databricks) |
| STT | Whisper Large V3 (local or API) |
| TTS | Kokoro TTS / Piper (open source) |
| Real-time | WebSockets (FastAPI native) |
| State Management | In-memory (Redis for production) |

---

## Security Considerations

- [ ] Rate limiting on API endpoints
- [ ] WebSocket connection authentication
- [ ] Audio data encryption in transit
- [ ] Session timeout handling
- [ ] Input sanitization for all user data

---

## Future Enhancements (Out of Scope Now)

- User authentication
- Resume-based personalization
- Coding challenges
- Video recording playback
- Progress tracking across sessions
- Payment integration

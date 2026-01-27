# Building an AI-Powered Mock Interview Platform: A 3-Part Engineering Guide

---

# Part 1: System Architecture & State Machine Design

## What We're Building

A web-based mock interview platform for data engineers. Users select their experience level and target role, then conduct a verbal interview with an AI interviewer. The system:

- Generates role-appropriate questions using Gemini models
- Processes user audio responses via Whisper
- Evaluates answers in real-time
- Produces detailed performance reports

No fluff. Let's dive into the engineering.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND (HTML/CSS/JS)                      │
│  Setup Page → Interview Room → Report Dashboard             │
└─────────────────────────────┬───────────────────────────────┘
                              │ WebSocket + REST API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 BACKEND (Python FastAPI)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │              INTERVIEW ORCHESTRATOR                    │  │
│  │  State Machine • Session Management • Flow Control     │  │
│  └──────────────────────────┬────────────────────────────┘  │
│           ┌─────────────────┼─────────────────┐              │
│           ▼                 ▼                 ▼              │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐        │
│  │ AI Reasoning│   │   Audio     │   │ Evaluation  │        │
│  │   Layer     │   │ Processing  │   │   Engine    │        │
│  │  (Gemini)   │   │ (Whisper)   │   │             │        │
│  └─────────────┘   └─────────────┘   └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**Why this structure?**

1. **Separation of concerns** - Each component handles one thing well
2. **Testable** - Mock any component for testing
3. **Swappable** - Replace Whisper with another STT without touching the orchestrator

---

## The Interview Orchestrator: A State Machine

The core of the system is a finite state machine. This is the right abstraction because:

- Interviews have clear phases (asking → listening → evaluating)
- State transitions are predictable and validatable
- Makes debugging easier ("Why did it fail?" → "Invalid transition from X to Y")

### States

```python
class InterviewState(str, Enum):
    # Pre-interview
    SETUP = "setup"
    READY = "ready"
    
    # During interview
    ASKING = "asking"        # AI speaking question
    LISTENING = "listening"  # Recording user audio
    PROCESSING = "processing"  # Transcribing
    EVALUATING = "evaluating"  # AI scoring response
    DECIDING = "deciding"    # Next action decision
    
    # Post-interview
    COMPLETE = "complete"
    GENERATING_REPORT = "generating_report"
    FINISHED = "finished"
    
    # Error states
    PAUSED = "paused"
    ERROR = "error"
    CANCELLED = "cancelled"
```

### Valid Transitions

```python
VALID_TRANSITIONS = {
    InterviewState.SETUP: [InterviewState.READY, InterviewState.CANCELLED],
    InterviewState.READY: [InterviewState.ASKING, InterviewState.CANCELLED],
    InterviewState.ASKING: [InterviewState.LISTENING, InterviewState.PAUSED, InterviewState.ERROR],
    InterviewState.LISTENING: [InterviewState.PROCESSING, InterviewState.PAUSED, InterviewState.ERROR],
    InterviewState.PROCESSING: [InterviewState.EVALUATING, InterviewState.ERROR],
    InterviewState.EVALUATING: [InterviewState.DECIDING, InterviewState.ERROR],
    InterviewState.DECIDING: [InterviewState.ASKING, InterviewState.COMPLETE, InterviewState.ERROR],
    InterviewState.COMPLETE: [InterviewState.GENERATING_REPORT],
    InterviewState.GENERATING_REPORT: [InterviewState.FINISHED, InterviewState.ERROR],
}
```

**Key insight**: The `DECIDING` state is crucial. After evaluating a response, we need to decide:
- Ask a follow-up? (go back to `ASKING`)
- Move to next question? (go to `ASKING`)  
- End interview? (go to `COMPLETE`)

### Transition Implementation

```python
async def transition_state(
    self,
    session_id: str,
    new_state: InterviewState,
) -> InterviewSession:
    session = self.get_session(session_id)
    old_state = session.state
    
    # Validate transition
    valid_next_states = self.VALID_TRANSITIONS.get(old_state, [])
    if new_state not in valid_next_states:
        raise StateTransitionError(
            f"Invalid transition from {old_state} to {new_state}"
        )
    
    # Update state
    session.state = new_state
    
    # Handle side effects
    if new_state == InterviewState.READY:
        session.started_at = datetime.utcnow()
    elif new_state == InterviewState.COMPLETE:
        session.completed_at = datetime.utcnow()
    
    # Notify listeners
    for callback in self._state_change_callbacks:
        await callback(session_id, old_state, new_state)
    
    return session
```

---

## Data Models

### Interview Session

The session holds everything about an interview:

```python
class InterviewSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    setup: InterviewSetup
    state: InterviewState = InterviewState.SETUP
    
    # Questions and responses
    questions: list[QuestionResponse] = []
    
    # Tracking
    total_core_questions_asked: int = 0
    total_followups_asked: int = 0
    asked_question_hashes: set[str] = set()  # For deduplication
    current_question_context: list[dict] = []  # Conversation history
    
    # Scoring
    skill_scores: dict[str, list[float]] = {}
    running_score: float = 0.0
    current_difficulty: int = 5
    difficulty_history: list[int] = []
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

**Why `asked_question_hashes`?**

To prevent repetitive questions. When we generate a question, we normalize and hash the text, then check if that hash exists:

```python
def is_question_asked(self, question_text: str) -> bool:
    normalized = self._normalize_question(question_text)
    question_hash = hashlib.md5(normalized.encode()).hexdigest()
    return question_hash in self.asked_question_hashes

def _normalize_question(self, text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text
```

---

## Interview Flow

```
User submits setup → POST /api/interview/setup
                          ↓
                    Create session (SETUP state)
                          ↓
User clicks start → POST /api/interview/{id}/start
                          ↓
                    Transition to READY → Generate first question
                          ↓
              WebSocket /ws/interview/{id}
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
   Question sent                      User responds
   (text + audio)                    (audio stream)
        ↓                                   ↓
   ASKING state                      LISTENING state
                                            ↓
                                    Audio → Whisper → Transcript
                                            ↓
                                    PROCESSING → EVALUATING
                                            ↓
                                    Gemini scores response
                                            ↓
                                    DECIDING state
                                            ↓
                          ┌─────────┴─────────┐
                          ↓                   ↓
                    Follow-up?           Next question?
                          ↓                   ↓
                    Back to ASKING      Back to ASKING
                                              or
                                         COMPLETE
```

---

## Session Storage

For simplicity, we use in-memory storage:

```python
class InterviewOrchestrator:
    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}
    
    def get_session(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)
    
    async def update_session(self, session: InterviewSession) -> None:
        self._sessions[session.session_id] = session
```

**Production note**: Replace with Redis for horizontal scaling. The `InterviewSession` model is Pydantic-based, so serialization is trivial:

```python
# Store
await redis.set(f"session:{session_id}", session.model_dump_json())

# Retrieve
data = await redis.get(f"session:{session_id}")
session = InterviewSession.model_validate_json(data)
```

---

## What's Next

In Part 2, we'll cover:
- AI Reasoning Layer implementation
- Prompt engineering for question generation
- Response evaluation with scoring rubrics
- Handling follow-up decisions

---

# Part 2: AI Integration & Prompt Engineering

## Model Selection Strategy

We use two models with different purposes:

| Task | Model | Why |
|------|-------|-----|
| Question generation | Gemini Pro | Needs deep reasoning about role requirements, skills, difficulty |
| Follow-up decisions | Gemini Flash | Low latency for conversational flow |
| Response evaluation | Gemini Pro | Accurate scoring requires understanding context |

```python
class AIReasoningLayer:
    async def _call_gemini_pro(self, prompt: str, max_tokens: int = 2048) -> str:
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,  # Some creativity for varied questions
        }
        response = await self.client.post(
            self.settings.gemini_pro_endpoint,
            json=payload,
        )
        return self._extract_content(response.json())
    
    async def _call_gemini_flash(self, prompt: str, max_tokens: int = 512) -> str:
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8,  # Slightly higher for natural conversation
        }
        response = await self.client.post(
            self.settings.gemini_flash_endpoint,
            json=payload,
        )
        return self._extract_content(response.json())
```

---

## Question Generation

### The Prompt

The prompt has several critical sections:

```python
def generate_question_prompt(self, context: InterviewContext) -> str:
    prompt = f"""{self.SYSTEM_CONTEXT}

=== INTERVIEW CONTEXT ===
Target Role: {role.display_name} ({role.experience_range})
Experience: {context.session.setup.years_of_experience} years
Cloud Platform: {context.session.setup.cloud_preference.value}
Questions Asked: {context.session.total_core_questions_asked}/{max_questions}
Current Difficulty: {context.session.current_difficulty}/10
Performance Trend: {context.performance_trend}

=== SKILLS CONTEXT ===
Skills Covered: {covered}
Skills Remaining: {remaining}
Priority: Focus on skills NOT YET covered.

=== PREVIOUSLY ASKED QUESTIONS ===
{previous_questions_text}

=== RULES ===
1. DO NOT ask any question similar to those listed above
2. Generate a NEW question on a different topic
3. Match difficulty level {context.session.current_difficulty}/10
4. Prefer scenario-based questions over definitions

=== OUTPUT FORMAT ===
Return JSON only:
{{
    "question_text": "Your question here",
    "skill_id": "relevant_skill_id",
    "difficulty": "easy|medium|hard",
    "expected_points": ["point1", "point2", "point3"]
}}
"""
    return prompt
```

**Key elements**:

1. **System context** - Establishes the AI's role as interviewer
2. **Interview context** - Current state (difficulty, questions asked)
3. **Skills context** - What's been covered vs. what remains
4. **Previously asked questions** - Full list for deduplication
5. **Rules** - Explicit constraints
6. **Output format** - Structured JSON for parsing

### Deduplication: The Hard Part

AI models can generate semantically similar questions even when told not to. We handle this in multiple layers:

**Layer 1: Prompt includes all previous questions**

```python
previous_questions = []
for q in context.session.questions:
    previous_questions.append(f"- {q.question_text}")
previous_questions_text = "\n".join(previous_questions)
```

**Layer 2: Retry loop with hash checking**

```python
async def generate_question(self, context: InterviewContext) -> Question:
    max_attempts = 3
    
    for attempt in range(max_attempts):
        prompt = self.interviewer_prompts.generate_question_prompt(context)
        response = await self._call_gemini_pro(prompt)
        question = self._parse_question_response(response)
        
        # Check if this question was already asked
        if not context.session.is_question_asked(question.text):
            return question
        
        logger.warning(f"Duplicate question generated, attempt {attempt + 1}")
    
    # Fallback to pre-defined question pool
    return self._get_fallback_question(context)
```

**Layer 3: Fallback question pool**

When AI fails repeatedly, use a curated pool:

```python
def _get_fallback_question(self, context: InterviewContext) -> Question:
    fallback_pool = [
        ("How would you design a data pipeline that processes 10M events/day?", "data_pipeline_design"),
        ("Explain your approach to handling schema evolution in production.", "schema_evolution"),
        ("What strategies do you use for handling data skew in Spark?", "spark_optimization"),
        # ... 20+ more
    ]
    
    # Filter out already-asked questions
    available = [
        (text, skill) for text, skill in fallback_pool
        if not context.session.is_question_asked(text)
    ]
    
    if not available:
        available = fallback_pool  # Reset if exhausted
    
    text, skill_id = random.choice(available)
    return Question(text=text, skill_id=skill_id, ...)
```

---

## Response Evaluation

### Scoring Rubric

Each response is scored on 5 dimensions (0-10 each):

```python
class ScoreBreakdown(BaseModel):
    technical_correctness: float = Field(ge=0, le=10)
    depth_of_understanding: float = Field(ge=0, le=10)
    practical_experience: float = Field(ge=0, le=10)
    communication_clarity: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=10)
    
    @property
    def overall_score(self) -> float:
        return (
            self.technical_correctness * 0.3 +
            self.depth_of_understanding * 0.25 +
            self.practical_experience * 0.2 +
            self.communication_clarity * 0.15 +
            self.confidence * 0.1
        )
```

**Weights are intentional**:
- Technical correctness matters most (0.3)
- Confidence matters least (0.1) - we don't penalize nervousness

### Evaluation Prompt

```python
def generate_evaluation_prompt(self, context, question_text, transcript) -> str:
    prompt = f"""Evaluate this interview response.

=== QUESTION ===
{question_text}

=== CANDIDATE RESPONSE ===
{transcript}

=== SCORING CRITERIA ===
Rate each dimension 0-10:

1. Technical Correctness (0-10)
   - 0-3: Major factual errors or misconceptions
   - 4-6: Partially correct but missing key concepts
   - 7-10: Accurate and complete

2. Depth of Understanding (0-10)
   - 0-3: Surface-level only
   - 4-6: Reasonable understanding
   - 7-10: Deep knowledge, explains trade-offs

3. Practical Experience (0-10)
   - 0-3: Purely theoretical
   - 4-6: Some experience mentioned
   - 7-10: Clear real-world examples

4. Communication Clarity (0-10)
   - 0-3: Disorganized, hard to follow
   - 4-6: Understandable but could be clearer
   - 7-10: Well-structured, articulate

5. Confidence (0-10)
   - 0-3: Very uncertain, lots of hedging
   - 4-6: Moderate confidence
   - 7-10: Confident without arrogance

=== OUTPUT FORMAT ===
Return JSON:
{{
    "scores": {{
        "technical_correctness": X,
        "depth_of_understanding": X,
        "practical_experience": X,
        "communication_clarity": X,
        "confidence": X
    }},
    "what_went_well": ["point1", "point2"],
    "what_was_missing": ["point1", "point2"],
    "red_flags": [],
    "needs_followup": true/false,
    "followup_reason": "reason if needs_followup is true",
    "difficulty_delta": -1/0/1
}}
"""
    return prompt
```

---

## Follow-up Decision Logic

The evaluation includes a `needs_followup` boolean and `followup_reason`. The decision tree:

```
Response received
       ↓
   Evaluate
       ↓
┌──────┴──────┐
│ Score < 5?  │
└──────┬──────┘
       ↓
   Yes → Follow-up to clarify
       ↓
   No → Score >= 7.5?
            ↓
        Yes → Increase difficulty, next question
            ↓
        No → Stay at current difficulty, next question
```

Follow-up prompt includes conversation context:

```python
def generate_followup_prompt(self, context, evaluation) -> str:
    # Build conversation history
    conversation = []
    for turn in context.session.current_question_context:
        role = turn.get("role", "")
        content = turn.get("content", "")
        conversation.append(f"{role}: {content}")
    
    conversation_text = "\n".join(conversation)
    
    prompt = f"""Based on this conversation, generate a follow-up question.

=== CONVERSATION ===
{conversation_text}

=== EVALUATION ===
The response was weak in: {evaluation.followup_reason}

=== FOLLOW-UP TYPES ===
- "probe": Ask for deeper explanation
- "clarify": Clear up confusion or vagueness
- "example": Request a specific example
- "challenge": Push back to test conviction

Generate a natural follow-up question.

=== OUTPUT ===
{{
    "followup_type": "probe|clarify|example|challenge",
    "followup_question": "Your question here",
    "reason": "Why this follow-up is needed"
}}
"""
    return prompt
```

---

## Handling AI Response Parsing Failures

AI outputs can be malformed. Defensive parsing:

```python
def _parse_question_response(self, response: str) -> Question:
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return Question(
                text=data["question_text"],
                skill_id=data.get("skill_id", "general"),
                # ... other fields
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse AI response: {e}")
    
    # Check if response looks like raw JSON (malformed)
    if response.strip().startswith("{") or response.strip().startswith("["):
        logger.error("AI returned malformed JSON, using fallback")
        return self._get_fallback_question(context)
    
    # Use response as plain text question
    return Question(text=response.strip(), skill_id="general", ...)
```

---

## What's Next

In Part 3, we'll cover:
- WebSocket implementation for real-time communication
- Audio processing with Whisper and Edge-TTS
- Frontend architecture
- Deploying to Databricks Apps

---

# Part 3: Real-Time Audio & Deployment

## WebSocket Architecture

REST APIs are insufficient for interviews:
- We need real-time audio streaming
- State updates must be pushed to the client
- Bidirectional communication for a natural flow

### WebSocket Endpoint

```python
@router.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    orchestrator = get_orchestrator()
    session = orchestrator.get_session(session_id)
    
    if not session:
        await websocket.close(code=4004)
        return
    
    await websocket.accept()
    
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "state": session.state.value,
        })
        
        # Register state change listener
        async def on_state_change(sid, old, new):
            if sid == session_id:
                await websocket.send_json({
                    "type": "state_change",
                    "old_state": old.value,
                    "new_state": new.value,
                })
        
        orchestrator.on_state_change(on_state_change)
        
        # Message loop
        while True:
            message = await websocket.receive_json()
            await handle_message(websocket, orchestrator, session_id, message)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
```

### Message Types

```python
async def handle_message(websocket, orchestrator, session_id, message):
    msg_type = message.get("type")
    
    if msg_type == "start":
        result = await orchestrator.start_interview(session_id)
        await websocket.send_json({"type": "question", **result})
    
    elif msg_type == "response":
        transcript = message.get("transcript")
        result = await orchestrator.submit_response(session_id, transcript=transcript)
        await websocket.send_json({"type": result["action"], **result})
    
    elif msg_type == "skip":
        result = await orchestrator.submit_response(session_id, transcript="[Skipped]")
        await websocket.send_json({"type": result["action"], **result})
    
    elif msg_type == "end":
        result = await orchestrator.end_interview(session_id)
        await websocket.send_json({"type": "ended", **result})
```

---

## Audio Processing

### Speech-to-Text with Whisper

Two modes: local model or API.

```python
class AudioProcessor:
    def __init__(self):
        self.settings = get_settings()
        
        if self.settings.use_local_whisper:
            import whisper
            self.whisper_model = whisper.load_model("large-v3")
        else:
            self.whisper_model = None
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        if self.settings.use_local_whisper:
            return await self._transcribe_local(audio_data)
        else:
            return await self._transcribe_api(audio_data)
    
    async def _transcribe_local(self, audio_data: bytes) -> str:
        # Save to temp file (Whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            result = self.whisper_model.transcribe(
                temp_path,
                language="en",
                task="transcribe",
            )
            return result["text"].strip()
        finally:
            os.unlink(temp_path)
```

### Text-to-Speech with Edge-TTS

Edge-TTS is free, fast, and sounds natural:

```python
async def text_to_speech(self, text: str) -> dict:
    import edge_tts
    
    communicate = edge_tts.Communicate(text, self.settings.tts_voice)
    
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    
    audio_data = b"".join(audio_chunks)
    audio_base64 = base64.b64encode(audio_data).decode()
    
    return {
        "audio_base64": audio_base64,
        "format": "mp3",
        "voice": self.settings.tts_voice,
    }
```

---

## Frontend Architecture

Plain HTML/CSS/JS. No framework needed for this complexity level.

### Interview Page Structure

```html
<div class="interview-container">
    <!-- AI Avatar -->
    <div class="ai-section">
        <div class="avatar" id="ai-avatar">
            <div class="avatar-circle">
                <div class="sound-wave"></div>
            </div>
        </div>
        <audio id="question-audio" hidden></audio>
    </div>
    
    <!-- User Section -->
    <div class="user-section">
        <video id="user-video" autoplay muted></video>
        <div class="transcript" id="live-transcript"></div>
    </div>
    
    <!-- Controls -->
    <div class="controls">
        <button id="skip-btn">Skip Question</button>
        <button id="end-btn">End Interview</button>
    </div>
    
    <!-- Progress -->
    <div class="progress">
        <span id="question-counter">Question 1 of 10</span>
        <div class="progress-bar" id="progress-bar"></div>
    </div>
</div>

<!-- Loading Overlay -->
<div id="loading-overlay" class="hidden">
    <div class="spinner"></div>
    <p id="loading-message">Preparing your interview...</p>
</div>
```

### WebSocket Client

```javascript
class InterviewSession {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.ws = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
    }
    
    connect() {
        this.ws = new WebSocket(`ws://${location.host}/ws/interview/${this.sessionId}`);
        
        this.ws.onopen = () => {
            console.log('Connected');
            this.ws.send(JSON.stringify({ type: 'start' }));
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'question':
                this.displayQuestion(data);
                this.playQuestionAudio(data.audio_data);
                break;
            case 'followup':
                this.displayFollowup(data);
                this.playQuestionAudio(data.audio_data);
                break;
            case 'complete':
                window.location.href = `/report/${this.sessionId}`;
                break;
        }
    }
    
    async startRecording() {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(stream);
        
        this.mediaRecorder.ondataavailable = (e) => {
            this.audioChunks.push(e.data);
        };
        
        this.mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
            const base64 = await this.blobToBase64(audioBlob);
            
            this.ws.send(JSON.stringify({
                type: 'response',
                audio_base64: base64,
            }));
            
            this.audioChunks = [];
        };
        
        this.mediaRecorder.start();
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
    }
}
```

---

## Deploying to Databricks Apps

### Required Files

**app.yaml** - Databricks Apps configuration:

```yaml
command:
  - "/bin/sh"
  - "-c"
  - "uvicorn main:app --host 0.0.0.0 --port $DATABRICKS_APP_PORT"

env:
  - name: DATABRICKS_HOST
    valueFrom: DATABRICKS_HOST
  - name: DATABRICKS_TOKEN
    valueFrom: DATABRICKS_TOKEN
  - name: GEMINI_PRO_ENDPOINT
    valueFrom: GEMINI_PRO_ENDPOINT
  - name: GEMINI_FLASH_ENDPOINT
    valueFrom: GEMINI_FLASH_ENDPOINT
  - name: USE_LOCAL_WHISPER
    value: "false"

resources:
  memory: "4Gi"
  cpu: "2"
```

**Key insight**: Use `/bin/sh -c` to expand environment variables. Direct variable expansion in YAML doesn't work.

**requirements.txt**:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.26.0
openai-whisper>=20231117
edge-tts>=6.1.9
python-dotenv>=1.0.0
```

### Port Handling

Databricks provides the port via `DATABRICKS_APP_PORT`. Handle it in Python:

```python
if __name__ == "__main__":
    import os
    import uvicorn
    
    # Databricks provides port, fallback for local dev
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    
    uvicorn.run("main:app", host="0.0.0.0", port=port)
```

### Deployment Steps

1. Push code to GitHub
2. In Databricks: Compute → Apps → Create App
3. Connect GitHub repository
4. Configure secrets in Databricks UI:
   - `DATABRICKS_HOST`
   - `DATABRICKS_TOKEN`
   - `GEMINI_PRO_ENDPOINT`
   - `GEMINI_FLASH_ENDPOINT`
5. Deploy

---

## Key Lessons Learned

1. **State machines simplify complex flows** - Interview logic became trivial to debug once states were explicit.

2. **AI deduplication needs multiple layers** - Prompts alone aren't enough; add hash checking and fallback pools.

3. **Parse AI responses defensively** - Always handle malformed JSON; never trust the output format.

4. **WebSockets > REST for real-time** - The bidirectional nature matches interview dynamics perfectly.

5. **Edge-TTS is underrated** - Free, fast, and sounds better than many paid APIs.

6. **Local Whisper needs RAM** - `large-v3` needs ~10GB. Use API mode for constrained environments.

---

## Repository

Full source code: [github.com/KaushalVachhani/DataReady.io](https://github.com/KaushalVachhani/DataReady.io)

---

*End of 3-Part Series*

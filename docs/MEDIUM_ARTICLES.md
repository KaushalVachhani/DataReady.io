# Building an AI-Powered Mock Interview Platform: A 3-Part Engineering Guide

---

# Part 1: System Architecture & State Machine Design

## The Problem We're Solving

Here's the thing about preparing for data engineering interviews: reading about Spark optimization is very different from explaining it out loud to someone staring at you, waiting for an answer.

I wanted to build something that simulates that pressure. A platform where you actually *talk* to an AI interviewer, get real-time follow-up questions when your answer is shallow, and walk away with honest feedback about where you stand.

This isn't a chatbot. This isn't a quiz app. This is meant to feel like sitting across from a senior engineer who's deciding whether to hire you.

Let me show you how I built it.

---

## Starting with the Architecture

Before writing any code, I sketched out what needed to happen:

1. User configures their interview (role, experience, skills)
2. AI generates a question and speaks it
3. User responds verbally
4. System transcribes the audio
5. AI evaluates the response
6. Decide: follow-up question, next topic, or end?
7. Repeat until done
8. Generate a detailed report

Looking at this flow, a few things become clear:

- We need **real-time communication** (WebSockets, not REST)
- We need **audio processing** in both directions (speech-to-text, text-to-speech)
- We need **AI integration** for questions, evaluation, and follow-ups
- We need to track **state** carefully (are we listening? evaluating? asking?)

Here's how I structured it:

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

Why this separation? Because I wanted each piece to be replaceable. If tomorrow I want to swap Whisper for a faster transcription API, I shouldn't have to touch the orchestrator. If I want to use Claude instead of Gemini, that's just the AI layer.

This isn't over-engineering. It's insurance against future pain.

---

## The Heart of the System: A State Machine

Okay, here's where it gets interesting.

When I first started, I had a bunch of if-else statements tracking what was happening. "If we're waiting for audio..." "If we just finished evaluating..." It was a mess. Bugs everywhere. Impossible to debug.

Then I realized: an interview is just a series of **states** and **transitions**. The AI is asking, the user is responding, we're processing, we're deciding what's next. These are discrete phases with clear boundaries.

So I built a state machine. And everything got simpler.

### The States

```python
class InterviewState(str, Enum):
    # Before the interview starts
    SETUP = "setup"      # User picking their role, skills
    READY = "ready"      # Configuration done, ready to begin
    
    # The interview itself
    ASKING = "asking"        # AI is speaking the question
    LISTENING = "listening"  # We're recording the user
    PROCESSING = "processing"  # Transcribing their audio
    EVALUATING = "evaluating"  # AI is scoring the response
    DECIDING = "deciding"    # Figuring out what comes next
    
    # After
    COMPLETE = "complete"
    GENERATING_REPORT = "generating_report"
    FINISHED = "finished"
    
    # Things going wrong
    PAUSED = "paused"
    ERROR = "error"
    CANCELLED = "cancelled"
```

Each state has a clear meaning. When something breaks, I can immediately ask: "What state were we in?" That alone tells me where to look.

### What Transitions Are Allowed?

Not every state can lead to every other state. You can't go from `SETUP` directly to `EVALUATING`. That makes no sense. So I defined the valid transitions:

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

See that `DECIDING` state? That's the magic one. After we evaluate a response, we have to decide: do we ask a follow-up? Move to the next topic? Or is this interview done? Those three paths all come from `DECIDING`.

### How Transitions Work

Here's the actual implementation. Nothing fancy, just disciplined:

```python
async def transition_state(
    self,
    session_id: str,
    new_state: InterviewState,
) -> InterviewSession:
    session = self.get_session(session_id)
    old_state = session.state
    
    # Is this transition even allowed?
    valid_next_states = self.VALID_TRANSITIONS.get(old_state, [])
    if new_state not in valid_next_states:
        raise StateTransitionError(
            f"Invalid transition from {old_state} to {new_state}"
        )
    
    # Update the state
    session.state = new_state
    
    # Some transitions have side effects
    if new_state == InterviewState.READY:
        session.started_at = datetime.utcnow()
    elif new_state == InterviewState.COMPLETE:
        session.completed_at = datetime.utcnow()
    
    # Let anyone listening know what happened
    for callback in self._state_change_callbacks:
        await callback(session_id, old_state, new_state)
    
    return session
```

That `StateTransitionError`? It's saved me countless hours. When something tries to make an illegal move, I know immediately. No silent failures.

---

## Tracking Everything: The Session Model

Every interview needs to remember a lot of stuff. What questions have we asked? What did the user say? How are they scoring? What difficulty are we at?

I put all of this in one place:

```python
class InterviewSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    setup: InterviewSetup
    state: InterviewState = InterviewState.SETUP
    
    # Every question and response
    questions: list[QuestionResponse] = []
    
    # Counters (important for knowing "Question 5 of 10")
    total_core_questions_asked: int = 0
    total_followups_asked: int = 0
    
    # For preventing repetitive questions
    asked_question_hashes: set[str] = set()
    
    # Conversation context for follow-ups
    current_question_context: list[dict] = []
    
    # Scoring
    skill_scores: dict[str, list[float]] = {}
    running_score: float = 0.0
    current_difficulty: int = 5
    difficulty_history: list[int] = []
    
    # When things happened
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

Let me explain a couple of these.

**`asked_question_hashes`**: This is how we prevent the AI from asking the same question twice. Every time we ask something, we normalize the text (lowercase, remove punctuation) and hash it. Before asking a new question, we check if that hash already exists. Simple but effective.

```python
def is_question_asked(self, question_text: str) -> bool:
    normalized = self._normalize_question(question_text)
    question_hash = hashlib.md5(normalized.encode()).hexdigest()
    return question_hash in self.asked_question_hashes
```

**`current_question_context`**: This is the conversation history for the current question. If the user asks for clarification, we need to remember what was already said. Otherwise the AI has amnesia and the experience feels broken.

---

## The Flow in Action

Let me walk you through what actually happens:

```
1. User fills out the setup form
   → POST /api/interview/setup
   → We create a session, store it, return the ID
   
2. User clicks "Start Interview"
   → WebSocket connects to /ws/interview/{session_id}
   → We transition to READY, then immediately to ASKING
   → AI generates first question
   → Text-to-speech converts it to audio
   → Audio streams to the browser
   
3. User hears the question and responds
   → Browser records audio
   → Audio chunks sent via WebSocket
   → We transition to LISTENING → PROCESSING
   → Whisper transcribes the audio
   
4. We evaluate the response
   → Transition to EVALUATING
   → AI scores the response on 5 dimensions
   → We store the evaluation (hidden from user for now)
   
5. We decide what's next
   → Transition to DECIDING
   → Was the answer weak? → Follow-up question
   → Was it solid? → Next topic (maybe harder)
   → Done with 10 questions? → COMPLETE
   
6. Repeat until done

7. Generate report
   → Compile all evaluations
   → Calculate overall scores
   → Determine hiring verdict
   → Present to user
```

---

## Where Are Sessions Stored?

For now, in memory:

```python
class InterviewOrchestrator:
    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}
    
    def get_session(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)
```

Is this production-ready? No. If the server restarts, sessions are gone. But for an MVP, it's fine.

When I need to scale, the path is clear: Redis. The `InterviewSession` model is Pydantic, so serialization is trivial:

```python
# Store
await redis.set(f"session:{session_id}", session.model_dump_json())

# Retrieve  
data = await redis.get(f"session:{session_id}")
session = InterviewSession.model_validate_json(data)
```

No code changes to the orchestrator. Just a new storage backend.

---

## What We Covered

In this first part, we established the foundation:

- The overall architecture and why components are separated
- The state machine that keeps the interview flow predictable
- The session model that tracks everything
- How the interview flow actually works

In Part 2, we'll get into the AI. How do we generate good questions? How do we prevent repetition? How do we evaluate responses fairly? That's where things get interesting.

---

# Part 2: AI Integration & Prompt Engineering

## Two Models, Two Jobs

Early on, I realized I needed different AI capabilities for different tasks. Some things need deep reasoning. Other things need to be fast.

Here's how I split it:

| Task | Model | Why |
|------|-------|-----|
| Generate questions | Gemini Pro | Needs to understand role requirements, gauge difficulty, pick relevant topics |
| Evaluate responses | Gemini Pro | Accurate scoring requires nuanced understanding |
| Decide on follow-ups | Gemini Flash | Speed matters here — we don't want awkward pauses |

The implementation is straightforward:

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

Notice the temperature difference. For questions, I want some variety (0.7). For follow-ups, I want it to feel more conversational (0.8). For evaluation, I'd actually want it lower (more deterministic), but that's a tuning exercise.

---

## Generating Good Questions

This is where prompt engineering really matters. A bad prompt gives you generic, repetitive, off-topic questions. A good prompt makes the AI behave like an actual interviewer.

Here's what I include in every question-generation prompt:

### 1. System Context — Who You Are

```python
SYSTEM_CONTEXT = """You are an experienced data engineering interviewer at a top tech company.

Your role:
- Conduct a professional technical interview
- Ask relevant, role-appropriate questions
- Never reveal answers or correct the candidate
- Speak concisely like a real interviewer
- Maintain a neutral, professional tone

You are NOT a chatbot. You are simulating a real interview experience.

Guidelines:
- Ask one question at a time
- Keep questions focused and clear
- Prefer scenario-based questions over definitions
- Use "How would you..." and "Describe a time when..." formats
- Avoid trivia or obscure tool-specific questions
"""
```

That last part is important. I don't want "What's the default block size in HDFS?" I want "How would you design a data pipeline that handles schema changes gracefully?"

### 2. Interview Context — Where We Are

The AI needs to know what's already happened:

```python
=== INTERVIEW CONTEXT ===
Target Role: Senior Data Engineer (5-8 years)
Experience: 6 years
Cloud Platform: AWS
Questions Asked: 4/10
Current Difficulty: 6/10
Performance Trend: improving
```

If the candidate is doing well, we can push harder. If they're struggling, maybe ease off. The AI adjusts based on this context.

### 3. Skills Context — What to Ask About

```python
=== SKILLS CONTEXT ===
Skills Covered: sql_optimization, spark_tuning
Skills Remaining: streaming, data_modeling, orchestration
Priority: Focus on skills NOT YET covered.
```

This prevents the AI from asking 5 Spark questions in a row. Spread the coverage.

### 4. Previously Asked Questions — Don't Repeat Yourself

This is crucial. I pass the full text of every question asked so far:

```python
=== PREVIOUSLY ASKED QUESTIONS ===
1. [Core] How would you optimize a slow-running Spark job?
2. [Follow-up] Can you give a specific example of when you applied that?
3. [Core] Describe your approach to handling schema evolution.
```

And I explicitly tell the AI:

```python
=== RULES ===
1. DO NOT ask any question similar to those listed above
2. Generate a NEW question on a different topic
```

Does it always work? No. Which is why we need more layers of protection.

---

## The Deduplication Problem

Here's something I learned the hard way: prompts alone aren't enough to prevent repetition.

You can tell the AI "don't repeat questions" all you want. Sometimes it still does. Maybe the wording is slightly different, but it's the same question. "How do you optimize Spark?" vs "What's your approach to Spark optimization?" — same thing.

So I built three layers of protection:

### Layer 1: The Prompt

We just covered this. Include all previous questions and tell the AI not to repeat.

### Layer 2: Hash Checking with Retries

After the AI generates a question, we check if we've already asked something similar:

```python
async def generate_question(self, context: InterviewContext) -> Question:
    max_attempts = 3
    
    for attempt in range(max_attempts):
        prompt = self.interviewer_prompts.generate_question_prompt(context)
        response = await self._call_gemini_pro(prompt)
        question = self._parse_question_response(response)
        
        # Have we asked this before?
        if not context.session.is_question_asked(question.text):
            return question
        
        logger.warning(f"Duplicate question generated, attempt {attempt + 1}")
    
    # AI keeps repeating? Use our backup pool
    return self._get_fallback_question(context)
```

The hash check normalizes the text (lowercase, no punctuation) and compares. Not perfect for semantic similarity, but catches most duplicates.

### Layer 3: Fallback Question Pool

When the AI fails three times, we give up on it and use a curated pool:

```python
def _get_fallback_question(self, context: InterviewContext) -> Question:
    fallback_pool = [
        ("How would you design a data pipeline that processes 10M events/day?", "data_pipeline_design"),
        ("Explain your approach to handling schema evolution in production.", "schema_evolution"),
        ("What strategies do you use for handling data skew in Spark?", "spark_optimization"),
        ("How do you ensure data quality in a streaming pipeline?", "data_quality"),
        # ... 20+ more, organized by skill
    ]
    
    # Filter out already-asked questions
    available = [
        (text, skill) for text, skill in fallback_pool
        if not context.session.is_question_asked(text)
    ]
    
    if not available:
        available = fallback_pool  # Everything exhausted, start over
    
    text, skill_id = random.choice(available)
    return Question(text=text, skill_id=skill_id, ...)
```

Is this elegant? Not really. Does it work? Absolutely.

---

## Evaluating Responses

Now the hard part: scoring what the user said.

I don't want a single number. I want to understand *why* the response was good or bad. So I score on five dimensions:

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

Why these weights?

- **Technical correctness (30%)**: The most important. Did they get it right?
- **Depth (25%)**: Did they just scratch the surface or really understand?
- **Practical experience (20%)**: Book knowledge vs. actually doing it
- **Communication (15%)**: Can they explain their thinking clearly?
- **Confidence (10%)**: Lowest weight because I don't want to penalize nervous candidates

### The Evaluation Prompt

I give the AI clear scoring criteria:

```python
=== SCORING CRITERIA ===
Rate each dimension 0-10:

1. Technical Correctness (0-10)
   - 0-3: Major factual errors or misconceptions
   - 4-6: Partially correct but missing key concepts
   - 7-10: Accurate and complete

2. Depth of Understanding (0-10)
   - 0-3: Surface-level only, reciting definitions
   - 4-6: Reasonable understanding, some gaps
   - 7-10: Deep knowledge, explains trade-offs

3. Practical Experience (0-10)
   - 0-3: Purely theoretical, no real examples
   - 4-6: Some experience mentioned
   - 7-10: Clear real-world examples with details

4. Communication Clarity (0-10)
   - 0-3: Disorganized, hard to follow
   - 4-6: Understandable but rambling
   - 7-10: Well-structured, articulate

5. Confidence (0-10)
   - 0-3: Very uncertain, excessive hedging
   - 4-6: Moderate confidence
   - 7-10: Confident without arrogance
```

The rubric makes the AI's scoring more consistent. Without it, you get wildly different scores for similar responses.

---

## When to Ask Follow-ups

Not every weak answer needs a follow-up. But some do.

After evaluating, the AI tells me whether a follow-up is needed and why:

```python
{
    "needs_followup": true,
    "followup_reason": "Response was vague about implementation details",
    "difficulty_delta": 0  // Don't change difficulty yet
}
```

The decision tree looks like this:

```
Response evaluated
       ↓
   Score < 5?
       ↓
   Yes → "Can you elaborate on that?" (follow-up)
       ↓
   No → Score >= 7.5?
            ↓
        Yes → Increase difficulty, next question
            ↓
        No → Same difficulty, next question
```

### Building Follow-up Context

For follow-ups to make sense, the AI needs to remember the conversation:

```python
def generate_followup_prompt(self, context, evaluation) -> str:
    # Build the conversation so far
    conversation = []
    for turn in context.session.current_question_context:
        role = turn.get("role", "")  # "interviewer" or "candidate"
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
"""
    return prompt
```

This way, if the user said "I'd use Spark for that," the follow-up can be "Can you walk me through how you'd actually set that up?" instead of a random new question.

---

## When AI Responses Break

Here's something nobody tells you: AI outputs are unreliable.

You ask for JSON, you might get JSON with markdown code fences. Or a preamble before the JSON. Or malformed JSON. Or something completely unexpected.

You have to be paranoid:

```python
def _parse_question_response(self, response: str) -> Question:
    try:
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return Question(
                text=data["question_text"],
                skill_id=data.get("skill_id", "general"),
                # ...
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse AI response: {e}")
    
    # If the response looks like raw JSON but didn't parse, that's bad
    if response.strip().startswith("{"):
        logger.error("AI returned malformed JSON, using fallback")
        return self._get_fallback_question(context)
    
    # Maybe the AI just gave us the question as plain text
    return Question(text=response.strip(), skill_id="general")
```

Never trust the AI to follow your format instructions perfectly. Always have a fallback path.

---

## What We Covered

In this part, we dove into the AI layer:

- Using different models for different tasks (Pro for thinking, Flash for speed)
- Crafting prompts that make the AI behave like a real interviewer
- Three-layer deduplication (prompt, hash checking, fallback pool)
- Scoring responses on five dimensions with clear rubrics
- Deciding when to ask follow-ups
- Handling malformed AI outputs gracefully

Next up: the real-time stuff. WebSockets, audio processing, and actually deploying this thing.

---

# Part 3: Real-Time Audio & Deployment

## Why WebSockets?

Let me be clear: you cannot build this with REST APIs alone.

Think about what needs to happen:
- Audio streams from the browser to the server (not a single request)
- The server pushes state updates to the browser (not polling)
- Everything feels real-time (not request-response-request-response)

REST is great for CRUD. This isn't CRUD. This is a conversation.

### The WebSocket Endpoint

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
        # Tell the client we're connected
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "state": session.state.value,
        })
        
        # Listen for state changes and push them to the client
        async def on_state_change(sid, old, new):
            if sid == session_id:
                await websocket.send_json({
                    "type": "state_change",
                    "old_state": old.value,
                    "new_state": new.value,
                })
        
        orchestrator.on_state_change(on_state_change)
        
        # Main message loop
        while True:
            message = await websocket.receive_json()
            await handle_message(websocket, orchestrator, session_id, message)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
```

The key insight: we register a callback for state changes. Whenever the orchestrator transitions state, the client knows immediately. No polling.

### Message Types

The client and server speak in JSON messages:

```python
async def handle_message(websocket, orchestrator, session_id, message):
    msg_type = message.get("type")
    
    if msg_type == "start":
        # Begin the interview
        result = await orchestrator.start_interview(session_id)
        await websocket.send_json({"type": "question", **result})
    
    elif msg_type == "response":
        # User finished speaking
        transcript = message.get("transcript")
        result = await orchestrator.submit_response(session_id, transcript=transcript)
        await websocket.send_json({"type": result["action"], **result})
    
    elif msg_type == "skip":
        # User wants to skip this question
        result = await orchestrator.submit_response(session_id, transcript="[Skipped]")
        await websocket.send_json({"type": result["action"], **result})
    
    elif msg_type == "end":
        # User wants to end early
        result = await orchestrator.end_interview(session_id)
        await websocket.send_json({"type": "ended", **result})
```

Clean, predictable, easy to debug.

---

## Audio: The Hard Part

Getting audio right was the most frustrating part of this project. Let me save you some pain.

### Speech-to-Text with Whisper

Whisper is amazing. It handles accents, background noise, technical terms. But there are two ways to use it:

**Local model** — Load it into memory, run inference locally.

Pros: No API costs, works offline, no latency from network calls.
Cons: Needs 10GB+ RAM for the large model, slow on CPU.

**API** — Send audio to a hosted endpoint.

Pros: No RAM requirements, consistent performance.
Cons: Network latency, potential costs, dependency on external service.

I support both:

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
```

For local transcription, Whisper needs a file path (annoying, but that's the API):

```python
async def _transcribe_local(self, audio_data: bytes) -> str:
    # Whisper wants a file, not bytes
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
        os.unlink(temp_path)  # Clean up
```

### Text-to-Speech with Edge-TTS

For the AI's voice, I use Edge-TTS. It's Microsoft's TTS service, but the library wraps it nicely and it's free.

The quality is surprisingly good. Way better than the robotic voices I expected.

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
    }
```

I send the audio as base64 over the WebSocket. The browser decodes it and plays it through an `<audio>` element. Simple.

---

## The Frontend

I deliberately kept this simple: vanilla HTML, CSS, JavaScript. No React. No Vue. No build step.

Why? Because the complexity is in the backend. The frontend just needs to:
1. Show the AI avatar
2. Play audio
3. Record the user
4. Display the transcript
5. Send messages over WebSocket

That's it. A framework would be overkill.

### The Interview Page Structure

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
    
    <!-- User's video preview -->
    <div class="user-section">
        <video id="user-video" autoplay muted></video>
        <div class="transcript" id="live-transcript"></div>
    </div>
    
    <!-- Controls -->
    <div class="controls">
        <button id="skip-btn">Skip Question</button>
        <button id="end-btn">End Interview</button>
    </div>
</div>

<!-- Loading overlay for transitions -->
<div id="loading-overlay" class="hidden">
    <div class="spinner"></div>
    <p id="loading-message">Preparing your interview...</p>
</div>
```

### The WebSocket Client

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
}
```

Nothing complicated. Record audio, convert to base64, send over WebSocket. Let the backend handle the rest.

---

## Deploying to Databricks Apps

Alright, you've built it locally. Now how do you actually run it somewhere?

I chose Databricks Apps because I was already using Databricks for the AI models. Keeps everything in one ecosystem.

### The Configuration

Databricks Apps need an `app.yaml` file:

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

See that `/bin/sh -c` wrapper? That's important. Databricks doesn't expand environment variables in the command array directly. You need a shell to do that.

I learned this the hard way when `$DATABRICKS_APP_PORT` was passed literally as a string and the app crashed.

### Handling the Port

Databricks tells your app which port to use via an environment variable. Handle it in Python:

```python
if __name__ == "__main__":
    import os
    import uvicorn
    
    # Databricks provides the port, default to 8000 for local dev
    port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
    
    uvicorn.run("main:app", host="0.0.0.0", port=port)
```

### Dependencies

Databricks Apps use `requirements.txt`:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
httpx>=0.26.0
edge-tts>=6.1.9
python-dotenv>=1.0.0
```

Notice I left out `openai-whisper`. That thing needs 10GB of RAM. Set `USE_LOCAL_WHISPER=false` and use an API instead.

### The Deployment Steps

1. Push your code to GitHub
2. In Databricks: **Compute → Apps → Create App**
3. Connect your GitHub repo
4. Configure secrets in the Databricks UI:
   - `DATABRICKS_HOST`
   - `DATABRICKS_TOKEN`
   - `GEMINI_PRO_ENDPOINT`
   - `GEMINI_FLASH_ENDPOINT`
5. Deploy

That's it. Databricks handles the container, the networking, the scaling.

---

## Lessons Learned

Let me leave you with some hard-won insights:

**1. State machines make complex flows manageable.**

Before I had explicit states, debugging was a nightmare. After? I could trace exactly what happened and where it went wrong.

**2. AI deduplication needs multiple layers.**

Don't trust the AI to follow instructions. Check programmatically. Have fallbacks.

**3. Always parse AI responses defensively.**

Assume the output format will be wrong sometimes. Handle it gracefully.

**4. WebSockets aren't scary.**

If you need bidirectional real-time communication, just use them. The API is simpler than you think.

**5. Edge-TTS is a hidden gem.**

Free, fast, and sounds natural. Way better than I expected.

**6. Local Whisper is hungry.**

The large model needs serious RAM. For constrained environments, use an API.

**7. Databricks Apps want a shell wrapper.**

Environment variable expansion doesn't happen automatically. Use `/bin/sh -c`.

---

## What's Next?

This is a functional MVP. Here's what I'd add for production:

- **Redis for session storage** — Right now sessions die on restart
- **User authentication** — Track interview history
- **Video recording** — Let users watch themselves back
- **Question bank management** — Admin interface for curating questions
- **Analytics** — Which topics trip people up most?

But that's for another day. The foundation is solid.

---

## Repository

All the code is here: [github.com/KaushalVachhani/DataReady.io](https://github.com/KaushalVachhani/DataReady.io)

Clone it. Run it. Break it. Make it better.

---

*End of 3-Part Series*

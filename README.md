# DataReady.io

**AI-Powered Data Engineering Mock Interview Platform**

A production-ready platform for simulating realistic data engineering interviews with adaptive AI, role-based difficulty, and comprehensive feedback.

![DataReady.io](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 🎯 Features

### Interview Experience
- **Adaptive AI Interviewer** - Adjusts questions based on your performance
- **Role-Based Difficulty** - Junior to Principal-level interviews
- **Live Audio Interaction** - Respond verbally, hear questions spoken
- **Real-Time Transcription** - See your responses as you speak
- **Follow-Up Questions** - Dynamic probing based on answer depth

### Skill Assessment
- **10+ Skill Categories** - SQL, Spark, Streaming, System Design, etc.
- **Cloud-Specific Options** - AWS, GCP, Azure, or cloud-agnostic
- **Performance Tracking** - Difficulty adapts in real-time

### Feedback & Reporting
- **Detailed Score Breakdown** - 5 evaluation dimensions
- **Skill-Wise Analysis** - Radar chart visualization
- **Hiring Verdict** - Strong Hire to Needs Improvement
- **Personalized Study Roadmap** - Week-by-week improvement plan

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (HTML/CSS/JS)                       │
│  Setup Page → Interview Room → Report Dashboard                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │ WebSocket + REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (Python FastAPI)                      │
├─────────────────────────────────────────────────────────────────┤
│  Interview Orchestrator ─┬─ AI Reasoning Layer (Gemini)         │
│                          ├─ Audio Processing (Whisper/TTS)      │
│                          ├─ Evaluation Engine                   │
│                          └─ Report Generator                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Databricks account with Gemini model access
- Microphone and webcam (for interview)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/KaushalVachhani/DataReady.io.git
   cd DataReady.io
   ```

2. **Install uv** (if not already installed)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Databricks credentials
   ```

5. **Run the server**
   ```bash
   uv run python main.py
   ```

6. **Open in browser**
   ```
   http://localhost:8000
   ```

### Docker (Alternative)

```bash
# Build the image
docker build -t dataready .

# Run the container
docker run -p 8000:8000 --env-file .env dataready
```

---

## 📁 Project Structure

```
dataready-io/
├── main.py                 # FastAPI application entry point
├── pyproject.toml          # Project dependencies
├── .env.example            # Environment configuration template
│
├── src/
│   ├── api/                # REST & WebSocket endpoints
│   │   ├── endpoints/      # Route handlers
│   │   ├── router.py       # Main API router
│   │   └── dependencies.py # Dependency injection
│   │
│   ├── core/               # Business logic
│   │   ├── interview_orchestrator.py  # State machine
│   │   ├── ai_reasoning.py            # Gemini integration
│   │   ├── audio_processor.py         # STT/TTS
│   │   ├── evaluation_engine.py       # Scoring
│   │   └── report_generator.py        # Report creation
│   │
│   ├── models/             # Pydantic data models
│   │   ├── interview.py    # Session & state
│   │   ├── question.py     # Questions
│   │   ├── evaluation.py   # Scoring
│   │   ├── report.py       # Report structure
│   │   └── roles.py        # Roles & skills
│   │
│   ├── prompts/            # AI prompt templates
│   │   ├── interviewer.py  # Question generation
│   │   ├── evaluator.py    # Response evaluation
│   │   └── report.py       # Report generation
│   │
│   └── config/             # Configuration
│       └── settings.py     # Environment settings
│
├── static/                 # Frontend assets
│   ├── index.html          # Setup page
│   ├── interview.html      # Interview room
│   ├── report.html         # Report dashboard
│   ├── css/styles.css      # Styles
│   └── js/                 # JavaScript
│       ├── setup.js
│       ├── interview.js
│       └── report.js
│
└── docs/
    └── ARCHITECTURE.md     # System design documentation
```

---

## 🎓 Role Definitions

| Role | Experience | Focus Areas |
|------|------------|-------------|
| **Junior DE** | 0-2 years | SQL, ETL basics, Git, Cloud fundamentals |
| **Mid-Level DE** | 2-5 years | Advanced SQL, Spark, Orchestration, Data quality |
| **Senior DE** | 5-8 years | Platform design, Performance, Streaming |
| **Staff DE** | 8+ years | Architecture, Governance, Multi-cloud |

---

## 📊 Evaluation Rubric

Each response is scored on 5 dimensions (0-10):

1. **Technical Correctness** - Accuracy of technical content
2. **Depth of Understanding** - How deeply concepts are understood
3. **Practical Experience** - Evidence of hands-on work
4. **Communication Clarity** - How clearly ideas are articulated
5. **Confidence** - Appropriate confidence in delivery

---

## 🔧 Configuration

### Databricks Setup

1. Create a Databricks workspace
2. Deploy Gemini 3 Pro and Gemini Flash models
3. Create serving endpoints
4. Generate an access token

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Workspace URL | Required |
| `DATABRICKS_TOKEN` | Access token | Required |
| `WHISPER_MODEL` | STT model size | `large-v3` |
| `TTS_MODEL` | TTS engine | `edge-tts` |
| `MAX_QUESTIONS` | Questions per interview | `10` |

---

## 🚢 Deployment

### Databricks Apps (Recommended)

Deploy directly to your Databricks workspace:

1. **Navigate to Apps in Databricks**
   - Go to your Databricks workspace
   - Click on **Compute** → **Apps**
   - Click **Create App**

2. **Configure the App**
   - Name: `dataready-io`
   - Source: Connect your GitHub repository or upload files
   - The `app.yaml` configuration will be auto-detected

3. **Set Environment Variables (Secrets)**
   
   In the Databricks Apps UI, configure these secrets:
   
   | Variable | Description |
   |----------|-------------|
   | `DATABRICKS_HOST` | Your Databricks workspace URL |
   | `DATABRICKS_TOKEN` | Personal Access Token |
   | `GEMINI_PRO_ENDPOINT` | Gemini Pro model endpoint |
   | `GEMINI_FLASH_ENDPOINT` | Gemini Flash model endpoint |

4. **Deploy**
   - Click **Deploy** and wait for the app to start
   - Access via the provided Databricks App URL

### Railway

1. Connect your GitHub repository to Railway
2. Add environment variables in Railway dashboard:
   - `DATABRICKS_HOST`
   - `DATABRICKS_TOKEN`
   - `GEMINI_PRO_ENDPOINT`
   - `GEMINI_FLASH_ENDPOINT`
3. Deploy! Railway will auto-detect the Dockerfile

### Manual Docker Deployment

```bash
# Build
docker build -t dataready .

# Run with environment variables
docker run -d -p 8000:8000 \
  -e DATABRICKS_HOST="your-host" \
  -e DATABRICKS_TOKEN="your-token" \
  -e GEMINI_PRO_ENDPOINT="your-endpoint" \
  -e GEMINI_FLASH_ENDPOINT="your-endpoint" \
  dataready
```

---

## 🛣️ Roadmap

### Phase 1 (Current)
- [x] Core interview flow
- [x] AI question generation
- [x] Audio processing
- [x] Report generation

### Phase 2
- [ ] User authentication
- [ ] Interview history
- [ ] Question bank management
- [ ] Admin dashboard

### Phase 3
- [ ] Coding challenges
- [ ] Resume-based personalization
- [ ] Video recording playback
- [ ] Team/organization features

### Phase 4
- [ ] Mobile app
- [ ] API for integrations
- [ ] White-label options

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Gemini models via Databricks
- OpenAI Whisper for transcription
- Edge-TTS for voice synthesis

---

<p align="center">
  <strong>Practice makes perfect. 🚀</strong>
</p>

"""
AI Interviewer Prompt Templates

Contains structured prompts for:
- Question generation
- Follow-up decision making
- Conversational responses

Designed to make the AI behave like a real human interviewer,
not a chatbot.
"""

from src.models.interview import InterviewContext
from src.models.evaluation import ResponseEvaluation
from src.models.roles import get_role_focus_areas, Role


class InterviewerPrompts:
    """
    Prompt templates for the AI interviewer.
    
    Key principles:
    - Professional but personable tone
    - Concise and clear questions
    - Never reveals answers
    - Adapts to candidate level
    """
    
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

    def generate_question_prompt(self, context: InterviewContext) -> str:
        """Generate prompt for creating the next interview question."""
        
        role = context.session.setup.target_role
        focus_areas = get_role_focus_areas(role)
        
        # Build skills context
        covered = ", ".join(context.skills_covered[:5]) if context.skills_covered else "None yet"
        remaining = ", ".join(context.skills_remaining[:5]) if context.skills_remaining else "All covered"
        
        # Recent performance context
        recent_perf = ""
        if context.recent_responses:
            scores = []
            for resp in context.recent_responses[-3:]:
                if resp.evaluation:
                    eval_scores = resp.evaluation.get("scores", {})
                    avg = sum(eval_scores.values()) / len(eval_scores) if eval_scores else 5.0
                    scores.append(avg)
            if scores:
                avg_recent = sum(scores) / len(scores)
                if avg_recent >= 7.5:
                    recent_perf = "Candidate is performing well - consider increasing difficulty."
                elif avg_recent <= 4.5:
                    recent_perf = "Candidate is struggling - consider adjusting difficulty down."
                else:
                    recent_perf = "Candidate is performing adequately."
        
        # Get ALL previously asked questions to avoid repetition
        previous_questions = []
        for i, q in enumerate(context.session.questions):
            prefix = "[Core]" if not q.is_followup else "[Follow-up]"
            # Include full question text for better deduplication
            previous_questions.append(f"{i+1}. {prefix} {q.question_text}")
        previous_questions_text = "\n".join(previous_questions) if previous_questions else "None yet"
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== INTERVIEW CONTEXT ===
Target Role: {role.display_name} ({role.experience_range})
Experience: {context.session.setup.years_of_experience} years
Cloud Platform: {context.session.setup.cloud_preference.value}
Questions Asked: {context.session.total_core_questions_asked}/{context.session.setup.max_questions}
Current Difficulty: {context.session.current_difficulty}/10
Performance Trend: {context.performance_trend}
{recent_perf}

=== CLOUD PLATFORM EMPHASIS ===
The candidate has selected "{context.session.setup.cloud_preference.value}" as their preferred cloud platform.
IMPORTANT: At least 30-40% of your questions should be specific to {context.session.setup.cloud_preference.value} services and tools.
- For AWS: Reference S3, Redshift, Glue, EMR, Athena, Lambda, Kinesis, Step Functions, IAM, etc.
- For Azure: Reference ADLS, Synapse, Data Factory, Databricks, Event Hubs, Functions, etc.
- For GCP: Reference BigQuery, Cloud Storage, Dataflow, Dataproc, Pub/Sub, Cloud Functions, etc.
When asking about ETL, data pipelines, storage, or processing - USE THE SPECIFIC CLOUD SERVICES.

=== ROLE FOCUS AREAS ===
{', '.join(focus_areas)}

=== SKILLS COVERED ===
{covered}

=== SKILLS REMAINING TO COVER ===
{remaining}

=== QUESTIONS ALREADY ASKED (DO NOT REPEAT OR REPHRASE ANY OF THESE) ===
{previous_questions_text}

=== YOUR TASK ===
Generate the next interview question.

CRITICAL: You MUST generate a COMPLETELY DIFFERENT question from the ones listed above.
- Do NOT ask about the same topic/concept if already covered
- Do NOT rephrase a previous question  
- Do NOT ask variations of previous questions
- If a skill was already tested, pick a DIFFERENT skill

Requirements:
1. Target an uncovered skill from the remaining skills list
2. Match difficulty level {context.session.current_difficulty}/10
3. Make it role-appropriate for {role.display_name}
4. Prefer scenario-based or design questions
5. Be specific and clear
6. Keep it to 1-3 sentences
7. MUST be on a completely NEW topic not covered in any previous question
8. When possible, frame questions using {context.session.setup.cloud_preference.value} services

Output JSON format:
{{
    "question": "Your question text here",
    "category": "sql|python|etl|spark|streaming|cloud|orchestration|data_modeling|system_design|distributed|performance|governance|observability",
    "skill_id": "skill identifier from the skills list",
    "type": "conceptual|scenario|design|troubleshooting|behavioral|tradeoff",
    "difficulty": "easy|medium|hard|expert",
    "difficulty_score": {context.session.current_difficulty},
    "expected_points": ["point 1", "point 2", "point 3"],
    "red_flags": ["concerning answer pattern 1"]
}}

Generate the question now:"""

        return prompt
    
    def generate_followup_prompt(
        self,
        context: InterviewContext,
        evaluation: ResponseEvaluation
    ) -> str:
        """Generate prompt for deciding on follow-up questions."""
        
        score = evaluation.scores.overall_score
        transcript = evaluation.transcript[:500]  # Truncate for prompt
        
        # Get full conversation context for this question thread
        conversation_context = context.session.get_conversation_context_str()
        
        # Check if this looks like a clarification request from the candidate
        is_clarification_request = any(phrase in transcript.lower() for phrase in [
            "could you clarify",
            "can you explain",
            "what do you mean",
            "i don't understand",
            "could you repeat",
            "can you rephrase",
            "not sure what you",
            "please clarify",
            "what exactly",
        ])
        
        # Determine follow-up type guidance
        if is_clarification_request:
            guidance = "The candidate is asking for clarification. Rephrase or clarify the question without giving away the answer."
        elif score < 4:
            guidance = "The response was weak. Ask a clarifying question to understand their baseline knowledge."
        elif score < 6:
            guidance = "The response was shallow. Probe for more depth or ask for a specific example."
        elif score < 8:
            guidance = "The response was good. Consider challenging them with a harder scenario or edge case."
        else:
            guidance = "The response was excellent. Move on unless you want to explore an advanced topic."
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== FULL CONVERSATION CONTEXT (for this question thread) ===
{conversation_context if conversation_context else "No previous exchanges on this question."}

=== LATEST RESPONSE ===
Candidate's Response:
"{transcript}..."

=== EVALUATION ===
Overall Score: {score:.1f}/10
Technical Correctness: {evaluation.scores.technical_correctness:.1f}/10
Depth: {evaluation.scores.depth_of_understanding:.1f}/10
Practical Experience: {evaluation.scores.practical_experience:.1f}/10

What was missing: {', '.join(evaluation.feedback.what_was_missing[:3]) if evaluation.feedback.what_was_missing else 'None noted'}

=== GUIDANCE ===
{guidance}

=== YOUR TASK ===
Decide whether to ask a follow-up question.

IMPORTANT:
- If the candidate asked for clarification, you MUST provide it (rephrase the question or give more context)
- Never give away the answer when clarifying
- Maintain context from the conversation above

Follow-up types:
- probe: Dig deeper into the answer
- clarify: Respond to candidate's request for clarification (rephrase/explain the question)
- challenge: Push back or ask about edge cases
- example: Ask for a concrete example

Output JSON format:
{{
    "should_followup": true/false,
    "reason": "Why you are or aren't asking a follow-up",
    "type": "probe|clarify|challenge|example",
    "question": "Your follow-up question or clarification (if should_followup is true)",
    "difficulty_adjustment": -1/0/1
}}

Decide now:"""

        return prompt
    
    def generate_transition_prompt(
        self,
        context: InterviewContext,
        next_topic: str
    ) -> str:
        """Generate a natural transition to the next topic."""
        
        prompt = f"""You are conducting a technical interview.

The candidate just finished answering a question about one topic.
Now you need to transition to a new topic: {next_topic}

Generate a brief, natural transition phrase that an interviewer would use.
Keep it to 1 sentence. Examples:
- "Let's move on to discuss your experience with..."
- "Now I'd like to ask about..."
- "Shifting gears a bit, tell me about..."

Generate the transition:"""

        return prompt
    
    def generate_closing_prompt(self, context: InterviewContext) -> str:
        """Generate closing remarks for the interview."""
        
        prompt = f"""You are concluding a technical interview.

Interview Summary:
- Role: {context.session.setup.target_role.display_name}
- Questions Asked: {context.session.total_core_questions_asked}
- Duration: {context.session.get_duration_seconds() / 60:.1f} minutes

Generate brief closing remarks that:
1. Thank the candidate for their time
2. Explain that they will receive detailed feedback
3. Wish them well
4. Are warm but professional

Keep it to 2-3 sentences.

Generate the closing:"""

        return prompt


# === QUESTION TEMPLATES BY ROLE ===

JUNIOR_QUESTION_TEMPLATES = [
    {
        "template": "Can you explain the difference between {concept_a} and {concept_b} in SQL?",
        "skill": "sql_basics",
        "type": "conceptual",
        "examples": [("INNER JOIN", "LEFT JOIN"), ("WHERE", "HAVING"), ("UNION", "UNION ALL")],
    },
    {
        "template": "Walk me through how you would design a simple ETL pipeline to load data from {source} to {destination}.",
        "skill": "etl_concepts",
        "type": "design",
        "examples": [("a CSV file", "a database"), ("an API", "a data warehouse")],
    },
    {
        "template": "What is {concept} and why is it important in data engineering?",
        "skill": "general",
        "type": "conceptual",
        "examples": [("data normalization",), ("indexing",), ("version control",)],
    },
]

MID_QUESTION_TEMPLATES = [
    {
        "template": "How would you design a data pipeline that processes {volume} of data daily with requirements for {requirement}?",
        "skill": "etl_pipeline_design",
        "type": "design",
        "examples": [("10GB", "near real-time updates"), ("100GB", "exactly-once processing")],
    },
    {
        "template": "Describe how you would optimize a Spark job that is {problem}.",
        "skill": "spark_tuning",
        "type": "troubleshooting",
        "examples": [("running slowly due to data skew",), ("running out of memory",)],
    },
    {
        "template": "Explain {concept} and how you've used it in a production environment.",
        "skill": "general",
        "type": "behavioral",
        "examples": [("window functions",), ("Airflow DAGs",), ("data quality testing",)],
    },
]

SENIOR_QUESTION_TEMPLATES = [
    {
        "template": "How would you architect a data platform that needs to handle {challenge}?",
        "skill": "data_platform_design",
        "type": "design",
        "examples": [
            ("both batch and streaming workloads",),
            ("multi-region data processing with low latency requirements",),
        ],
    },
    {
        "template": "Describe your approach to implementing {system} at scale.",
        "skill": "distributed_systems",
        "type": "scenario",
        "examples": [("data observability",), ("data governance",), ("cost optimization",)],
    },
    {
        "template": "What trade-offs would you consider when choosing between {option_a} and {option_b}?",
        "skill": "system_design",
        "type": "tradeoff",
        "examples": [
            ("a data lake and a data warehouse",),
            ("batch and streaming processing",),
            ("strong and eventual consistency",),
        ],
    },
]

STAFF_QUESTION_TEMPLATES = [
    {
        "template": "How would you approach designing a data strategy for {scenario}?",
        "skill": "enterprise_data_architecture",
        "type": "design",
        "examples": [
            ("an organization transitioning to multi-cloud",),
            ("a company going through a major acquisition",),
        ],
    },
    {
        "template": "Describe how you would lead the technical decision-making for {initiative}.",
        "skill": "technical_leadership",
        "type": "behavioral",
        "examples": [
            ("adopting a new data processing framework",),
            ("implementing data governance at scale",),
        ],
    },
    {
        "template": "How do you balance {tension_a} with {tension_b} in platform decisions?",
        "skill": "platform_strategy",
        "type": "tradeoff",
        "examples": [
            ("innovation", "stability"),
            ("cost efficiency", "performance"),
            ("team autonomy", "standardization"),
        ],
    },
]

"""
AI Evaluator Prompt Templates

Contains structured prompts for evaluating candidate responses
according to the scoring rubric.

Evaluation dimensions:
- Technical Correctness
- Depth of Understanding
- Practical Experience
- Communication Clarity
- Confidence
"""

from src.models.interview import InterviewContext
from src.models.question import Question


class EvaluatorPrompts:
    """
    Prompt templates for AI evaluation of responses.
    
    Key principles:
    - Objective, rubric-based scoring
    - Identify both strengths and gaps
    - Provide actionable feedback
    - Detect seniority signals
    """
    
    SYSTEM_CONTEXT = """You are an expert technical interviewer evaluating a data engineering candidate's response.

Your role:
- Score the response objectively against the rubric
- Identify what the candidate did well
- Note what was missing or incorrect
- Look for red flags (misconceptions, overconfidence, etc.)
- Identify signals of seniority level
- Suggest if a follow-up question would help

Be fair but thorough. Look for both explicit and implicit understanding.
"""

    SCORING_RUBRIC = """
=== SCORING RUBRIC (0-10 scale) ===

TECHNICAL CORRECTNESS:
- 9-10: Completely accurate, no errors, includes edge cases
- 7-8: Mostly accurate, minor omissions, fundamentally sound
- 5-6: Partially correct, some errors but shows basic understanding
- 3-4: Significant errors, fundamental misunderstandings
- 1-2: Mostly or completely incorrect

DEPTH OF UNDERSTANDING:
- 9-10: Expert-level insight, explains "why" not just "what"
- 7-8: Strong understanding, can discuss trade-offs
- 5-6: Surface-level understanding, limited depth
- 3-4: Superficial, memorized without understanding
- 1-2: No real understanding demonstrated

PRACTICAL EXPERIENCE:
- 9-10: Clear evidence of hands-on production experience
- 7-8: Good practical examples, understands real-world challenges
- 5-6: Some practical exposure, limited real examples
- 3-4: Mostly theoretical, few practical examples
- 1-2: No evidence of practical experience

COMMUNICATION CLARITY:
- 9-10: Exceptionally clear, well-structured, easy to follow
- 7-8: Clear and organized, minor improvements possible
- 5-6: Understandable but could be clearer
- 3-4: Disorganized, hard to follow
- 1-2: Very unclear, rambling, incoherent

CONFIDENCE:
- 9-10: Appropriately confident, admits uncertainty when warranted
- 7-8: Good confidence, comfortable with the material
- 5-6: Some hesitation, but reasonable
- 3-4: Very hesitant or overconfident without substance
- 1-2: Extremely uncertain or inappropriately overconfident
"""

    def generate_evaluation_prompt(
        self,
        question: Question,
        transcript: str,
        context: InterviewContext
    ) -> str:
        """Generate prompt for evaluating a response."""
        
        role = context.session.setup.target_role
        
        # Format expected points
        expected = "\n".join(f"- {point}" for point in question.expected_points) if question.expected_points else "No specific points defined"
        
        # Format red flags
        red_flags = "\n".join(f"- {flag}" for flag in question.red_flags) if question.red_flags else "None specified"
        
        prompt = f"""{self.SYSTEM_CONTEXT}

{self.SCORING_RUBRIC}

=== CONTEXT ===
Role Being Interviewed For: {role.display_name} ({role.experience_range})
Candidate's Experience: {context.session.setup.years_of_experience} years
Question Difficulty: {question.difficulty_score}/10
Question Category: {question.category.value}

=== QUESTION ASKED ===
{question.text}

=== EXPECTED POINTS IN A GOOD ANSWER ===
{expected}

=== RED FLAGS TO WATCH FOR ===
{red_flags}

=== CANDIDATE'S RESPONSE ===
"{transcript}"

=== YOUR TASK ===
Evaluate the response according to the rubric.

IMPORTANT: Output ONLY valid JSON, no preamble text. Start directly with {{

{{
    "scores": {{
        "technical_correctness": <0-10>,
        "depth_of_understanding": <0-10>,
        "practical_experience": <0-10>,
        "communication_clarity": <0-10>,
        "confidence": <0-10>
    }},
    "feedback": {{
        "what_went_well": ["specific point 1", "specific point 2"],
        "what_was_missing": ["missing concept 1", "missing concept 2"],
        "red_flags": ["if any concerns"],
        "seniority_signals": ["signals indicating their experience level"],
        "improvement_suggestions": ["specific actionable improvement 1", "improvement 2"]
    }},
    "needs_followup": true/false,
    "followup_reason": "why a follow-up would or wouldn't help",
    "followup_type": "probe|clarify|challenge|example",
    "difficulty_delta": <-2 to +2>,
    "notes": "Any additional observations"
}}"""

        return prompt
    
    def generate_seniority_assessment_prompt(
        self,
        context: InterviewContext
    ) -> str:
        """Generate prompt for assessing demonstrated seniority level."""
        
        # Collect all responses
        responses_summary = []
        for q in context.session.questions[:5]:
            if q.response_transcript:
                responses_summary.append({
                    "question": q.question_text[:100],
                    "response": q.response_transcript[:200],
                })
        
        responses_text = "\n\n".join([
            f"Q: {r['question']}...\nA: {r['response']}..."
            for r in responses_summary
        ])
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== INTERVIEW CONTEXT ===
Target Role: {context.session.setup.target_role.display_name}
Claimed Experience: {context.session.setup.years_of_experience} years

=== SAMPLE Q&A ===
{responses_text}

=== YOUR TASK ===
Based on the responses, assess what seniority level the candidate actually demonstrates.

Seniority Levels:
- Junior (0-2 years): Knows fundamentals, learning best practices
- Mid (2-5 years): Solid skills, can work independently
- Senior (5-8 years): Deep expertise, can lead technical decisions
- Staff (8+ years): Strategic thinking, organizational impact

Output JSON:
{{
    "demonstrated_level": "junior|mid|senior|staff",
    "alignment_with_target": "above|at|below",
    "evidence": ["signal 1", "signal 2", "signal 3"],
    "gaps_for_target_level": ["gap 1", "gap 2"]
}}

Assess now:"""

        return prompt


# === EVALUATION CRITERIA BY ROLE ===

JUNIOR_EVALUATION_CRITERIA = {
    "must_know": [
        "Basic SQL (SELECT, JOIN, WHERE, GROUP BY)",
        "ETL concept understanding",
        "Relational database basics",
        "Git fundamentals",
    ],
    "good_to_know": [
        "Window functions",
        "Python for data processing",
        "Cloud storage concepts",
        "Command line basics",
    ],
    "seniority_signals": {
        "positive": [
            "Shows curiosity and willingness to learn",
            "Acknowledges knowledge gaps honestly",
            "Can explain basic concepts clearly",
        ],
        "concerning": [
            "Overclaims expertise",
            "Struggles with fundamentals",
            "Cannot explain basic concepts",
        ],
    },
}

MID_EVALUATION_CRITERIA = {
    "must_know": [
        "Advanced SQL (CTEs, window functions)",
        "ETL pipeline design",
        "Spark fundamentals",
        "Orchestration tools (Airflow, etc.)",
        "Data quality concepts",
    ],
    "good_to_know": [
        "Performance optimization",
        "Cloud-native data services",
        "Testing strategies",
        "Monitoring basics",
    ],
    "seniority_signals": {
        "positive": [
            "Has production experience stories",
            "Understands trade-offs",
            "Can debug and troubleshoot",
        ],
        "concerning": [
            "Only theoretical knowledge",
            "Cannot discuss real scenarios",
            "Unaware of common pitfalls",
        ],
    },
}

SENIOR_EVALUATION_CRITERIA = {
    "must_know": [
        "Data platform architecture",
        "Distributed systems concepts",
        "Performance tuning",
        "Streaming fundamentals",
        "Cloud optimization",
    ],
    "good_to_know": [
        "Multi-cloud strategies",
        "Data governance",
        "Team leadership",
        "Cost optimization",
    ],
    "seniority_signals": {
        "positive": [
            "Discusses architectural decisions",
            "Considers long-term maintainability",
            "Thinks about team and org impact",
        ],
        "concerning": [
            "Focuses only on implementation",
            "Cannot discuss trade-offs at scale",
            "No leadership experience",
        ],
    },
}

STAFF_EVALUATION_CRITERIA = {
    "must_know": [
        "Enterprise architecture",
        "Cross-team collaboration",
        "Technology evaluation",
        "Strategic planning",
        "Stakeholder management",
    ],
    "good_to_know": [
        "Industry trends",
        "Vendor evaluation",
        "Org-wide initiatives",
        "Mentorship",
    ],
    "seniority_signals": {
        "positive": [
            "Thinks at organization level",
            "Discusses impact on multiple teams",
            "Can articulate technology vision",
        ],
        "concerning": [
            "Limited to single-team perspective",
            "Cannot discuss strategic decisions",
            "No evidence of influence beyond immediate team",
        ],
    },
}

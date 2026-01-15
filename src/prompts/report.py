"""
AI Report Generation Prompts

Contains prompts for generating insightful report content
that goes beyond simple aggregation.
"""

from src.models.interview import InterviewSession
from src.models.evaluation import InterviewEvaluation


class ReportPrompts:
    """
    Prompt templates for generating report insights.
    
    Used to enhance the report with AI-generated:
    - Personalized recommendations
    - Study roadmaps
    - Interviewer notes
    """
    
    SYSTEM_CONTEXT = """You are an expert career coach and technical interviewer providing feedback on a data engineering interview.

Your role:
- Provide constructive, actionable feedback
- Be encouraging but honest
- Focus on growth and improvement
- Give specific, practical suggestions
"""

    def generate_summary_prompt(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> str:
        """Generate prompt for overall interview summary."""
        
        # Build Q&A summary
        qa_summary = []
        for i, q in enumerate(session.questions[:5], 1):
            if q.evaluation:
                scores = q.evaluation.get("scores", {})
                avg = sum(scores.values()) / len(scores) if scores else 5.0
                qa_summary.append(f"Q{i}: {avg:.1f}/10 - {q.question_text[:50]}...")
        
        qa_text = "\n".join(qa_summary)
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== INTERVIEW SUMMARY ===
Role: {session.setup.target_role.display_name}
Experience: {session.setup.years_of_experience} years
Duration: {session.get_duration_seconds() / 60:.1f} minutes
Questions: {len(session.questions)}

=== PERFORMANCE OVERVIEW ===
Overall Score: {evaluation.overall_score:.1f}/100
Technical: {evaluation.avg_technical_correctness:.1f}/10
Depth: {evaluation.avg_depth_of_understanding:.1f}/10
Practical: {evaluation.avg_practical_experience:.1f}/10
Communication: {evaluation.avg_communication_clarity:.1f}/10
Confidence: {evaluation.avg_confidence:.1f}/10

=== QUESTION PERFORMANCE ===
{qa_text}

=== YOUR TASK ===
Write a 2-3 paragraph executive summary of this interview performance.

Include:
1. Overall assessment
2. Key strengths demonstrated
3. Main areas for improvement
4. Readiness for the target role

Be professional, constructive, and specific.

Write the summary:"""

        return prompt
    
    def generate_roadmap_prompt(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation,
        weak_areas: list[str]
    ) -> str:
        """Generate prompt for personalized study roadmap."""
        
        weak_list = "\n".join(f"- {area}" for area in weak_areas[:5])
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== CANDIDATE PROFILE ===
Target Role: {session.setup.target_role.display_name}
Experience: {session.setup.years_of_experience} years
Cloud Preference: {session.setup.cloud_preference.value}

=== AREAS NEEDING IMPROVEMENT ===
{weak_list}

=== OVERALL SCORE ===
{evaluation.overall_score:.1f}/100

=== YOUR TASK ===
Create a personalized 4-week study roadmap to address the weak areas.

For each week, specify:
1. Focus area
2. Specific topics to study
3. Hands-on exercises to complete
4. Resources (books, courses, tutorials)

Output JSON:
{{
    "overview": "Brief roadmap description",
    "weeks": [
        {{
            "week": 1,
            "focus": "Area of focus",
            "topics": ["topic 1", "topic 2"],
            "exercises": ["exercise 1", "exercise 2"],
            "resources": ["resource 1", "resource 2"],
            "goals": ["measurable goal 1", "measurable goal 2"]
        }}
    ],
    "success_metrics": ["How to know when ready"],
    "estimated_hours_per_week": 10
}}

Create the roadmap:"""

        return prompt
    
    def generate_strengths_narrative_prompt(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> str:
        """Generate narrative description of candidate's strengths."""
        
        # Find best-scoring skills
        best_skills = sorted(
            evaluation.skill_evaluations,
            key=lambda x: x.average_score,
            reverse=True
        )[:3]
        
        skills_text = "\n".join([
            f"- {s.skill_name}: {s.average_score:.1f}/10"
            for s in best_skills
        ])
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== TOP PERFORMING AREAS ===
{skills_text}

=== DIMENSION SCORES ===
Technical Accuracy: {evaluation.avg_technical_correctness:.1f}/10
Understanding Depth: {evaluation.avg_depth_of_understanding:.1f}/10
Practical Experience: {evaluation.avg_practical_experience:.1f}/10
Communication: {evaluation.avg_communication_clarity:.1f}/10

=== YOUR TASK ===
Write 2-3 sentences highlighting this candidate's key strengths.
Be specific about what they demonstrated well.
Keep it encouraging and professional.

Write the strengths narrative:"""

        return prompt
    
    def generate_improvement_narrative_prompt(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> str:
        """Generate narrative description of areas for improvement."""
        
        # Find lowest-scoring skills
        weak_skills = sorted(
            evaluation.skill_evaluations,
            key=lambda x: x.average_score
        )[:3]
        
        skills_text = "\n".join([
            f"- {s.skill_name}: {s.average_score:.1f}/10"
            for s in weak_skills
        ])
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== AREAS NEEDING IMPROVEMENT ===
{skills_text}

=== DIMENSION SCORES ===
Technical Accuracy: {evaluation.avg_technical_correctness:.1f}/10
Understanding Depth: {evaluation.avg_depth_of_understanding:.1f}/10
Practical Experience: {evaluation.avg_practical_experience:.1f}/10
Communication: {evaluation.avg_communication_clarity:.1f}/10

=== YOUR TASK ===
Write 2-3 sentences about areas where this candidate could improve.
Be constructive and specific.
Focus on actionable growth areas.

Write the improvement narrative:"""

        return prompt
    
    def generate_hiring_recommendation_prompt(
        self,
        session: InterviewSession,
        evaluation: InterviewEvaluation
    ) -> str:
        """Generate detailed hiring recommendation."""
        
        prompt = f"""{self.SYSTEM_CONTEXT}

=== INTERVIEW RESULTS ===
Role: {session.setup.target_role.display_name}
Experience: {session.setup.years_of_experience} years
Overall Score: {evaluation.overall_score:.1f}/100

Technical: {evaluation.avg_technical_correctness:.1f}/10
Depth: {evaluation.avg_depth_of_understanding:.1f}/10
Practical: {evaluation.avg_practical_experience:.1f}/10
Communication: {evaluation.avg_communication_clarity:.1f}/10
Confidence: {evaluation.avg_confidence:.1f}/10

Questions Asked: {evaluation.total_questions}
Follow-ups: {evaluation.total_followups}
Duration: {evaluation.interview_duration_seconds / 60:.1f} minutes

=== YOUR TASK ===
Provide a hiring recommendation as if you were the interviewer submitting feedback.

Output JSON:
{{
    "recommendation": "strong_hire|hire|borderline|no_hire",
    "confidence": "high|medium|low",
    "summary": "2-3 sentence summary",
    "strengths": ["key strength 1", "key strength 2"],
    "concerns": ["concern 1", "concern 2"],
    "leveling_assessment": "Assessment of appropriate level",
    "suggested_next_steps": ["next step 1", "next step 2"]
}}

Make the recommendation:"""

        return prompt

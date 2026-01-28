"""
AI Reasoning Layer for DataReady.io

Handles all AI-powered operations:
- Question generation
- Follow-up decision making
- Response evaluation
- Difficulty adaptation

Uses Gemini 3 Pro for deep reasoning and Gemini Flash for fast responses.
Integrated with Langfuse for observability and tracing.
"""

import json
import logging
import httpx
from typing import Any
from uuid import uuid4
from contextlib import contextmanager

from src.config.settings import get_settings
from src.models.interview import InterviewContext
from src.models.question import (
    Question,
    QuestionCategory,
    QuestionDifficulty,
    QuestionType,
    FollowUpDecision,
    GeneratedQuestion,
)
from src.models.evaluation import (
    ResponseEvaluation,
    ScoreBreakdown,
    EvaluationFeedback,
)
from src.models.roles import Role, get_role_focus_areas, SKILL_CATALOG
from src.prompts.interviewer import InterviewerPrompts
from src.prompts.evaluator import EvaluatorPrompts

logger = logging.getLogger(__name__)

# Langfuse imports
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    logger.warning("Langfuse not installed. Tracing disabled.")


class AIReasoningLayer:
    """
    Central AI reasoning component using Gemini models via Databricks.
    
    Model Selection:
    - Gemini 3 Pro: Question generation, evaluation (deep reasoning)
    - Gemini Flash: Follow-up decisions, conversational (low latency)
    
    Observability:
    - Langfuse integration for tracing all LLM calls
    """
    
    def __init__(self):
        """Initialize AI reasoning layer with Databricks configuration."""
        self.settings = get_settings()
        self.base_url = self.settings.databricks_host.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.settings.databricks_token}",
            "Content-Type": "application/json",
        }
        
        # HTTP client for API calls
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=60.0,
        )
        
        # Prompt templates
        self.interviewer_prompts = InterviewerPrompts()
        self.evaluator_prompts = EvaluatorPrompts()
        
        # Initialize Langfuse for observability
        self.langfuse = None
        if LANGFUSE_AVAILABLE and self.settings.langfuse_enabled:
            if self.settings.langfuse_secret_key and self.settings.langfuse_public_key:
                try:
                    self.langfuse = Langfuse(
                        secret_key=self.settings.langfuse_secret_key,
                        public_key=self.settings.langfuse_public_key,
                        host=self.settings.langfuse_base_url,
                    )
                    logger.info("Langfuse initialized for LLM observability")
                except Exception as e:
                    logger.warning(f"Failed to initialize Langfuse: {e}")
            else:
                logger.info("Langfuse keys not configured, tracing disabled")
    
    async def close(self):
        """Close the HTTP client and flush Langfuse."""
        await self.client.aclose()
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception as e:
                logger.warning(f"Failed to flush Langfuse: {e}")
    
    # =========================================================================
    # CORE AI OPERATIONS
    # =========================================================================
    
    def _extract_content(self, result: dict) -> str:
        """Extract text content from API response, handling list/dict formats."""
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Handle case where content is a list (multi-part response)
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            content = "".join(text_parts)
        
        return content if isinstance(content, str) else str(content)
    
    async def _call_gemini_pro(
        self, 
        prompt: str, 
        max_tokens: int = 2048,
        trace_name: str = "gemini_pro_call",
        trace_metadata: dict | None = None,
        session_id: str | None = None,
    ) -> str:
        """
        Call Gemini 3 Pro for deep reasoning tasks.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            trace_name: Name for Langfuse trace
            trace_metadata: Additional metadata for trace
            session_id: Interview session ID for trace grouping
            
        Returns:
            Model response text
        """
        try:
            payload = {
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            
            response = await self.client.post(
                self.settings.gemini_pro_endpoint,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            return self._extract_content(result)
            
        except httpx.HTTPError as e:
            logger.error(f"Gemini Pro API error: {e}")
            raise
    
    async def _call_gemini_flash(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        trace_name: str = "gemini_flash_call",
        trace_metadata: dict | None = None,
        session_id: str | None = None,
    ) -> str:
        """
        Call Gemini Flash for fast, conversational responses.
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response
            trace_name: Name for Langfuse trace
            trace_metadata: Additional metadata for trace
            session_id: Interview session ID for trace grouping
            
        Returns:
            Model response text
        """
        try:
            payload = {
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.8,
            }
            
            response = await self.client.post(
                self.settings.gemini_flash_endpoint,
                json=payload,
            )
            response.raise_for_status()
            
            result = response.json()
            return self._extract_content(result)
            
        except httpx.HTTPError as e:
            logger.error(f"Gemini Flash API error: {e}")
            raise
    
    # =========================================================================
    # QUESTION GENERATION
    # =========================================================================
    
    async def generate_question(self, context: InterviewContext) -> Question:
        """
        Generate the next interview question based on context.
        
        Uses Gemini Pro for thoughtful question generation that:
        - Matches the target role and difficulty
        - Covers uncovered skills
        - Adapts to performance trend
        - Prefers scenario-based questions
        - Avoids repeating previous questions
        
        Args:
            context: Current interview context
            
        Returns:
            Generated Question object
        """
        max_attempts = 3
        session_id = context.session.session_id
        
        # Create Langfuse span for the entire question generation flow (v3 API)
        span = None
        if self.langfuse:
            try:
                span = self.langfuse.start_span(
                    name="generate_question",
                    metadata={
                        "session_id": session_id,
                        "question_number": context.session.total_core_questions_asked + 1,
                        "difficulty": context.session.current_difficulty,
                        "skills_covered": len(context.skills_covered),
                        "skills_remaining": len(context.skills_remaining),
                        "role": context.session.setup.target_role.value,
                        "cloud_preference": context.session.setup.cloud_preference.value,
                    },
                )
            except Exception as lf_err:
                logger.warning(f"Langfuse span start failed: {lf_err}")
                span = None
        
        # Log context for debugging
        logger.info(
            f"Generating question #{context.session.total_core_questions_asked + 1} | "
            f"Skills covered: {len(context.skills_covered)} | "
            f"Skills remaining: {len(context.skills_remaining)} | "
            f"Questions asked: {context.session.get_asked_question_count()}"
        )
        
        for attempt in range(max_attempts):
            # Build the prompt
            prompt = self.interviewer_prompts.generate_question_prompt(context)
            
            # Log for prompt building
            if span:
                logger.debug(f"Built prompt for attempt {attempt + 1}, length: {len(prompt)}")
            
            try:
                # Call Gemini Pro with trace context
                response = await self._call_gemini_pro(
                    prompt, 
                    max_tokens=1024,
                    trace_name="question_generation_llm",
                    trace_metadata={
                        "attempt": attempt + 1,
                        "question_number": context.session.total_core_questions_asked + 1,
                    },
                    session_id=session_id,
                )
                
                # Parse the response
                question = self._parse_question_response(response, context)
                
                # Check if this question was already asked (text-based)
                if context.session.is_question_asked(question.text):
                    logger.warning(
                        f"Duplicate question detected (attempt {attempt + 1}): "
                        f"'{question.text[:50]}...' - regenerating..."
                    )
                    continue
                
                # Also check if the same skill was recently asked (for core questions)
                if question.skill_id and context.session.is_skill_asked(question.skill_id):
                    logger.info(
                        f"Skill '{question.skill_id}' was already targeted, "
                        f"but question text is different - allowing"
                    )
                
                logger.info(f"Generated new question on skill: {question.skill_id}")
                
                # End span with success
                if span:
                    try:
                        span.end(output={
                            "question_id": question.id,
                            "skill_id": question.skill_id,
                            "difficulty": question.difficulty.value,
                            "attempts": attempt + 1,
                        })
                    except Exception:
                        pass
                
                return question
                
            except Exception as e:
                logger.error(f"Question generation failed (attempt {attempt + 1}): {e}")
                if attempt == max_attempts - 1:
                    break
        
        # Fallback to a default question (with deduplication)
        logger.warning("Using fallback question due to generation failures")
        
        if span:
            try:
                span.end(output={"fallback_used": True, "reason": "generation_failures"})
            except Exception:
                pass
        
        return self._get_fallback_question(context)
    
    def _parse_question_response(
        self,
        response: str,
        context: InterviewContext
    ) -> Question:
        """Parse AI response into a Question object."""
        try:
            # Try to parse as JSON
            # The prompt asks for JSON output
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Map difficulty string to enum
                difficulty_map = {
                    "easy": QuestionDifficulty.EASY,
                    "medium": QuestionDifficulty.MEDIUM,
                    "hard": QuestionDifficulty.HARD,
                    "expert": QuestionDifficulty.EXPERT,
                }
                
                # Map category string to enum
                category_map = {
                    "sql": QuestionCategory.SQL,
                    "python": QuestionCategory.PYTHON,
                    "etl": QuestionCategory.ETL,
                    "spark": QuestionCategory.SPARK,
                    "streaming": QuestionCategory.STREAMING,
                    "cloud": QuestionCategory.CLOUD,
                    "orchestration": QuestionCategory.ORCHESTRATION,
                    "data_modeling": QuestionCategory.DATA_MODELING,
                    "system_design": QuestionCategory.SYSTEM_DESIGN,
                    "distributed": QuestionCategory.DISTRIBUTED,
                    "performance": QuestionCategory.PERFORMANCE,
                    "governance": QuestionCategory.GOVERNANCE,
                    "observability": QuestionCategory.OBSERVABILITY,
                }
                
                # Map question type
                type_map = {
                    "conceptual": QuestionType.CONCEPTUAL,
                    "scenario": QuestionType.SCENARIO,
                    "design": QuestionType.DESIGN,
                    "troubleshooting": QuestionType.TROUBLESHOOTING,
                    "behavioral": QuestionType.BEHAVIORAL,
                    "tradeoff": QuestionType.TRADEOFF,
                }
                
                return Question(
                    id=f"q_{uuid4().hex[:8]}",
                    text=data.get("question", ""),
                    context=data.get("context"),
                    category=category_map.get(
                        data.get("category", "system_design").lower(),
                        QuestionCategory.SYSTEM_DESIGN
                    ),
                    skill_id=data.get("skill_id", "data_platform_design"),
                    question_type=type_map.get(
                        data.get("type", "scenario").lower(),
                        QuestionType.SCENARIO
                    ),
                    difficulty=difficulty_map.get(
                        data.get("difficulty", "medium").lower(),
                        QuestionDifficulty.MEDIUM
                    ),
                    difficulty_score=data.get("difficulty_score", context.session.current_difficulty),
                    target_roles=[context.session.setup.target_role],
                    expected_points=data.get("expected_points", []),
                    red_flags=data.get("red_flags", []),
                    is_generated=True,
                )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse question JSON: {e}")
        
        # If JSON parsing fails, extract question text directly
        return self._get_fallback_question(context, question_text=response.strip())
    
    def _get_fallback_question(
        self,
        context: InterviewContext,
        question_text: str | None = None
    ) -> Question:
        """Get a fallback question when generation fails, with deduplication."""
        import random
        
        role = context.session.setup.target_role
        difficulty = context.session.current_difficulty
        
        # If we have a specific question text, use it
        if question_text and not context.session.is_question_asked(question_text):
            return Question(
                id=f"q_{uuid4().hex[:8]}",
                text=question_text,
                category=QuestionCategory.SYSTEM_DESIGN,
                skill_id=context.skills_remaining[0] if context.skills_remaining else "data_platform_design",
                question_type=QuestionType.SCENARIO,
                difficulty=self._score_to_difficulty(difficulty),
                difficulty_score=difficulty,
                target_roles=[role],
                expected_points=["Clear architecture", "Scalability considerations", "Trade-off analysis"],
                is_generated=True,
            )
        
        # Large pool of fallback questions by role (15+ per role)
        fallback_questions = {
            Role.JUNIOR_DE: [
                ("Explain the difference between INNER JOIN and LEFT JOIN in SQL.", "sql_joins"),
                ("What is ETL and why is it important in data engineering?", "etl_concepts"),
                ("How would you handle duplicate records in a dataset?", "data_quality_concepts"),
                ("What is database normalization and why is it important?", "database_normalization"),
                ("Explain what an index is and when you would use one.", "indexing_basics"),
                ("What's the difference between DELETE and TRUNCATE in SQL?", "sql_basics"),
                ("How do you use GROUP BY and HAVING clauses in SQL?", "sql_aggregations"),
                ("What is a primary key vs a foreign key?", "relational_db_concepts"),
                ("Explain the concept of ACID properties in databases.", "relational_db_concepts"),
                ("What are the basic Git commands you use daily?", "git_basics"),
                ("How would you read a large CSV file efficiently in Python?", "python_fundamentals"),
                ("What's the difference between a list and a tuple in Python?", "python_fundamentals"),
                ("Explain what cloud storage is and give examples.", "cloud_fundamentals"),
                ("What is the difference between SQL and NoSQL databases?", "relational_db_concepts"),
                ("How would you schedule a script to run daily?", "linux_cli_basics"),
            ],
            Role.MID_DE: [
                ("How would you design an ETL pipeline for daily data loads of 10GB?", "etl_pipeline_design"),
                ("Explain window functions in SQL and give an example use case.", "sql_window_functions"),
                ("What strategies would you use to optimize a slow Spark job?", "spark_tuning"),
                ("Describe how you would implement incremental data loading.", "incremental_loads"),
                ("What is Apache Airflow and how do you design DAGs?", "airflow_basics"),
                ("Explain the difference between batch and micro-batch processing.", "batch_processing"),
                ("How do you handle schema evolution in a data pipeline?", "schema_evolution"),
                ("What are CTEs and when would you use recursive CTEs?", "sql_ctes"),
                ("Describe your approach to data quality testing.", "data_testing"),
                ("How does Spark lazy evaluation work and why is it useful?", "spark_fundamentals"),
                ("What are the different join strategies in Spark?", "spark_dataframes"),
                ("How would you partition data in a data lake?", "data_lakes_basics"),
                ("Explain the concept of data lineage and why it matters.", "lineage_tracking"),
                ("What monitoring would you set up for a production pipeline?", "pipeline_monitoring"),
                ("How do you handle late-arriving data in a pipeline?", "data_quality_concepts"),
            ],
            Role.SENIOR_DE: [
                ("How would you design a data platform that scales from 100GB to 10TB daily?", "data_platform_design"),
                ("Explain how you would implement exactly-once semantics in streaming.", "exactly_once_semantics"),
                ("What are the trade-offs between data lake and data warehouse?", "lakehouse_architecture"),
                ("How would you handle data skew in a distributed processing job?", "data_skew_handling"),
                ("Describe your approach to optimizing cloud costs for data workloads.", "cloud_cost_optimization"),
                ("How would you design a real-time analytics system?", "stream_processing"),
                ("Explain the CAP theorem and its implications for data systems.", "cap_theorem"),
                ("How do you ensure data consistency in an event-driven architecture?", "distributed_computing"),
                ("What strategies do you use for disaster recovery in data systems?", "distributed_computing"),
                ("How would you implement data observability at scale?", "data_observability"),
                ("Describe your approach to managing technical debt in pipelines.", "data_platform_design"),
                ("How do you design for both OLTP and OLAP workloads?", "data_platform_design"),
                ("What's your strategy for migrating from a monolith to microservices?", "data_platform_design"),
                ("How would you implement row-level security in a data warehouse?", "data_security"),
                ("Explain different caching strategies for data applications.", "caching_strategies"),
            ],
            Role.STAFF_DE: [
                ("How would you design a multi-cloud data strategy for an enterprise?", "multi_cloud_strategy"),
                ("Describe your approach to implementing data governance at scale.", "data_governance"),
                ("How do you balance technical debt with feature delivery?", "platform_strategy"),
                ("What's your process for evaluating new data technologies?", "technology_evaluation"),
                ("How do you align data platform strategy with business goals?", "platform_strategy"),
                ("Describe how you've led a major data platform migration.", "cloud_migration"),
                ("How do you build and mentor a high-performing data team?", "team_technical_leadership"),
                ("What's your approach to cross-team data standardization?", "cross_team_collaboration"),
                ("How do you prioritize platform features across multiple teams?", "stakeholder_management"),
                ("Describe your approach to data mesh implementation.", "data_mesh_concepts"),
                ("How do you ensure compliance with regulations like GDPR?", "compliance_frameworks"),
                ("What metrics do you use to measure platform success?", "platform_strategy"),
                ("How do you handle conflicting requirements from different teams?", "stakeholder_management"),
                ("Describe your experience with vendor evaluation and selection.", "vendor_evaluation"),
                ("How do you create a 3-year technical roadmap?", "technical_roadmapping"),
            ],
            Role.PRINCIPAL_DE: [
                ("How would you evaluate and recommend a new data technology?", "technology_evaluation"),
                ("Describe your approach to aligning platform strategy with business.", "platform_strategy"),
                ("How do you foster a data-driven culture across an organization?", "team_technical_leadership"),
                ("What's your vision for the future of data engineering?", "platform_strategy"),
                ("How do you influence technical direction without direct authority?", "stakeholder_management"),
                ("Describe a time you changed an organization's technical direction.", "team_technical_leadership"),
                ("How do you balance innovation with operational stability?", "platform_strategy"),
                ("What's your approach to building partnerships with vendors?", "vendor_evaluation"),
                ("How do you ensure knowledge transfer across the organization?", "cross_team_collaboration"),
                ("Describe your experience with M&A data integration.", "enterprise_data_architecture"),
                ("How do you handle organization-wide data security concerns?", "data_security"),
                ("What's your approach to building a center of excellence?", "team_technical_leadership"),
                ("How do you measure and communicate ROI of platform investments?", "platform_strategy"),
                ("Describe your experience presenting to C-level executives.", "stakeholder_management"),
                ("How do you stay current with rapidly evolving technologies?", "technology_evaluation"),
            ],
        }
        
        # Cloud-specific fallback questions by provider
        cloud_questions = {
            "aws": [
                ("How would you design a data pipeline using AWS Glue and S3?", "aws_glue"),
                ("Explain the differences between Redshift, Athena, and EMR for analytics.", "aws_analytics"),
                ("How do you optimize Redshift query performance?", "redshift_optimization"),
                ("Describe how you'd use AWS Lambda for event-driven data processing.", "aws_lambda"),
                ("What's your approach to setting up Kinesis for real-time streaming?", "aws_kinesis"),
                ("How would you implement data lake architecture using S3 and Lake Formation?", "aws_lake_formation"),
                ("Explain how you'd use Step Functions to orchestrate data workflows.", "aws_step_functions"),
                ("How do you manage cross-account data access in AWS?", "aws_iam"),
                ("Describe your approach to cost optimization in AWS data workloads.", "aws_cost_optimization"),
                ("How would you set up EMR for large-scale Spark processing?", "aws_emr"),
            ],
            "azure": [
                ("How would you design a data pipeline using Azure Data Factory?", "azure_data_factory"),
                ("Explain the differences between Azure Synapse and Databricks.", "azure_synapse"),
                ("How do you optimize Synapse Analytics for large-scale queries?", "synapse_optimization"),
                ("Describe how you'd use Azure Functions for data processing.", "azure_functions"),
                ("What's your approach to setting up Event Hubs for streaming?", "azure_event_hubs"),
                ("How would you implement a data lakehouse using ADLS Gen2?", "azure_adls"),
                ("Explain how you'd use Azure Logic Apps for data workflow automation.", "azure_logic_apps"),
                ("How do you manage data security using Azure Purview?", "azure_purview"),
                ("Describe your approach to cost management in Azure data workloads.", "azure_cost_optimization"),
                ("How would you set up HDInsight for distributed data processing?", "azure_hdinsight"),
            ],
            "gcp": [
                ("How would you design a data pipeline using Dataflow and Cloud Storage?", "gcp_dataflow"),
                ("Explain the differences between BigQuery and Dataproc for analytics.", "bigquery_dataproc"),
                ("How do you optimize BigQuery for cost and performance?", "bigquery_optimization"),
                ("Describe how you'd use Cloud Functions for event-driven processing.", "gcp_cloud_functions"),
                ("What's your approach to setting up Pub/Sub for real-time streaming?", "gcp_pubsub"),
                ("How would you implement data lake architecture using Cloud Storage?", "gcp_cloud_storage"),
                ("Explain how you'd use Cloud Composer (Airflow) for orchestration.", "gcp_cloud_composer"),
                ("How do you manage data governance using Data Catalog?", "gcp_data_catalog"),
                ("Describe your approach to cost optimization in GCP data workloads.", "gcp_cost_optimization"),
                ("How would you set up Dataproc for Spark processing at scale?", "gcp_dataproc"),
            ],
        }
        
        # Get cloud preference from context
        cloud_pref = context.session.setup.cloud_preference.value.lower()
        
        # Start with role-based questions
        questions = list(fallback_questions.get(role, fallback_questions[Role.MID_DE]))
        
        # Add cloud-specific questions if a specific cloud is selected
        if cloud_pref in cloud_questions:
            cloud_specific = cloud_questions[cloud_pref]
            # Insert cloud questions to ensure they get asked
            questions = cloud_specific + questions
        
        # Filter out already-asked questions
        available_questions = [
            (q, skill) for q, skill in questions
            if not context.session.is_question_asked(q)
        ]
        
        # If all questions are exhausted, use any (shouldn't happen with 15+ questions)
        if not available_questions:
            logger.warning("All fallback questions exhausted, reusing questions")
            available_questions = questions
        
        # Pick a random question from available
        q_text, skill_id = random.choice(available_questions)
        
        return Question(
            id=f"q_{uuid4().hex[:8]}",
            text=q_text,
            category=QuestionCategory.SYSTEM_DESIGN,
            skill_id=skill_id,
            question_type=QuestionType.SCENARIO,
            difficulty=self._score_to_difficulty(difficulty),
            difficulty_score=difficulty,
            target_roles=[role],
            expected_points=["Clear explanation", "Practical considerations", "Trade-off analysis"],
            is_generated=True,
        )
    
    def _score_to_difficulty(self, score: int) -> QuestionDifficulty:
        """Convert numeric difficulty to enum."""
        if score <= 3:
            return QuestionDifficulty.EASY
        elif score <= 6:
            return QuestionDifficulty.MEDIUM
        elif score <= 8:
            return QuestionDifficulty.HARD
        else:
            return QuestionDifficulty.EXPERT
    
    # =========================================================================
    # FOLLOW-UP DECISION
    # =========================================================================
    
    async def generate_followup(
        self,
        context: InterviewContext,
        evaluation: ResponseEvaluation
    ) -> FollowUpDecision:
        """
        Decide whether and what follow-up question to ask.
        
        Uses Gemini Flash for fast decision making.
        
        Follow-up types:
        - probe: Dig deeper into the answer
        - clarify: Ask for clarification on unclear points
        - challenge: Push back on potentially incorrect statements
        - example: Ask for a concrete example
        
        Args:
            context: Current interview context
            evaluation: Evaluation of the previous response
            
        Returns:
            FollowUpDecision with question if needed
        """
        session_id = context.session.session_id
        
        prompt = self.interviewer_prompts.generate_followup_prompt(context, evaluation)
        
        try:
            response = await self._call_gemini_flash(
                prompt, 
                max_tokens=512,
                trace_name="followup_decision_llm",
                trace_metadata={
                    "question_id": evaluation.question_id,
                    "score": evaluation.scores.overall_score,
                },
                session_id=session_id,
            )
            
            result = self._parse_followup_response(response, evaluation)
            logger.info(f"Follow-up decision: should_followup={result.should_followup}, type={result.followup_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}")
            return self._get_fallback_followup(evaluation)
    
    def _parse_followup_response(
        self,
        response: str,
        evaluation: ResponseEvaluation
    ) -> FollowUpDecision:
        """Parse AI response into FollowUpDecision."""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                return FollowUpDecision(
                    should_followup=data.get("should_followup", True),
                    reason=data.get("reason", "Need more depth"),
                    followup_type=data.get("type", "probe"),
                    followup_question=data.get("question"),
                    difficulty_adjustment=data.get("difficulty_adjustment", 0),
                )
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse follow-up JSON: {e}")
        
        # Don't use raw response if it looks like JSON (parsing failed)
        if response.strip().startswith("{") or response.strip().startswith("["):
            logger.warning("Response looks like malformed JSON, using fallback question")
            return self._get_fallback_followup(evaluation, followup_text=None)
        
        return self._get_fallback_followup(evaluation, followup_text=response.strip())
    
    def _get_fallback_followup(
        self,
        evaluation: ResponseEvaluation,
        followup_text: str | None = None
    ) -> FollowUpDecision:
        """Get fallback follow-up when generation fails."""
        score = evaluation.scores.overall_score
        
        if score < 4:
            return FollowUpDecision(
                should_followup=True,
                reason="Response needs clarification",
                followup_type="clarify",
                followup_question=followup_text or "Could you explain that concept in simpler terms?",
                difficulty_adjustment=-1,
            )
        elif score < 6:
            return FollowUpDecision(
                should_followup=True,
                reason="Response could use more depth",
                followup_type="probe",
                followup_question=followup_text or "Can you provide a specific example from your experience?",
                difficulty_adjustment=0,
            )
        elif score < 8:
            return FollowUpDecision(
                should_followup=True,
                reason="Good answer, testing deeper knowledge",
                followup_type="challenge",
                followup_question=followup_text or "What would you do differently if the scale was 10x larger?",
                difficulty_adjustment=1,
            )
        else:
            return FollowUpDecision(
                should_followup=False,
                reason="Excellent answer, moving on",
                difficulty_adjustment=1,
            )
    
    # =========================================================================
    # RESPONSE EVALUATION
    # =========================================================================
    
    async def evaluate_response(
        self,
        question: Question,
        transcript: str,
        context: InterviewContext
    ) -> ResponseEvaluation:
        """
        Evaluate a candidate's response to a question.
        
        Uses Gemini Pro for accurate, thorough evaluation.
        
        Args:
            question: The question that was asked
            transcript: Transcribed response
            context: Current interview context
            
        Returns:
            Complete ResponseEvaluation
        """
        session_id = context.session.session_id
        
        prompt = self.evaluator_prompts.generate_evaluation_prompt(
            question=question,
            transcript=transcript,
            context=context
        )
        
        try:
            response = await self._call_gemini_pro(
                prompt, 
                max_tokens=1024,
                trace_name="evaluation_llm",
                trace_metadata={
                    "question_id": question.id,
                    "skill_id": question.skill_id,
                    "transcript_length": len(transcript),
                },
                session_id=session_id,
            )
            
            evaluation = self._parse_evaluation_response(response, question, transcript)
            
            # Log evaluation results
            logger.info(
                f"Evaluation complete: score={evaluation.scores.overall_score:.1f}, "
                f"needs_followup={evaluation.needs_followup}"
            )
            
            # Log score to Langfuse
            if self.langfuse:
                try:
                    self.langfuse.create_score(
                        name="overall_score",
                        value=evaluation.scores.overall_score,
                        comment=f"Skill: {question.skill_id}, Session: {session_id}",
                    )
                except Exception as lf_err:
                    logger.warning(f"Langfuse score failed: {lf_err}")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return self._get_fallback_evaluation(question, transcript)
    
    def _parse_evaluation_response(
        self,
        response: str,
        question: Question,
        transcript: str
    ) -> ResponseEvaluation:
        """Parse AI response into ResponseEvaluation."""
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                scores = data.get("scores", {})
                feedback = data.get("feedback", {})
                
                return ResponseEvaluation(
                    question_id=question.id,
                    skill_id=question.skill_id,
                    transcript=transcript,
                    response_duration_seconds=data.get("response_duration", 60.0),
                    scores=ScoreBreakdown(
                        technical_correctness=scores.get("technical_correctness", 5.0),
                        depth_of_understanding=scores.get("depth_of_understanding", 5.0),
                        practical_experience=scores.get("practical_experience", 5.0),
                        communication_clarity=scores.get("communication_clarity", 5.0),
                        confidence=scores.get("confidence", 5.0),
                    ),
                    feedback=EvaluationFeedback(
                        what_went_well=feedback.get("what_went_well", []),
                        what_was_missing=feedback.get("what_was_missing", []),
                        red_flags=feedback.get("red_flags", []),
                        seniority_signals=feedback.get("seniority_signals", []),
                        improvement_suggestions=feedback.get("improvement_suggestions", []),
                    ),
                    needs_followup=data.get("needs_followup", False),
                    followup_reason=data.get("followup_reason"),
                    followup_type=data.get("followup_type"),
                    difficulty_delta=data.get("difficulty_delta", 0),
                    evaluator_notes=data.get("notes"),
                )
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse evaluation JSON: {e}")
        
        return self._get_fallback_evaluation(question, transcript)
    
    def _get_fallback_evaluation(
        self,
        question: Question,
        transcript: str
    ) -> ResponseEvaluation:
        """Get fallback evaluation when AI fails."""
        # Simple heuristic-based evaluation
        word_count = len(transcript.split())
        
        # Base score on response length and some keywords
        base_score = min(7, max(3, word_count / 50))
        
        # Adjust for technical keywords
        tech_keywords = [
            "architecture", "scalability", "performance", "distributed",
            "consistency", "availability", "partition", "latency",
            "throughput", "batch", "streaming", "pipeline",
        ]
        keyword_count = sum(1 for kw in tech_keywords if kw.lower() in transcript.lower())
        tech_bonus = min(2, keyword_count * 0.3)
        
        final_score = min(9, base_score + tech_bonus)
        
        return ResponseEvaluation(
            question_id=question.id,
            skill_id=question.skill_id,
            transcript=transcript,
            response_duration_seconds=60.0,
            scores=ScoreBreakdown(
                technical_correctness=final_score,
                depth_of_understanding=final_score - 0.5,
                practical_experience=final_score - 1,
                communication_clarity=final_score + 0.5,
                confidence=final_score,
            ),
            feedback=EvaluationFeedback(
                what_went_well=["Response provided"],
                what_was_missing=["Could not evaluate in detail"],
                red_flags=[],
                seniority_signals=[],
            ),
            needs_followup=final_score < 6,
            followup_reason="Would like more detail" if final_score < 6 else None,
            difficulty_delta=1 if final_score > 7 else (-1 if final_score < 4 else 0),
        )
    
    # =========================================================================
    # DIFFICULTY ADAPTATION
    # =========================================================================
    
    async def suggest_difficulty_adjustment(
        self,
        context: InterviewContext,
        recent_evaluations: list[ResponseEvaluation]
    ) -> int:
        """
        Suggest difficulty adjustment based on recent performance.
        
        Returns:
            Adjustment value (-2 to +2)
        """
        if not recent_evaluations:
            return 0
        
        # Calculate average recent score
        avg_score = sum(e.scores.overall_score for e in recent_evaluations) / len(recent_evaluations)
        
        # Determine adjustment
        if avg_score >= 8.5:
            return 2  # Significantly increase difficulty
        elif avg_score >= 7:
            return 1  # Slightly increase difficulty
        elif avg_score >= 5:
            return 0  # Keep same difficulty
        elif avg_score >= 3:
            return -1  # Slightly decrease difficulty
        else:
            return -2  # Significantly decrease difficulty

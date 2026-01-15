"""
Role, skill, and experience definitions for DataReady.io

Defines the strict taxonomy for:
- Experience levels
- Target roles
- Cloud preferences
- Technical skills by role
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Experience(str, Enum):
    """Years of experience categories."""
    
    ENTRY = "0-2"      # Entry level
    MID = "2-5"        # Mid level
    SENIOR = "5-8"     # Senior level
    STAFF = "8-12"     # Staff level
    PRINCIPAL = "12+"  # Principal/Distinguished


class Role(str, Enum):
    """Target role definitions."""
    
    JUNIOR_DE = "junior_data_engineer"
    MID_DE = "mid_data_engineer"
    SENIOR_DE = "senior_data_engineer"
    STAFF_DE = "staff_data_engineer"
    PRINCIPAL_DE = "principal_data_engineer"
    
    @property
    def display_name(self) -> str:
        """Human-readable role name."""
        names = {
            "junior_data_engineer": "Junior Data Engineer",
            "mid_data_engineer": "Mid-Level Data Engineer",
            "senior_data_engineer": "Senior Data Engineer",
            "staff_data_engineer": "Staff Data Engineer",
            "principal_data_engineer": "Principal Data Engineer",
        }
        return names.get(self.value, self.value)
    
    @property
    def experience_range(self) -> str:
        """Expected experience for this role."""
        ranges = {
            "junior_data_engineer": "0-2 years",
            "mid_data_engineer": "2-5 years",
            "senior_data_engineer": "5-8 years",
            "staff_data_engineer": "8-12 years",
            "principal_data_engineer": "12+ years",
        }
        return ranges.get(self.value, "Unknown")


class CloudPreference(str, Enum):
    """Cloud platform preference."""
    
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    MULTI = "multi_cloud"
    AGNOSTIC = "cloud_agnostic"


class SkillCategory(str, Enum):
    """High-level skill categories."""
    
    SQL = "sql"
    PYTHON = "python"
    ETL = "etl_pipelines"
    SPARK = "spark"
    STREAMING = "streaming"
    CLOUD = "cloud"
    ORCHESTRATION = "orchestration"
    DATA_MODELING = "data_modeling"
    DATA_QUALITY = "data_quality"
    SYSTEM_DESIGN = "system_design"
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    GOVERNANCE = "governance"
    PERFORMANCE = "performance"
    OBSERVABILITY = "observability"


class Skill(BaseModel):
    """Individual skill definition."""
    
    id: str = Field(..., description="Unique skill identifier")
    name: str = Field(..., description="Human-readable skill name")
    category: SkillCategory = Field(..., description="Parent category")
    description: str = Field(..., description="Skill description")
    applicable_roles: list[Role] = Field(
        default_factory=list,
        description="Roles where this skill is relevant"
    )
    cloud_specific: CloudPreference | None = Field(
        default=None,
        description="If skill is cloud-specific"
    )


# ============================================================================
# SKILL DEFINITIONS BY ROLE
# ============================================================================

JUNIOR_SKILLS: list[str] = [
    # SQL
    "sql_basics",
    "sql_joins",
    "sql_aggregations",
    "sql_subqueries",
    # ETL
    "etl_concepts",
    "data_extraction",
    "data_transformation_basics",
    "data_loading",
    # Databases
    "relational_db_concepts",
    "database_normalization",
    "indexing_basics",
    # Tooling
    "git_basics",
    "linux_cli_basics",
    "python_fundamentals",
    # Cloud
    "cloud_fundamentals",
    "cloud_storage_basics",
]

MID_SKILLS: list[str] = [
    # Advanced SQL
    "sql_window_functions",
    "sql_ctes",
    "sql_optimization_basics",
    "sql_stored_procedures",
    # Spark
    "spark_fundamentals",
    "spark_dataframes",
    "spark_sql",
    "spark_partitioning",
    # ETL Design
    "etl_pipeline_design",
    "batch_processing",
    "incremental_loads",
    "data_validation",
    # Orchestration
    "airflow_basics",
    "dag_design",
    "task_dependencies",
    # Data Quality
    "data_quality_concepts",
    "data_testing",
    "schema_evolution",
    # Cloud Services
    "cloud_data_services",
    "data_lakes_basics",
]

SENIOR_SKILLS: list[str] = [
    # Platform Design
    "data_platform_design",
    "lakehouse_architecture",
    "data_mesh_concepts",
    # Performance
    "query_optimization",
    "spark_tuning",
    "data_skew_handling",
    "caching_strategies",
    # Distributed Systems
    "distributed_computing",
    "cap_theorem",
    "consistency_models",
    # Streaming
    "stream_processing",
    "kafka_architecture",
    "exactly_once_semantics",
    "windowing_concepts",
    # Cloud
    "cloud_cost_optimization",
    "multi_region_design",
    "infrastructure_as_code",
    # Observability
    "data_observability",
    "pipeline_monitoring",
    "alerting_strategies",
    "lineage_tracking",
]

STAFF_SKILLS: list[str] = [
    # Architecture
    "enterprise_data_architecture",
    "cross_domain_integration",
    "platform_strategy",
    "technology_evaluation",
    # Governance
    "data_governance",
    "data_security",
    "access_control_design",
    "compliance_frameworks",
    # Multi-cloud
    "multi_cloud_strategy",
    "cloud_migration",
    "vendor_evaluation",
    # Organization
    "team_technical_leadership",
    "cross_team_collaboration",
    "technical_roadmapping",
    "stakeholder_management",
    # Advanced Topics
    "ml_infrastructure",
    "real_time_analytics",
    "data_contracts",
    "api_design",
]


# ============================================================================
# SKILL CATALOG
# ============================================================================

SKILL_CATALOG: dict[str, Skill] = {
    # === SQL SKILLS ===
    "sql_basics": Skill(
        id="sql_basics",
        name="SQL Fundamentals",
        category=SkillCategory.SQL,
        description="Basic SELECT, WHERE, ORDER BY, LIMIT operations",
        applicable_roles=[Role.JUNIOR_DE]
    ),
    "sql_joins": Skill(
        id="sql_joins",
        name="SQL Joins",
        category=SkillCategory.SQL,
        description="INNER, LEFT, RIGHT, FULL, CROSS joins",
        applicable_roles=[Role.JUNIOR_DE, Role.MID_DE]
    ),
    "sql_aggregations": Skill(
        id="sql_aggregations",
        name="SQL Aggregations",
        category=SkillCategory.SQL,
        description="GROUP BY, HAVING, aggregate functions",
        applicable_roles=[Role.JUNIOR_DE, Role.MID_DE]
    ),
    "sql_subqueries": Skill(
        id="sql_subqueries",
        name="SQL Subqueries",
        category=SkillCategory.SQL,
        description="Nested queries, correlated subqueries",
        applicable_roles=[Role.JUNIOR_DE, Role.MID_DE]
    ),
    "sql_window_functions": Skill(
        id="sql_window_functions",
        name="Window Functions",
        category=SkillCategory.SQL,
        description="ROW_NUMBER, RANK, LAG, LEAD, partitioning",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "sql_ctes": Skill(
        id="sql_ctes",
        name="Common Table Expressions",
        category=SkillCategory.SQL,
        description="WITH clause, recursive CTEs",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "sql_optimization_basics": Skill(
        id="sql_optimization_basics",
        name="SQL Optimization",
        category=SkillCategory.SQL,
        description="Query plans, index usage, query rewriting",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "query_optimization": Skill(
        id="query_optimization",
        name="Advanced Query Optimization",
        category=SkillCategory.PERFORMANCE,
        description="Complex query tuning, cost-based optimization",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === ETL SKILLS ===
    "etl_concepts": Skill(
        id="etl_concepts",
        name="ETL Concepts",
        category=SkillCategory.ETL,
        description="Extract, Transform, Load fundamentals",
        applicable_roles=[Role.JUNIOR_DE]
    ),
    "etl_pipeline_design": Skill(
        id="etl_pipeline_design",
        name="ETL Pipeline Design",
        category=SkillCategory.ETL,
        description="End-to-end pipeline architecture",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "batch_processing": Skill(
        id="batch_processing",
        name="Batch Processing",
        category=SkillCategory.ETL,
        description="Batch job design and optimization",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "incremental_loads": Skill(
        id="incremental_loads",
        name="Incremental Loading",
        category=SkillCategory.ETL,
        description="CDC, watermarks, merge strategies",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    
    # === SPARK SKILLS ===
    "spark_fundamentals": Skill(
        id="spark_fundamentals",
        name="Spark Fundamentals",
        category=SkillCategory.SPARK,
        description="RDDs, transformations, actions, lazy evaluation",
        applicable_roles=[Role.MID_DE]
    ),
    "spark_dataframes": Skill(
        id="spark_dataframes",
        name="Spark DataFrames",
        category=SkillCategory.SPARK,
        description="DataFrame API, operations, UDFs",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "spark_tuning": Skill(
        id="spark_tuning",
        name="Spark Performance Tuning",
        category=SkillCategory.SPARK,
        description="Memory management, partitioning, broadcast joins",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "data_skew_handling": Skill(
        id="data_skew_handling",
        name="Data Skew Handling",
        category=SkillCategory.SPARK,
        description="Detecting and resolving data skew issues",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === STREAMING SKILLS ===
    "stream_processing": Skill(
        id="stream_processing",
        name="Stream Processing",
        category=SkillCategory.STREAMING,
        description="Real-time data processing patterns",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "kafka_architecture": Skill(
        id="kafka_architecture",
        name="Kafka Architecture",
        category=SkillCategory.STREAMING,
        description="Topics, partitions, consumer groups, replication",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "exactly_once_semantics": Skill(
        id="exactly_once_semantics",
        name="Exactly-Once Semantics",
        category=SkillCategory.STREAMING,
        description="Delivery guarantees, idempotency, transactions",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === ORCHESTRATION SKILLS ===
    "airflow_basics": Skill(
        id="airflow_basics",
        name="Airflow Fundamentals",
        category=SkillCategory.ORCHESTRATION,
        description="DAGs, operators, scheduling, connections",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "dag_design": Skill(
        id="dag_design",
        name="DAG Design Patterns",
        category=SkillCategory.ORCHESTRATION,
        description="Best practices for DAG architecture",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    
    # === DISTRIBUTED SYSTEMS ===
    "distributed_computing": Skill(
        id="distributed_computing",
        name="Distributed Computing",
        category=SkillCategory.DISTRIBUTED_SYSTEMS,
        description="Parallel processing, fault tolerance",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "cap_theorem": Skill(
        id="cap_theorem",
        name="CAP Theorem",
        category=SkillCategory.DISTRIBUTED_SYSTEMS,
        description="Consistency, availability, partition tolerance",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === SYSTEM DESIGN ===
    "data_platform_design": Skill(
        id="data_platform_design",
        name="Data Platform Design",
        category=SkillCategory.SYSTEM_DESIGN,
        description="End-to-end platform architecture",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "lakehouse_architecture": Skill(
        id="lakehouse_architecture",
        name="Lakehouse Architecture",
        category=SkillCategory.SYSTEM_DESIGN,
        description="Delta Lake, Iceberg, data lakehouse patterns",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "enterprise_data_architecture": Skill(
        id="enterprise_data_architecture",
        name="Enterprise Data Architecture",
        category=SkillCategory.SYSTEM_DESIGN,
        description="Organization-wide data strategy and design",
        applicable_roles=[Role.STAFF_DE, Role.PRINCIPAL_DE]
    ),
    
    # === GOVERNANCE ===
    "data_governance": Skill(
        id="data_governance",
        name="Data Governance",
        category=SkillCategory.GOVERNANCE,
        description="Policies, standards, stewardship",
        applicable_roles=[Role.STAFF_DE, Role.PRINCIPAL_DE]
    ),
    "data_security": Skill(
        id="data_security",
        name="Data Security",
        category=SkillCategory.GOVERNANCE,
        description="Encryption, access control, PII handling",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === OBSERVABILITY ===
    "data_observability": Skill(
        id="data_observability",
        name="Data Observability",
        category=SkillCategory.OBSERVABILITY,
        description="Monitoring data quality and pipeline health",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "pipeline_monitoring": Skill(
        id="pipeline_monitoring",
        name="Pipeline Monitoring",
        category=SkillCategory.OBSERVABILITY,
        description="Metrics, logging, alerting for pipelines",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "lineage_tracking": Skill(
        id="lineage_tracking",
        name="Data Lineage",
        category=SkillCategory.OBSERVABILITY,
        description="Tracking data flow and transformations",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    
    # === DATA QUALITY ===
    "data_quality_concepts": Skill(
        id="data_quality_concepts",
        name="Data Quality Concepts",
        category=SkillCategory.DATA_QUALITY,
        description="Dimensions of data quality, validation",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "data_testing": Skill(
        id="data_testing",
        name="Data Testing",
        category=SkillCategory.DATA_QUALITY,
        description="Unit tests, integration tests for pipelines",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "data_contracts": Skill(
        id="data_contracts",
        name="Data Contracts",
        category=SkillCategory.DATA_QUALITY,
        description="Schema contracts between producers and consumers",
        applicable_roles=[Role.STAFF_DE, Role.PRINCIPAL_DE]
    ),
    
    # === CLOUD SKILLS ===
    "cloud_fundamentals": Skill(
        id="cloud_fundamentals",
        name="Cloud Fundamentals",
        category=SkillCategory.CLOUD,
        description="Basic cloud concepts, compute, storage",
        applicable_roles=[Role.JUNIOR_DE]
    ),
    "cloud_data_services": Skill(
        id="cloud_data_services",
        name="Cloud Data Services",
        category=SkillCategory.CLOUD,
        description="Managed databases, data warehouses, analytics",
        applicable_roles=[Role.MID_DE, Role.SENIOR_DE]
    ),
    "cloud_cost_optimization": Skill(
        id="cloud_cost_optimization",
        name="Cloud Cost Optimization",
        category=SkillCategory.CLOUD,
        description="Right-sizing, reserved instances, cost monitoring",
        applicable_roles=[Role.SENIOR_DE, Role.STAFF_DE]
    ),
    "multi_cloud_strategy": Skill(
        id="multi_cloud_strategy",
        name="Multi-Cloud Strategy",
        category=SkillCategory.CLOUD,
        description="Cross-cloud architecture and portability",
        applicable_roles=[Role.STAFF_DE, Role.PRINCIPAL_DE]
    ),
    
    # === TOOLING ===
    "git_basics": Skill(
        id="git_basics",
        name="Git Fundamentals",
        category=SkillCategory.PYTHON,  # Using PYTHON as general tooling
        description="Version control basics, branching, merging",
        applicable_roles=[Role.JUNIOR_DE]
    ),
    "linux_cli_basics": Skill(
        id="linux_cli_basics",
        name="Linux CLI",
        category=SkillCategory.PYTHON,
        description="Command line navigation, scripting basics",
        applicable_roles=[Role.JUNIOR_DE]
    ),
    "python_fundamentals": Skill(
        id="python_fundamentals",
        name="Python Fundamentals",
        category=SkillCategory.PYTHON,
        description="Python syntax, data structures, functions",
        applicable_roles=[Role.JUNIOR_DE, Role.MID_DE]
    ),
}


def get_skills_for_role(role: Role) -> list[Skill]:
    """Get all skills applicable to a specific role."""
    return [
        skill for skill in SKILL_CATALOG.values()
        if role in skill.applicable_roles
    ]


def get_role_focus_areas(role: Role) -> list[str]:
    """Get the focus areas description for a role."""
    focus_areas = {
        Role.JUNIOR_DE: [
            "SQL fundamentals",
            "ETL basics",
            "Relational databases",
            "Git, Linux basics",
            "Cloud fundamentals",
            "Conceptual understanding",
        ],
        Role.MID_DE: [
            "Advanced SQL",
            "ETL pipeline design",
            "Spark fundamentals",
            "Cloud-native services",
            "Workflow orchestration",
            "Data quality & testing",
        ],
        Role.SENIOR_DE: [
            "Data platform design",
            "Performance tuning",
            "Distributed systems",
            "Streaming design",
            "Cloud cost optimization",
            "Observability and resiliency",
        ],
        Role.STAFF_DE: [
            "Platform ownership",
            "Cross-domain architecture",
            "Governance & security",
            "Multi-cloud strategy",
            "Organizational impact",
            "Long-term roadmap decisions",
        ],
        Role.PRINCIPAL_DE: [
            "Enterprise architecture",
            "Technology vision",
            "Industry influence",
            "Organization-wide impact",
            "Strategic partnerships",
            "Innovation leadership",
        ],
    }
    return focus_areas.get(role, [])

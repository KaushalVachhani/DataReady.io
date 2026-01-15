"""
Metadata API endpoints

Provides reference data for:
- Roles
- Skills
- Experience levels
- Cloud options
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.models.roles import (
    Role,
    Experience,
    CloudPreference,
    SkillCategory,
    SKILL_CATALOG,
    get_skills_for_role,
    get_role_focus_areas,
)
from src.models.interview import InterviewMode

router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class RoleInfo(BaseModel):
    """Information about a role."""
    id: str
    name: str
    experience_range: str
    focus_areas: list[str]


class SkillInfo(BaseModel):
    """Information about a skill."""
    id: str
    name: str
    category: str
    description: str
    applicable_roles: list[str]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/roles")
async def get_roles() -> list[RoleInfo]:
    """Get all available interview roles."""
    roles = []
    
    for role in Role:
        roles.append(RoleInfo(
            id=role.value,
            name=role.display_name,
            experience_range=role.experience_range,
            focus_areas=get_role_focus_areas(role),
        ))
    
    return roles


@router.get("/roles/{role_id}")
async def get_role_details(role_id: str) -> dict[str, Any]:
    """Get detailed information about a specific role."""
    try:
        role = Role(role_id)
    except ValueError:
        return {"error": f"Unknown role: {role_id}"}
    
    skills = get_skills_for_role(role)
    
    return {
        "id": role.value,
        "name": role.display_name,
        "experience_range": role.experience_range,
        "focus_areas": get_role_focus_areas(role),
        "skills": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category.value,
            }
            for s in skills
        ],
    }


@router.get("/skills")
async def get_skills() -> list[SkillInfo]:
    """Get all available skills."""
    skills = []
    
    for skill_id, skill in SKILL_CATALOG.items():
        skills.append(SkillInfo(
            id=skill.id,
            name=skill.name,
            category=skill.category.value,
            description=skill.description,
            applicable_roles=[r.value for r in skill.applicable_roles],
        ))
    
    return skills


@router.get("/skills/by-category")
async def get_skills_by_category() -> dict[str, list[SkillInfo]]:
    """Get skills grouped by category."""
    categories: dict[str, list[SkillInfo]] = {}
    
    for skill in SKILL_CATALOG.values():
        category = skill.category.value
        if category not in categories:
            categories[category] = []
        
        categories[category].append(SkillInfo(
            id=skill.id,
            name=skill.name,
            category=category,
            description=skill.description,
            applicable_roles=[r.value for r in skill.applicable_roles],
        ))
    
    return categories


@router.get("/skills/by-role/{role_id}")
async def get_skills_for_role_endpoint(role_id: str) -> list[SkillInfo]:
    """Get skills applicable to a specific role."""
    try:
        role = Role(role_id)
    except ValueError:
        return []
    
    skills = get_skills_for_role(role)
    
    return [
        SkillInfo(
            id=s.id,
            name=s.name,
            category=s.category.value,
            description=s.description,
            applicable_roles=[r.value for r in s.applicable_roles],
        )
        for s in skills
    ]


@router.get("/experience-levels")
async def get_experience_levels() -> list[dict[str, str]]:
    """Get all experience level options."""
    return [
        {"id": exp.value, "name": exp.name.title()}
        for exp in Experience
    ]


@router.get("/cloud-options")
async def get_cloud_options() -> list[dict[str, str]]:
    """Get all cloud preference options."""
    display_names = {
        "aws": "Amazon Web Services (AWS)",
        "gcp": "Google Cloud Platform (GCP)",
        "azure": "Microsoft Azure",
        "multi_cloud": "Multi-Cloud",
        "cloud_agnostic": "Cloud Agnostic",
    }
    
    return [
        {"id": cloud.value, "name": display_names.get(cloud.value, cloud.value)}
        for cloud in CloudPreference
    ]


@router.get("/interview-modes")
async def get_interview_modes() -> list[dict[str, str]]:
    """Get all interview mode options."""
    descriptions = {
        "structured": "Fixed questions only, no follow-ups",
        "structured_followup": "Questions with adaptive follow-ups based on responses",
        "stress": "High-pressure interview simulation (coming soon)",
    }
    
    return [
        {
            "id": mode.value,
            "name": mode.name.replace("_", " ").title(),
            "description": descriptions.get(mode.value, ""),
        }
        for mode in InterviewMode
    ]


@router.get("/skill-categories")
async def get_skill_categories() -> list[dict[str, str]]:
    """Get all skill category options."""
    display_names = {
        "sql": "SQL",
        "python": "Python & Tooling",
        "etl_pipelines": "ETL & Pipelines",
        "spark": "Apache Spark",
        "streaming": "Streaming",
        "cloud": "Cloud Platforms",
        "orchestration": "Orchestration",
        "data_modeling": "Data Modeling",
        "data_quality": "Data Quality",
        "system_design": "System Design",
        "distributed_systems": "Distributed Systems",
        "governance": "Governance & Security",
        "performance": "Performance",
        "observability": "Observability",
    }
    
    return [
        {"id": cat.value, "name": display_names.get(cat.value, cat.value)}
        for cat in SkillCategory
    ]

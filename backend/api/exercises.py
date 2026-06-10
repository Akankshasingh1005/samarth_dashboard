"""Exercise API — CRUD + seeding for Day-1 exercises."""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from models.exercise import Exercise
from services.auth_service import get_current_user, get_current_admin
from models.user import User

router = APIRouter()


class ExerciseOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    difficulty: str
    target_joints: List[str]
    target_reps: int
    target_sets: int
    target_rom_degrees: float
    estimated_duration_seconds: int
    gif_url: str | None
    safety_instructions: List[str]
    contraindications: List[str]
    is_active: bool


def _to_out(e: Exercise) -> ExerciseOut:
    return ExerciseOut(
        id=str(e.id),
        name=e.name,
        slug=e.slug,
        description=e.description,
        category=e.category,
        difficulty=e.difficulty,
        target_joints=e.target_joints,
        target_reps=e.target_reps,
        target_sets=e.target_sets,
        target_rom_degrees=e.target_rom_degrees,
        estimated_duration_seconds=e.estimated_duration_seconds,
        gif_url=e.gif_url,
        safety_instructions=e.safety_instructions,
        contraindications=e.contraindications,
        is_active=e.is_active,
    )


@router.get("/", response_model=List[ExerciseOut])
async def list_exercises(current_user: User = Depends(get_current_user)):
    exercises = await Exercise.find(Exercise.is_active == True).to_list()
    return [_to_out(e) for e in exercises]


@router.get("/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(exercise_id: str, current_user: User = Depends(get_current_user)):
    from beanie import PydanticObjectId
    exercise = await Exercise.get(PydanticObjectId(exercise_id))
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return _to_out(exercise)


async def run_seeding() -> int:
    """Initialize the database with Day-1 exercises. Skips already existing slugs."""
    day1 = [
        {
            "name": "Step Up Step Down",
            "slug": "step-up-step-down",
            "description": "Step up onto a stable platform with one foot followed by the other, then step back down. Improves lower-limb strength, balance, and proprioception.",
            "category": "full_leg",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 180,
            "gif_url": "/static/exercises/step-up-step-down.gif",
            "safety_instructions": [
                "Use a stable, non-slip platform",
                "Keep knee aligned over second toe",
                "Do not lock knee at top",
                "Hold a rail if needed for balance",
            ],
            "contraindications": ["Severe knee instability", "Recent total knee replacement < 6 weeks"],
        },
        {
            "name": "Leg Press",
            "slug": "leg-press",
            "description": "Push against a resistance surface using both legs. Strengthens quadriceps, hamstrings, and glutes in a controlled range of motion.",
            "category": "full_leg",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 12,
            "target_sets": 3,
            "target_rom_degrees": 100.0,
            "estimated_duration_seconds": 150,
            "gif_url": "/static/exercises/leg-press.gif",
            "safety_instructions": [
                "Keep lower back pressed against surface",
                "Do not lock knees at full extension",
                "Control the eccentric (return) phase",
                "Stop if sharp knee pain occurs",
            ],
            "contraindications": ["Acute knee inflammation", "Unstable patella"],
        },
        {
            "name": "Knee Extension",
            "slug": "knee-extension",
            "description": "From a seated position, straighten the knee by contracting the quadriceps. Excellent for isolated quad strengthening post-surgery.",
            "category": "knee",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee"],
            "target_reps": 15,
            "target_sets": 3,
            "target_rom_degrees": 120.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/knee-extension.gif",
            "safety_instructions": [
                "Perform slowly and with control",
                "Do not hyperextend the knee",
                "Keep thigh firmly on seat",
                "Pause at full extension for 2 seconds",
            ],
            "contraindications": ["ACL graft < 12 weeks post-op (open chain)", "Patellofemoral syndrome flare"],
        },
        {
            "name": "Hip Abduction",
            "slug": "hip-abduction",
            "description": "Standing or lying hip abduction strengthens the gluteus medius and prevents knee valgus during gait and functional activities.",
            "category": "hip",
            "difficulty": "beginner",
            "target_joints": ["left_hip", "right_hip"],
            "target_reps": 15,
            "target_sets": 3,
            "target_rom_degrees": 45.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/hip-abduction.gif",
            "safety_instructions": [
                "Keep pelvis level throughout movement",
                "Do not rotate the trunk",
                "Move through pain-free range only",
                "Hold a support if performing standing",
            ],
            "contraindications": ["Hip labral tear (confirm with physio)", "Acute hip bursitis"],
        },
        {
            "name": "Ankle Dorsiflexion",
            "slug": "ankle-dorsiflexion",
            "description": "Seated or standing ankle dorsiflexion improves ankle mobility, essential for normal gait and preventing compensatory patterns during squatting.",
            "category": "ankle",
            "difficulty": "beginner",
            "target_joints": ["left_ankle", "right_ankle"],
            "target_reps": 20,
            "target_sets": 3,
            "target_rom_degrees": 30.0,
            "estimated_duration_seconds": 90,
            "gif_url": "/static/exercises/ankle-dorsiflexion.gif",
            "safety_instructions": [
                "Perform slowly with full range",
                "Keep heel on floor when seated",
                "Progress to weight-bearing when comfortable",
            ],
            "contraindications": ["Achilles tendon rupture < 8 weeks", "Acute ankle sprain Grade III"],
        },
    ]

    seeded = 0
    for ex_data in day1:
        existing = await Exercise.find_one(Exercise.slug == ex_data["slug"])
        if not existing:
            await Exercise(**ex_data).insert()
            seeded += 1
    return seeded


@router.post("/seed", status_code=201, summary="Seed Day-1 exercises (admin only)")
async def seed_exercises(admin: User = Depends(get_current_admin)):
    """Initialize the database with Day-1 exercises. Skips already existing slugs."""
    seeded = await run_seeding()
    return {"message": f"Seeded {seeded} exercises", "total_in_db": 5}

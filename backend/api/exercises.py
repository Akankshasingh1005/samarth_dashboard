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
    """Initialize the database with the updated 10 exercises. Removes existing first."""
    # Remove all previous exercises to ensure only the requested 10 exist
    await Exercise.find_all().delete()

    day1 = [
        {
            "name": "Straight Leg Raise",
            "slug": "straight-leg-raise",
            "description": "Lying on your back, raise one leg straight up while keeping the other knee bent. Strengthens the quadriceps and hip flexors.",
            "category": "hip",
            "difficulty": "beginner",
            "target_joints": ["left_hip", "right_hip"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 45.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/straight-leg-raise.gif",
            "safety_instructions": ["Keep your lower back flat on the floor", "Do not arch your spine", "Lift slowly with a straight knee"],
            "contraindications": ["Severe lower back pain", "Acute hip inflammation"],
        },
        {
            "name": "Inline Lunge",
            "slug": "inline-lunge",
            "description": "Place one foot in front of the other in a straight line and lower your hips until both knees are bent at about 90 degrees. Improves balance, stability, and lower body strength.",
            "category": "full_leg",
            "difficulty": "intermediate",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 180,
            "gif_url": "/static/exercises/inline-lunge.gif",
            "safety_instructions": ["Keep front knee aligned over front foot", "Ensure torso remains upright", "Perform near a wall for balance support if needed"],
            "contraindications": ["Severe knee instability", "Patellofemoral pain flare-up"],
        },
        {
            "name": "Hurdle Step",
            "slug": "hurdle-step",
            "description": "Step over an imaginary hurdle, lifting the knee high towards the chest and stepping down with control. Evaluates and improves hip mobility, balance, and core stability.",
            "category": "hip",
            "difficulty": "intermediate",
            "target_joints": ["left_hip", "right_hip", "left_knee", "right_knee"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 80.0,
            "estimated_duration_seconds": 150,
            "gif_url": "/static/exercises/hurdle-step.gif",
            "safety_instructions": ["Avoid excessive leaning or twisting of the trunk", "Raise knee as high as comfortable", "Step down softly"],
            "contraindications": ["Severe hip osteoarthritis", "Uncompensated balance impairment"],
        },
        {
            "name": "Side Lunge",
            "slug": "side-lunge",
            "description": "Step to the side and lower your hips, bending one knee while keeping the other leg straight. Strengthens lateral hip muscles and improves flexibility.",
            "category": "full_leg",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 70.0,
            "estimated_duration_seconds": 150,
            "gif_url": "/static/exercises/side-lunge.gif",
            "safety_instructions": ["Keep knee of bending leg tracking over the toes", "Keep trailing leg completely straight", "Keep chest lifted"],
            "contraindications": ["Adductor strain", "Lateral meniscus tear"],
        },
        {
            "name": "Squat",
            "slug": "squat",
            "description": "Lower your hips from a standing position and then stand back up. A fundamental movement pattern for lower body strength and mobility.",
            "category": "full_leg",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 12,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/squat.gif",
            "safety_instructions": ["Keep weight in your heels", "Do not let knees buckle inward (valgus)", "Keep back straight and chest up"],
            "contraindications": ["Acute knee effusion", "Severe lower back strain"],
        },
        {
            "name": "Deep Squat",
            "slug": "deep-squat",
            "description": "Lower your hips below the knee line to achieve a deep squat position. Tests and improves full lower-body joint mobility and strength.",
            "category": "full_leg",
            "difficulty": "advanced",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 120.0,
            "estimated_duration_seconds": 180,
            "gif_url": "/static/exercises/deep-squat.gif",
            "safety_instructions": ["Maintain spinal alignment", "Go only as deep as pain permits", "Ensure heels stay on the ground"],
            "contraindications": ["Meniscal tears", "Severe patellofemoral arthritis"],
        },
        {
            "name": "CTK Squat",
            "slug": "ctk-squat",
            "description": "A specialized squat variation targeting specific depth and alignment checkpoints for core, thigh, and knee rehabilitation.",
            "category": "full_leg",
            "difficulty": "intermediate",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 150,
            "gif_url": "/static/exercises/ctk-squat.gif",
            "safety_instructions": ["Control movement speed", "Ensure knee-hip coordination", "Maintain upright posture"],
            "contraindications": ["Recent knee surgeries (< 8 weeks)", "Acute lower back pain"],
        },
        {
            "name": "Sit to Stand",
            "slug": "sit-to-stand",
            "description": "Rise from a chair to a standing position and sit back down, using minimal support. Essential for functional strength and independent mobility.",
            "category": "full_leg",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/sit-to-stand.gif",
            "safety_instructions": ["Use a sturdy chair that will not slide", "Push through heels to stand", "Lower back down with control"],
            "contraindications": ["Severe balance impairment without supervision"],
        },
        {
            "name": "Hip Abduction",
            "slug": "hip-abduction",
            "description": "Move the leg away from the midline of the body. Strengthens the hip abductors, crucial for lateral stability.",
            "category": "hip",
            "difficulty": "beginner",
            "target_joints": ["left_hip", "right_hip"],
            "target_reps": 15,
            "target_sets": 3,
            "target_rom_degrees": 45.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/hip-abduction.gif",
            "safety_instructions": ["Keep pelvis level throughout movement", "Do not rotate the trunk", "Move through pain-free range only"],
            "contraindications": ["Hip labral tear", "Acute hip bursitis"],
        },
        {
            "name": "Knee Bend",
            "slug": "knee-bend",
            "description": "Gently bend the knee, sliding the heel towards the buttocks (heel slide) or standing. Improves knee flexion range of motion.",
            "category": "knee",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee"],
            "target_reps": 15,
            "target_sets": 3,
            "target_rom_degrees": 120.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/knee-bend.gif",
            "safety_instructions": ["Perform slowly and with control", "Keep thigh firmly on seat or floor", "Do not force range beyond comfort"],
            "contraindications": ["ACL graft < 12 weeks post-op (open chain)"],
        },
    ]

    seeded = 0
    for ex_data in day1:
        await Exercise(**ex_data).insert()
        seeded += 1
    return seeded


@router.post("/seed", status_code=201, summary="Seed default exercises (admin only)")
async def seed_exercises(admin: User = Depends(get_current_admin)):
    """Initialize the database with default exercises. Removes any existing ones first."""
    seeded = await run_seeding()
    return {"message": f"Seeded {seeded} exercises", "total_in_db": 10}

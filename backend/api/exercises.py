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
    thumbnail_url: str | None
    demo_video_url: str | None
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
        thumbnail_url=getattr(e, "thumbnail_url", None),
        demo_video_url=getattr(e, "demo_video_url", None),
        safety_instructions=e.safety_instructions,
        contraindications=e.contraindications,
        is_active=e.is_active,
    )


# Fixed sort order for all 10 exercises
EXERCISE_SORT_ORDER = [
    "hip-abduction",
    "knee-bend",
    "straight-leg-raise",
    "inline-lunge",
    "hurdle-step",
    "side-lunge",
    "squat",
    "deep-squat",
    "ctk-squat",
    "sit-to-stand",
]


@router.get("/", response_model=List[ExerciseOut])
async def list_exercises(current_user: User = Depends(get_current_user)):
    exercises = await Exercise.find(Exercise.is_active == True).to_list()
    # Sort: according to EXERCISE_SORT_ORDER mapping, rest alphabetical
    sort_map = {slug: i for i, slug in enumerate(EXERCISE_SORT_ORDER)}
    exercises.sort(key=lambda ex: sort_map.get(ex.slug, 999))
    return [_to_out(e) for e in exercises]


@router.get("/{exercise_id}", response_model=ExerciseOut)
async def get_exercise(exercise_id: str, current_user: User = Depends(get_current_user)):
    from beanie import PydanticObjectId
    exercise = await Exercise.get(PydanticObjectId(exercise_id))
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return _to_out(exercise)


@router.post("/seed", status_code=201, summary="Seed Day-1 exercises (admin only)")
async def seed_exercises(admin: User = Depends(get_current_admin)):
    """Initialize the database with the 10 standard exercises. Skips/updates existing, deletes removed ones."""

    day1 = [
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
            "thumbnail_url": "/static/exercises/hip-abduction.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep pelvis level throughout movement",
                "Do not rotate the trunk",
                "Move through pain-free range only",
                "Hold a support if performing standing",
            ],
            "contraindications": [
                "Hip labral tear (confirm with physio)",
                "Acute hip bursitis",
            ],
        },
        {
            "name": "Knee Bend",
            "slug": "knee-bend",
            "description": "Stand with feet hip-width apart and slowly bend your knees, lowering your body as if sitting back into a chair. Return to standing. Strengthens quadriceps, hamstrings, and improves knee joint mobility.",
            "category": "knee",
            "difficulty": "beginner",
            "target_joints": ["left_knee", "right_knee", "left_hip", "right_hip"],
            "target_reps": 15,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 120,
            "gif_url": "/static/exercises/knee-bend.gif",
            "thumbnail_url": "/static/exercises/knee-bend.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep knees aligned over second toe",
                "Do not let knees extend past toes",
                "Maintain upright posture throughout",
                "Stop if sharp knee pain occurs",
                "Hold support if needed for balance",
            ],
            "contraindications": [
                "Acute knee inflammation",
                "Recent knee surgery < 4 weeks",
            ],
        },
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
            "thumbnail_url": "/static/exercises/straight-leg-raise.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep your lower back flat on the floor",
                "Do not arch your spine",
                "Lift slowly with a straight knee",
            ],
            "contraindications": [
                "Severe lower back pain",
                "Acute hip inflammation",
            ],
        },
        {
            "name": "Inline Lunge",
            "slug": "inline-lunge",
            "description": "Place one foot in front of the other in a straight line and lower your hips until both knees are bent at about 90 degrees. Improves balance, stability, and lower body strength.",
            "category": "full_leg",
            "difficulty": "intermediate",
            "target_joints": [
                "left_knee",
                "right_knee",
                "left_hip",
                "right_hip",
                "left_ankle",
                "right_ankle",
            ],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 90.0,
            "estimated_duration_seconds": 180,
            "gif_url": "/static/exercises/inline-lunge.gif",
            "thumbnail_url": "/static/exercises/inline-lunge.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep front knee aligned over front foot",
                "Ensure torso remains upright",
                "Perform near a wall for balance support if needed",
            ],
            "contraindications": [
                "Severe knee instability",
                "Patellofemoral pain flare-up",
            ],
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
            "thumbnail_url": "/static/exercises/hurdle-step.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Avoid excessive leaning or twisting of the trunk",
                "Raise knee as high as comfortable",
                "Step down softly",
            ],
            "contraindications": [
                "Severe hip osteoarthritis",
                "Uncompensated balance impairment",
            ],
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
            "thumbnail_url": "/static/exercises/side-lunge.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep knee of bending leg tracking over the toes",
                "Keep trailing leg completely straight",
                "Keep chest lifted",
            ],
            "contraindications": [
                "Adductor strain",
                "Lateral meniscus tear",
            ],
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
            "thumbnail_url": "/static/exercises/squat.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Keep weight in your heels",
                "Do not let knees buckle inward (valgus)",
                "Keep back straight and chest up",
            ],
            "contraindications": [
                "Acute knee effusion",
                "Severe lower back strain",
            ],
        },
        {
            "name": "Deep Squat",
            "slug": "deep-squat",
            "description": "Lower your hips below the knee line to achieve a deep squat position. Tests and improves full lower-body joint mobility and strength.",
            "category": "full_leg",
            "difficulty": "advanced",
            "target_joints": [
                "left_knee",
                "right_knee",
                "left_hip",
                "right_hip",
                "left_ankle",
                "right_ankle",
            ],
            "target_reps": 10,
            "target_sets": 3,
            "target_rom_degrees": 120.0,
            "estimated_duration_seconds": 180,
            "gif_url": "/static/exercises/deep-squat.gif",
            "thumbnail_url": "/static/exercises/deep-squat.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Maintain spinal alignment",
                "Go only as deep as pain permits",
                "Ensure heels stay on the ground",
            ],
            "contraindications": [
                "Meniscal tears",
                "Severe patellofemoral arthritis",
            ],
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
            "thumbnail_url": "/static/exercises/ctk-squat.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Control movement speed",
                "Ensure knee-hip coordination",
                "Maintain upright posture",
            ],
            "contraindications": [
                "Recent knee surgeries (< 8 weeks)",
                "Acute lower back pain",
            ],
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
            "thumbnail_url": "/static/exercises/sit-to-stand.png",
            "demo_video_url": None,
            "audio_guide_url": None,
            "safety_instructions": [
                "Use a sturdy chair that will not slide",
                "Push through heels to stand",
                "Lower back down with control",
            ],
            "contraindications": [
                "Severe balance impairment without supervision",
            ],
        },
    ]

    # Clean up obsolete exercises from the database
    target_slugs = [ex["slug"] for ex in day1]
    deleted = await Exercise.find({"slug": {"$nin": target_slugs}}).delete()

    seeded = 0
    for ex_data in day1:
        existing = await Exercise.find_one(Exercise.slug == ex_data["slug"])
        if not existing:
            await Exercise(**ex_data).insert()
            seeded += 1
        else:
            # Update existing exercises with current properties
            for key, val in ex_data.items():
                if key not in ("name", "slug"):
                    setattr(existing, key, val)
            existing.updated_at = datetime.utcnow()
            await existing.save()

    return {
        "message": f"Seeded {seeded} new exercises, updated existing, deleted {deleted.deleted_count if deleted else 0} obsolete",
        "total_in_db": len(day1),
    }

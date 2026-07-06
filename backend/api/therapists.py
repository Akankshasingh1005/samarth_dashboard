"""Therapists API."""
from fastapi import APIRouter, Depends, HTTPException
from models.therapist import Therapist
from models.user import User
from services.auth_service import get_current_user, get_current_therapist

router = APIRouter()


@router.get("/me")
async def get_my_therapist_profile(current_user: User = Depends(get_current_therapist)):
    therapist = await Therapist.find_one(Therapist.user_id == current_user.id)
    if not therapist:
        raise HTTPException(404, "Therapist profile not found")
    return {
        "id": str(therapist.id),
        "user_id": str(therapist.user_id),
        "license_number": therapist.license_number,
        "specialization": therapist.specialization,
        "clinic_name": therapist.clinic_name,
        "bio": therapist.bio,
        "patient_count": len(therapist.patient_ids),
    }

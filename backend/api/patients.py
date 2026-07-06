"""Patients API."""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from beanie import PydanticObjectId
from pydantic import BaseModel
from models.patient import Patient
from models.user import User
from services.auth_service import get_current_user, get_current_therapist

router = APIRouter()


@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    patient = await Patient.find_one(Patient.user_id == current_user.id)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    return {
        "id": str(patient.id),
        "user_id": str(patient.user_id),
        "therapist_id": str(patient.therapist_id) if patient.therapist_id else None,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "phone": patient.phone,
        "medical_history": patient.medical_history,
        "injury_type": patient.injury_type,
        "current_condition": patient.current_condition,
        "target_rom": patient.target_rom,
    }


@router.put("/me")
async def update_my_profile(updates: dict, current_user: User = Depends(get_current_user)):
    patient = await Patient.find_one(Patient.user_id == current_user.id)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    allowed = ["gender", "phone", "address", "medical_history", "injury_type", "current_condition"]
    for field in allowed:
        if field in updates:
            setattr(patient, field, updates[field])
    patient.updated_at = datetime.utcnow()
    await patient.save()
    return {"message": "Profile updated"}


@router.get("/", summary="List all patients (therapist/admin only)")
async def list_patients(current_user: User = Depends(get_current_therapist)):
    patients = await Patient.find_all().to_list()
    return [{"id": str(p.id), "user_id": str(p.user_id), "injury_type": p.injury_type} for p in patients]

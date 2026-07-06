"""Analytics API - MongoDB aggregation pipelines for patient progress."""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from beanie import PydanticObjectId
from database import get_db
from services.auth_service import get_current_user
from models.user import User

router = APIRouter()


@router.get("/patient/{patient_id}/summary")
async def patient_analytics_summary(patient_id: str, current_user: User = Depends(get_current_user)):
    """Overall patient analytics summary."""
    db = get_db()
    pid = PydanticObjectId(patient_id)
    from models.patient import Patient
    patient = await Patient.get(pid) or await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    pid = patient.id

    pipeline = [
        {"$match": {"patient_id": pid}},
        {"$group": {
            "_id": None,
            "total_sessions": {"$sum": 1},
            "completed_sessions": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "total_reps": {"$sum": "$total_reps"},
            "avg_left_rom": {"$avg": "$avg_left_rom"},
            "avg_right_rom": {"$avg": "$avg_right_rom"},
            "avg_symmetry": {"$avg": "$symmetry_score"},
            "avg_session_score": {"$avg": "$session_score"},
        }}
    ]
    result = await db["sessions"].aggregate(pipeline).to_list(1)
    if not result:
        return {
            "total_sessions": 0, "completed_sessions": 0, "total_reps": 0,
            "avg_left_rom": 0.0, "avg_right_rom": 0.0, "avg_symmetry": 0.0,
            "avg_session_score": 0.0, "completion_rate": 0.0
        }

    r = result[0]
    r.pop("_id", None)
    total = r.get("total_sessions", 1) or 1
    r["completion_rate"] = round((r.get("completed_sessions", 0) / total) * 100, 1)
    if r.get("avg_session_score") is not None:
        r["avg_session_score"] = round(r["avg_session_score"] * 100, 1)
    else:
        r["avg_session_score"] = 0.0
    return r


@router.get("/patient/{patient_id}/weekly")
async def weekly_progress(patient_id: str, weeks: int = 8, current_user: User = Depends(get_current_user)):
    """Weekly ROM, symmetry, and session count trends."""
    db = get_db()
    pid = PydanticObjectId(patient_id)
    from models.patient import Patient
    patient = await Patient.get(pid) or await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    pid = patient.id
    since = datetime.utcnow() - timedelta(weeks=weeks)

    pipeline = [
        {"$match": {"patient_id": pid, "start_time": {"$gte": since}, "status": "completed"}},
        {"$group": {
            "_id": {
                "year": {"$year": "$start_time"},
                "week": {"$week": "$start_time"},
            },
            "sessions": {"$sum": 1},
            "total_reps": {"$sum": "$total_reps"},
            "avg_left_rom": {"$avg": "$avg_left_rom"},
            "avg_right_rom": {"$avg": "$avg_right_rom"},
            "avg_symmetry": {"$avg": "$symmetry_score"},
            "avg_score": {"$avg": "$session_score"},
            "first_date": {"$min": "$start_time"},
        }},
        {"$sort": {"first_date": 1}},
    ]
    results = await db["sessions"].aggregate(pipeline).to_list(None)
    return [
        {
            "week": f"W{r['_id']['week']}",
            "year": r["_id"]["year"],
            "date": r["first_date"].isoformat() if r.get("first_date") else None,
            "sessions": r["sessions"],
            "total_reps": r["total_reps"],
            "avg_left_rom": round(r["avg_left_rom"] or 0, 1),
            "avg_right_rom": round(r["avg_right_rom"] or 0, 1),
            "avg_symmetry": round(r["avg_symmetry"] or 0, 1),
            "avg_score": round((r["avg_score"] or 0) * 100, 1),
        }
        for r in results
    ]


@router.get("/patient/{patient_id}/rom-trends")
async def rom_trends(patient_id: str, days: int = 30, current_user: User = Depends(get_current_user)):
    """Daily ROM trends for the last N days."""
    db = get_db()
    pid = PydanticObjectId(patient_id)
    from models.patient import Patient
    patient = await Patient.get(pid) or await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    pid = patient.id
    since = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"patient_id": pid, "start_time": {"$gte": since}, "status": "completed"}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$start_time"}},
            "avg_left_rom": {"$avg": "$avg_left_rom"},
            "avg_right_rom": {"$avg": "$avg_right_rom"},
            "avg_symmetry": {"$avg": "$symmetry_score"},
            "sessions": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = await db["sessions"].aggregate(pipeline).to_list(None)
    return [
        {
            "date": r["_id"],
            "avg_left_rom": round(r["avg_left_rom"] or 0, 1),
            "avg_right_rom": round(r["avg_right_rom"] or 0, 1),
            "avg_symmetry": round(r["avg_symmetry"] or 0, 1),
            "sessions": r["sessions"],
        }
        for r in results
    ]


@router.get("/patient/{patient_id}/exercise-breakdown")
async def exercise_breakdown(patient_id: str, current_user: User = Depends(get_current_user)):
    """Sessions per exercise type."""
    db = get_db()
    pid = PydanticObjectId(patient_id)
    from models.patient import Patient
    patient = await Patient.get(pid) or await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")
    pid = patient.id
    pipeline = [
        {"$match": {"patient_id": pid, "status": "completed"}},
        {"$group": {
            "_id": "$exercise_id",
            "count": {"$sum": 1},
            "avg_reps": {"$avg": "$total_reps"},
            "avg_rom": {"$avg": {"$avg": ["$avg_left_rom", "$avg_right_rom"]}},
        }},
        {"$lookup": {
            "from": "exercises",
            "localField": "_id",
            "foreignField": "_id",
            "as": "exercise",
        }},
        {"$unwind": {"path": "$exercise", "preserveNullAndEmptyArrays": True}},
    ]
    results = await db["sessions"].aggregate(pipeline).to_list(None)
    return [
        {
            "exercise_id": str(r["_id"]),
            "exercise_name": r.get("exercise", {}).get("name", "Unknown"),
            "session_count": r["count"],
            "avg_reps": round(r["avg_reps"] or 0, 1),
            "avg_rom": round(r["avg_rom"] or 0, 1),
        }
        for r in results
    ]


@router.get("/therapist/{therapist_id}/overview")
async def therapist_overview(therapist_id: str, current_user: User = Depends(get_current_user)):
    """All-patient overview for a therapist."""
    db = get_db()
    tid = PydanticObjectId(therapist_id)
    pipeline = [
        {"$match": {"therapist_id": tid}},
        {"$group": {
            "_id": "$patient_id",
            "total_sessions": {"$sum": 1},
            "last_session": {"$max": "$start_time"},
            "avg_symmetry": {"$avg": "$symmetry_score"},
            "avg_rom": {"$avg": {"$avg": ["$avg_left_rom", "$avg_right_rom"]}},
        }},
    ]
    results = await db["sessions"].aggregate(pipeline).to_list(None)
    return [
        {
            "patient_id": str(r["_id"]),
            "total_sessions": r["total_sessions"],
            "last_session": r["last_session"].isoformat() if r.get("last_session") else None,
            "avg_symmetry": round(r["avg_symmetry"] or 0, 1),
            "avg_rom": round(r["avg_rom"] or 0, 1),
        }
        for r in results
    ]

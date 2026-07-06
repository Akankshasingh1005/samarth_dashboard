"""Reports API - PDF generation with WeasyPrint + CSV export."""
import os
import csv
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from beanie import PydanticObjectId
from models.report import Report
from models.session import Session
from models.angle_data import AngleData
from models.user import User
from models.patient import Patient
from services.auth_service import get_current_user
from backend_config import settings

router = APIRouter()


@router.post("/generate")
async def generate_report(
    patient_id: str,
    report_type: str = "session",
    session_ids: list = None,
    current_user: User = Depends(get_current_user),
):
    pid = PydanticObjectId(patient_id)
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)

    # Resolve pid to Patient profile and User
    patient = await Patient.get(pid)
    if not patient:
        patient = await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")

    if session_ids:
        sids = [PydanticObjectId(s) for s in session_ids]
        sessions = await Session.find({"_id": {"$in": sids}}).to_list()
    else:
        sessions = await Session.find(
            Session.patient_id == patient.id, Session.status == "completed"
        ).sort(-Session.start_time).limit(10).to_list()

    if not sessions:
        raise HTTPException(404, "No completed sessions found for report")

    user = await User.get(patient.user_id)

    # Build CSV report
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"report_{patient_id}_{ts}.csv"
    csv_path = os.path.join(settings.REPORTS_DIR, csv_filename)

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Session ID", "Exercise", "Date", "Duration(s)", "Reps", "Avg Left ROM", "Avg Right ROM", "Symmetry %", "Session Score"])
        for s in sessions:
            if s.start_time:
                local_time = s.start_time.replace(tzinfo=timezone.utc).astimezone()
                date_str = local_time.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = "N/A"
                
            writer.writerow([
                str(s.id),
                str(s.exercise_id),
                date_str,
                round(s.duration_seconds or 0, 1),
                s.total_reps,
                round(s.avg_left_rom, 1),
                round(s.avg_right_rom, 1),
                round(s.symmetry_score, 1),
                round(s.session_score or 0, 2),
            ])

    report = Report(
        patient_id=patient.id,
        session_ids=[s.id for s in sessions],
        type=report_type,
        csv_url=f"/reports/download/{csv_filename}",
    )
    await report.insert()
    return {"report_id": str(report.id), "csv_url": report.csv_url, "sessions_included": len(sessions)}


@router.get("/download/{filename}")
async def download_report(filename: str, current_user: User = Depends(get_current_user)):
    file_path = os.path.join(settings.REPORTS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "Report file not found")
    return FileResponse(file_path, filename=filename, media_type="text/csv")


@router.get("/patient/{patient_id}")
async def list_patient_reports(patient_id: str, current_user: User = Depends(get_current_user)):
    pid = PydanticObjectId(patient_id)
    
    patient = await Patient.get(pid)
    if not patient:
        patient = await Patient.find_one(Patient.user_id == pid)
    if not patient:
        raise HTTPException(404, "Patient profile not found")

    reports = await Report.find(Report.patient_id == patient.id).sort(-Report.generated_at).to_list()
    return [
        {
            "id": str(r.id),
            "type": r.type,
            "csv_url": r.csv_url,
            "pdf_url": r.pdf_url,
            "sessions_count": len(r.session_ids),
            "generated_at": r.generated_at,
        }
        for r in reports
    ]

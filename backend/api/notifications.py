"""Notifications API."""
from fastapi import APIRouter, Depends, HTTPException
from beanie import PydanticObjectId
from models.notification import Notification
from models.user import User
from services.auth_service import get_current_user

router = APIRouter()


@router.get("/")
async def get_notifications(current_user: User = Depends(get_current_user), limit: int = 20):
    notes = await Notification.find(
        Notification.user_id == current_user.id
    ).sort(-Notification.created_at).limit(limit).to_list()
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "action_url": n.action_url,
            "created_at": n.created_at,
        }
        for n in notes
    ]


@router.get("/unread-count")
async def unread_count(current_user: User = Depends(get_current_user)):
    count = await Notification.find(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return {"unread": count}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: str, current_user: User = Depends(get_current_user)):
    note = await Notification.get(PydanticObjectId(notification_id))
    if not note:
        raise HTTPException(404, "Notification not found")
    note.is_read = True
    await note.save()
    return {"message": "Marked as read"}


@router.put("/mark-all-read")
async def mark_all_read(current_user: User = Depends(get_current_user)):
    notes = await Notification.find(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).to_list()
    for n in notes:
        n.is_read = True
        await n.save()
    return {"message": f"Marked {len(notes)} notifications as read"}

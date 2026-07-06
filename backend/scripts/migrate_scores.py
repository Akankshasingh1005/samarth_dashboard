import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from backend_config import settings
from database import connect_db, close_db
from models.session import Session
from models.angle_data import AngleData

def map_score_val(raw_score: float) -> float:
    raw_score = max(0.0, min(1.0, raw_score))
    if raw_score < 0.20:
        val = 0.45 + (raw_score / 0.20) * 0.05
    elif raw_score < 0.30:
        val = 0.55 + ((raw_score - 0.20) / 0.10) * 0.05
    elif raw_score < 0.45:
        val = 0.65 + ((raw_score - 0.30) / 0.15) * 0.10
    else:
        val = 0.76 + ((raw_score - 0.45) / 0.55) * 0.17
    return round(val, 2)

def invert_old_score(mapped_score: float) -> float:
    # Old mapping: mapped = 0.84 + raw * 0.08
    # raw = (mapped - 0.84) / 0.08
    raw = (mapped_score - 0.84) / 0.08
    return max(0.0, min(1.0, raw))

async def main():
    await connect_db()
    print("Database connected. Starting migration...")
    
    sessions = await Session.find(Session.status == "completed").to_list()
    print(f"Migrating {len(sessions)} completed sessions...")
    
    updated_count = 0
    for s in sessions:
        angle_data = await AngleData.find_one(AngleData.session_id == s.id)
        
        if not angle_data or not angle_data.ps2_rep_results:
            # If no detailed rep data, remap overall session score directly
            if s.session_score is not None:
                old_score = s.session_score
                if 0.84 <= old_score <= 0.92:
                    raw_score = invert_old_score(old_score)
                    new_score = map_score_val(raw_score)
                else:
                    new_score = map_score_val(old_score)
                
                s.session_score = new_score
                s.quality_score = new_score
                await s.save()
                print(f"Session {s.id} (No Reps): Updated overall={old_score} -> {new_score}")
                updated_count += 1
            continue
            
        old_overall = s.session_score
        new_rep_scores = []
        
        # Modify rep results in AngleData
        modified_reps = []
        for r in angle_data.ps2_rep_results:
            s_metric = r.get("session", {})
            old_rep_score = s_metric.get("session_score", 0.5)
            
            # Invert old score if in old mapped range
            if 0.84 <= old_rep_score <= 0.92:
                raw_rep_score = invert_old_score(old_rep_score)
            else:
                raw_rep_score = old_rep_score
            
            new_rep_score = map_score_val(raw_rep_score)
            s_metric["session_score"] = new_rep_score
            new_rep_scores.append(new_rep_score)
            modified_reps.append(r)
            
        if new_rep_scores:
            top_scores = sorted(new_rep_scores, reverse=True)[:10]
            new_overall = round(sum(top_scores) / len(top_scores), 2)
        else:
            new_overall = 0.0
            
        # Update documents
        angle_data.ps2_rep_results = modified_reps
        await angle_data.save()
        
        s.session_score = new_overall
        s.quality_score = new_overall
        await s.save()
        
        print(f"Session {s.id}: Updated overall={old_overall} -> {new_overall} | {len(new_rep_scores)} reps updated")
        updated_count += 1
            
    print(f"Migration completed successfully. Total updated sessions: {updated_count}")
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())

from typing import List, Optional
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from google.cloud.firestore import Client
from app.database.session import get_db
from app.auth.permissions import get_current_active_user
from app.models.models import User

router = APIRouter()
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    doc_metadata = {
        "id": file_id,
        "filename": file.filename,
        "safe_filename": safe_filename,
        "file_path": file_path,
        "file_size": len(content),
        "content_type": file.content_type,
        "uploader_id": current_user.id,
        "uploader_name": current_user.name,
        "uploaded_at": datetime.utcnow().isoformat()
    }
    
    db.collection('files').document(file_id).set(doc_metadata)
    
    return {
        "id": file_id,
        "filename": file.filename,
        "file_size": len(content),
        "url": f"/api/v1/files/download/{file_id}",
        "message": "File uploaded successfully"
    }

@router.get("")
def list_files(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    files_ref = db.collection('files')
    docs = list(files_ref.stream())
    return [doc.to_dict() for doc in docs]

@router.get("/download/{file_id}")
def download_file_info(
    file_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('files').document(file_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="File not found")
    return doc.to_dict()


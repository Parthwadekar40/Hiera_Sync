from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client
from typing import Optional
import uuid
import random
import string
from app.database.session import get_db
from app.schemas.schemas import DepartmentCreate, DepartmentResponse
from app.auth.permissions import get_current_active_user, get_current_user
from app.models.models import User, RoleEnum
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter()

def generate_invitation_code(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@router.post("", response_model=DepartmentResponse)
def create_department(
    dept_in: DepartmentCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    departments_ref = db.collection('departments')
    existing = list(departments_ref.stream())

    # Bootstrap case: an empty database has no active HOD, and only an active HOD
    # can approve anyone - so nobody could ever get the app started. The first
    # department may therefore be claimed by whoever registers it, even while that
    # account is still PENDING, and the claimer is activated by doing it.
    is_bootstrap = len(existing) == 0

    if not is_bootstrap:
        if current_user.status != "ACTIVE":
            raise HTTPException(
                status_code=403,
                detail="Your account is waiting for department approval before it can create one",
            )
        if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HOD]:
            raise HTTPException(status_code=403, detail="Only Admins or HODs can create departments")

        if any(dept.to_dict().get("hod_id") == current_user.id for dept in existing):
            raise HTTPException(status_code=400, detail="You already manage a department")

    # Generate unique code
    while True:
        code = generate_invitation_code()
        code_query = departments_ref.where(filter=FieldFilter('code', '==', code)).stream()
        if not list(code_query):
            break

    dept_id = str(uuid.uuid4())
    dept_data = {
        "id": dept_id,
        "name": dept_in.name,
        "code": code,
        "hod_id": current_user.id,
        "is_hod": dept_in.is_hod,
    }
    
    departments_ref.document(dept_id).set(dept_data)

    # Link the creator to the department they just made. This used to be guarded
    # by "if not current_user.department_id", but registration always writes a
    # placeholder ("AIML"), so the link never happened and /departments/me stayed
    # empty - the page reported success while the account pointed at nothing.
    user_patch = {"department_id": dept_id}
    if is_bootstrap:
        # The account that starts the system becomes its HOD: registration defaults
        # to FACULTY, and a FACULTY dashboard cannot approve anyone - which would
        # leave the department with a leader who has no leader tools.
        user_patch["status"] = "ACTIVE"
        if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HOD, RoleEnum.PRINCIPAL]:
            user_patch["role"] = RoleEnum.HOD.value
    db.collection('users').document(current_user.id).set(user_patch, merge=True)

    return {**dept_data, "bootstrap": is_bootstrap}

@router.get("/me", response_model=Optional[DepartmentResponse])
def get_my_department(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not current_user.department_id:
        # Check if they are an admin who created one but it didn't sync
        departments_ref = db.collection('departments')
        query = departments_ref.where(filter=FieldFilter('hod_id', '==', current_user.id)).stream()
        docs = list(query)
        if docs:
            return docs[0].to_dict()
        return None

    dept_doc = db.collection('departments').document(current_user.department_id).get()
    if not dept_doc.exists:
        return None

    return dept_doc.to_dict()

@router.put("/code", response_model=DepartmentResponse)
def regenerate_department_code(
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role not in [RoleEnum.ADMIN, RoleEnum.HOD]:
        raise HTTPException(status_code=403, detail="Only Admins or HODs can regenerate codes")

    departments_ref = db.collection('departments')
    query = departments_ref.where(filter=FieldFilter('hod_id', '==', current_user.id)).stream()
    docs = list(query)
    
    if not docs:
        raise HTTPException(status_code=404, detail="Department not found")
        
    dept_doc = docs[0]
    dept_data = dept_doc.to_dict()

    while True:
        new_code = generate_invitation_code()
        code_query = departments_ref.where(filter=FieldFilter('code', '==', new_code)).stream()
        if not list(code_query):
            break

    dept_data['code'] = new_code
    departments_ref.document(dept_data['id']).update({"code": new_code})
    
    return dept_data

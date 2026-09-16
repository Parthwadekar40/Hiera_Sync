from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from fastapi.security import OAuth2PasswordRequestForm
from app.database.session import get_db
from app.schemas.schemas import (
    UserCreate, UserResponse, LoginRequest, LoginResponse,
    EmployeeResponse, EmployeeCreate, EmployeeUpdate, ForgotPasswordRequest
)
from app.models.models import User, RoleEnum
from app.auth.password import get_password_hash, verify_password
from app.auth.jwt import create_access_token
from app.auth.lookup import find_user_by_email, normalize_email, user_exists
from app.auth.permissions import get_current_active_user, get_current_user, check_role
from datetime import timedelta
from app.config.settings import settings
import uuid

import firebase_admin
from firebase_admin import auth as firebase_auth
from app.database import session as db_session
from app.utils.logging import logger
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter()


def _demo_mode() -> bool:
    """True while running on the in-memory database (no Firebase credentials).

    Firebase Auth is the identity provider in production, but it is unavailable
    without a service-account file. In demo mode the local password hash in the
    users collection is the only credential, so accounts are minted with a
    synthetic id and activated straight away - enough to exercise the workflow.
    """
    return db_session.is_memory_db()

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Client = Depends(get_db)):
    users_ref = db.collection('users')
    # Stored lowercased so that the address can be typed back in any case later.
    email = normalize_email(user_in.email)
    if user_exists(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    if _demo_mode():
        new_id = f"demo_{uuid.uuid4().hex[:12]}"
        status_value = "ACTIVE"
        logger.warning(f"Demo mode: created account {new_id} without Firebase Auth.")
    else:
        try:
            fb_user = firebase_auth.create_user(
                email=user_in.email,
                password=user_in.password,
                display_name=user_in.name
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        new_id = fb_user.uid
        status_value = "PENDING"

    hashed_password = get_password_hash(user_in.password)
    
    user_data = {
        "id": new_id,
        "name": user_in.name,
        "email": email,
        "hashed_password": hashed_password,
        "role": user_in.role.value if hasattr(user_in.role, 'value') else str(user_in.role),
        "department_id": user_in.department_id or "AIML",
        "designation": user_in.designation or "Assistant Professor",
        "area_of_interest": user_in.area_of_interest,
        "joining_date": user_in.joining_date or "Not Available",
        "association": user_in.association or "Regular",
        "avatar_url": user_in.avatar_url,
        "status": status_value
    }

    users_ref.document(new_id).set(user_data)
    return user_data

@router.post("/login", response_model=LoginResponse)
def login(login_in: LoginRequest, db: Client = Depends(get_db)):
    users_ref = db.collection('users')
    user_doc = find_user_by_email(db, login_in.email)

    if not user_doc:
        logger.info(f"Login failed: no profile in the 'users' collection for {login_in.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stored_hash = user_doc.get("hashed_password") or ""
    if not stored_hash:
        # The profile exists in Firestore but carries no password: typical for an
        # account created in the Firebase console, which never touches this
        # collection. Login only compares the stored bcrypt hash, so say so.
        logger.warning(
            f"Login for {login_in.email}: profile has no hashed_password (created outside /auth/register?)"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account has no password on file in the department database. "
                   "Sign up on the register page (or ask the HOD to re-create it) so the "
                   "profile and the password are stored together.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        password_ok = verify_password(login_in.password, stored_hash)
    except ValueError:
        # bcrypt raises instead of returning False when the stored value is not a
        # hash at all (plain text pasted into the console) - that was a 500.
        logger.warning(f"Login for {login_in.email}: stored password hash is malformed")
        password_ok = False

    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_doc["email"]}, expires_delta=access_token_expires
    )

    user_id = user_doc.get("id")
    if user_doc.get("status") == "PENDING":
        try:
            requests_ref = db.collection('join_requests')
            req_query = requests_ref.where(filter=FieldFilter('faculty_id', '==', user_id)).where(filter=FieldFilter('status', '==', 'Approved')).stream()
            approved_reqs = list(req_query)
            if approved_reqs:
                req_data = approved_reqs[0].to_dict()
                dept_id = req_data.get('department_id')
                user_doc["status"] = "ACTIVE"
                if dept_id:
                    user_doc["department_id"] = dept_id
                users_ref.document(user_id).update({
                    "status": "ACTIVE",
                    "department_id": user_doc["department_id"]
                })
        except Exception as e:
            print("Login auto-sync error:", e)
    
    user_response = UserResponse(
        id=user_id,
        name=user_doc.get("name", ""),
        email=user_doc.get("email", ""),
        role=user_doc.get("role", RoleEnum.FACULTY),
        department_id=user_doc.get("department_id", "AIML"),
        designation=user_doc.get("designation", "Assistant Professor"),
        area_of_interest=user_doc.get("area_of_interest"),
        joining_date=user_doc.get("joining_date", "Not Available"),
        association=user_doc.get("association", "Regular"),
        avatar_url=user_doc.get("avatar_url"),
        status=user_doc.get("status", "ACTIVE")
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    if _demo_mode():
        return {
            "message": "Password resets are unavailable while the app runs on the in-memory "
                       "demo database — email a link once Firebase credentials are configured.",
            "link": None,
        }
    try:
        link = firebase_auth.generate_password_reset_link(req.email)
        return {"message": "Password reset email generated", "link": link}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Employee / Faculty Management Endpoints
@router.get("/employees", response_model=List[EmployeeResponse])
def list_employees(
    search: Optional[str] = Query(None, alias="q"),
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    users_ref = db.collection('users')
    docs = users_ref.stream()
    employees = []
    for doc in docs:
        data = doc.to_dict()
        if search:
            q = search.lower()
            name_match = q in data.get("name", "").lower()
            area_match = q in data.get("area_of_interest", "").lower() if data.get("area_of_interest") else False
            desig_match = q in data.get("designation", "").lower() if data.get("designation") else False
            if not (name_match or area_match or desig_match):
                continue
        employees.append(data)
    return employees

@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: str,
    db: Client = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc_ref = db.collection('users').document(employee_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Employee not found")
    return doc.to_dict()

@router.post("/employees", response_model=EmployeeResponse)
def create_employee(
    employee_in: EmployeeCreate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    # Normalised, or the profile can never be signed in to from the login form.
    email = normalize_email(employee_in.email)
    if user_exists(db, email):
        raise HTTPException(status_code=400, detail="Email already exists")

    pwd = employee_in.password or "Sbjit@123"
    if _demo_mode():
        new_id = f"demo_{uuid.uuid4().hex[:12]}"
    else:
        try:
            fb_user = firebase_auth.create_user(
                email=email,
                password=pwd,
                display_name=employee_in.name
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        new_id = fb_user.uid

    hashed_password = get_password_hash(pwd)
    data = {
        "id": new_id,
        "name": employee_in.name,
        "email": email,
        "hashed_password": hashed_password,
        "role": employee_in.role.value if hasattr(employee_in.role, 'value') else str(employee_in.role),
        "department_id": employee_in.department_id or "AIML",
        "designation": employee_in.designation or "Assistant Professor",
        "area_of_interest": employee_in.area_of_interest,
        "joining_date": employee_in.joining_date or "Not Available",
        "association": employee_in.association or "Regular",
        "avatar_url": employee_in.avatar_url,
        "status": "ACTIVE"
    }
    db.collection('users').document(new_id).set(data)
    return data

@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: str,
    employee_update: EmployeeUpdate,
    db: Client = Depends(get_db),
    current_user: User = Depends(check_role([RoleEnum.ADMIN, RoleEnum.HOD]))
):
    doc_ref = db.collection('users').document(employee_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = {k: v for k, v in employee_update.dict(exclude_unset=True).items() if v is not None}
    if "role" in update_data and hasattr(update_data["role"], 'value'):
        update_data["role"] = update_data["role"].value
        
    doc_ref.update(update_data)
    updated_doc = doc_ref.get().to_dict()
    return updated_doc


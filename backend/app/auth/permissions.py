from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from app.auth.jwt import verify_token
from app.auth.lookup import find_user_by_email
from app.database.session import get_db
from app.models.models import User, RoleEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Client = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_token(token, credentials_exception)
    
    user_dict = find_user_by_email(db, token_data.email)

    if not user_dict:
        raise credentials_exception

    user_id = user_dict.get("id")

    # Auto-sync/heal: If user status is PENDING, check if their join request was Approved
    if user_dict.get("status") == "PENDING":
        try:
            requests_ref = db.collection('join_requests')
            req_query = requests_ref.where(filter=FieldFilter('faculty_id', '==', user_id)).where(filter=FieldFilter('status', '==', 'Approved')).stream()
            approved_reqs = list(req_query)
            if approved_reqs:
                req_data = approved_reqs[0].to_dict()
                dept_id = req_data.get('department_id')
                user_dict["status"] = "ACTIVE"
                if dept_id:
                    user_dict["department_id"] = dept_id
                # Persist active status back to users document in Firestore
                db.collection('users').document(user_id).update({
                    "status": "ACTIVE",
                    "department_id": user_dict["department_id"]
                })
        except Exception as e:
            print("Auto-sync join request check error:", e)

    return User(**user_dict)

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def check_role(required_roles: list[RoleEnum]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker

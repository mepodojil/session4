"""
Slalom Capabilities Management System API

A FastAPI application that enables Slalom consultants to register their
capabilities and manage consulting expertise across the organization.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Slalom Capabilities Management API",
              description="API for managing consulting capabilities and consultant expertise")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

PRACTICE_LEADS_FILE = current_dir / "practice_leads.json"


def _load_practice_leads():
    if not PRACTICE_LEADS_FILE.exists():
        return {}

    with open(PRACTICE_LEADS_FILE, "r", encoding="utf-8") as file:
        raw_data = json.load(file)

    return {lead["username"]: lead for lead in raw_data.get("practice_leads", [])}


practice_leads = _load_practice_leads()
sessions = {}
pending_requests = {}
audit_log = []
next_pending_request_id = 1

# In-memory capabilities database
capabilities = {
    "Cloud Architecture": {
        "description": "Design and implement scalable cloud solutions using AWS, Azure, and GCP",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["AWS Solutions Architect", "Azure Architect Expert"],
        "industry_verticals": ["Healthcare", "Financial Services", "Retail"],
        "capacity": 40,  # hours per week available across team
        "consultants": ["alice.smith@slalom.com", "bob.johnson@slalom.com"]
    },
    "Data Analytics": {
        "description": "Advanced data analysis, visualization, and machine learning solutions",
        "practice_area": "Technology", 
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Tableau Desktop Specialist", "Power BI Expert", "Google Analytics"],
        "industry_verticals": ["Retail", "Healthcare", "Manufacturing"],
        "capacity": 35,
        "consultants": ["emma.davis@slalom.com", "sophia.wilson@slalom.com"]
    },
    "DevOps Engineering": {
        "description": "CI/CD pipeline design, infrastructure automation, and containerization",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"], 
        "certifications": ["Docker Certified Associate", "Kubernetes Admin", "Jenkins Certified"],
        "industry_verticals": ["Technology", "Financial Services"],
        "capacity": 30,
        "consultants": ["john.brown@slalom.com", "olivia.taylor@slalom.com"]
    },
    "Digital Strategy": {
        "description": "Digital transformation planning and strategic technology roadmaps",
        "practice_area": "Strategy",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Digital Transformation Certificate", "Agile Certified Practitioner"],
        "industry_verticals": ["Healthcare", "Financial Services", "Government"],
        "capacity": 25,
        "consultants": ["liam.anderson@slalom.com", "noah.martinez@slalom.com"]
    },
    "Change Management": {
        "description": "Organizational change leadership and adoption strategies",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Prosci Certified", "Lean Six Sigma Black Belt"],
        "industry_verticals": ["Healthcare", "Manufacturing", "Government"],
        "capacity": 20,
        "consultants": ["ava.garcia@slalom.com", "mia.rodriguez@slalom.com"]
    },
    "UX/UI Design": {
        "description": "User experience design and digital product innovation",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Adobe Certified Expert", "Google UX Design Certificate"],
        "industry_verticals": ["Retail", "Healthcare", "Technology"],
        "capacity": 30,
        "consultants": ["amelia.lee@slalom.com", "harper.white@slalom.com"]
    },
    "Cybersecurity": {
        "description": "Information security strategy, risk assessment, and compliance",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["CISSP", "CISM", "CompTIA Security+"],
        "industry_verticals": ["Financial Services", "Healthcare", "Government"],
        "capacity": 25,
        "consultants": ["ella.clark@slalom.com", "scarlett.lewis@slalom.com"]
    },
    "Business Intelligence": {
        "description": "Enterprise reporting, data warehousing, and business analytics",
        "practice_area": "Technology",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Microsoft BI Certification", "Qlik Sense Certified"],
        "industry_verticals": ["Retail", "Manufacturing", "Financial Services"],
        "capacity": 35,
        "consultants": ["james.walker@slalom.com", "benjamin.hall@slalom.com"]
    },
    "Agile Coaching": {
        "description": "Agile transformation and team coaching for scaled delivery",
        "practice_area": "Operations",
        "skill_levels": ["Emerging", "Proficient", "Advanced", "Expert"],
        "certifications": ["Certified Scrum Master", "SAFe Agilist", "ICAgile Certified"],
        "industry_verticals": ["Technology", "Financial Services", "Healthcare"],
        "capacity": 20,
        "consultants": ["charlotte.young@slalom.com", "henry.king@slalom.com"]
    }
}


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()


def validate_practice_lead_credentials(username: str, password: str):
    lead = practice_leads.get(username)
    if not lead:
        return None

    candidate_hash = hash_password(password, lead["salt"])
    if not secrets.compare_digest(candidate_hash, lead["password_hash"]):
        return None

    return lead


def create_session(lead):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
    sessions[token] = {
        "username": lead["username"],
        "role": lead["role"],
        "practice_areas": lead.get("practice_areas", []),
        "expires_at": expires_at,
    }
    return token, sessions[token]


def get_session(x_auth_token: str | None):
    if not x_auth_token:
        return None

    session = sessions.get(x_auth_token)
    if not session:
        return None

    if datetime.now(timezone.utc) >= session["expires_at"]:
        sessions.pop(x_auth_token, None)
        return None

    return session


def require_practice_lead_session(x_auth_token: str | None):
    session = get_session(x_auth_token)
    if not session or session.get("role") != "practice_lead":
        raise HTTPException(status_code=403, detail="Practice lead authentication required")
    return session


def add_audit_event(action: str, actor: str, capability_name: str, target_email: str, details: str):
    audit_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "capability": capability_name,
        "target_email": target_email,
        "details": details,
    })


def get_pending_for_capability(capability_name: str):
    return pending_requests.get(capability_name, [])


def find_pending_request(capability_name: str, request_id: int):
    requests = get_pending_for_capability(capability_name)
    for request in requests:
        if request["id"] == request_id:
            return request
    return None


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/capabilities")
def get_capabilities():
    response = {}
    for name, details in capabilities.items():
        response[name] = {
            **details,
            "pending_requests": get_pending_for_capability(name),
        }
    return response


@app.post("/auth/login")
def login(username: str, password: str):
    lead = validate_practice_lead_credentials(username, password)
    if not lead:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, session = create_session(lead)
    return {
        "message": "Logged in successfully",
        "token": token,
        "user": {
            "username": session["username"],
            "role": session["role"],
            "practice_areas": session["practice_areas"],
            "expires_at": session["expires_at"].isoformat(),
        },
    }


@app.post("/auth/logout")
def logout(x_auth_token: str | None = Header(default=None, alias="X-Auth-Token")):
    if x_auth_token:
        sessions.pop(x_auth_token, None)
    return {"message": "Logged out"}


@app.get("/auth/me")
def auth_me(x_auth_token: str | None = Header(default=None, alias="X-Auth-Token")):
    session = get_session(x_auth_token)
    if not session:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": {
            "username": session["username"],
            "role": session["role"],
            "practice_areas": session["practice_areas"],
            "expires_at": session["expires_at"].isoformat(),
        },
    }


@app.post("/capabilities/{capability_name}/register")
def register_for_capability(
    capability_name: str,
    email: str,
    requester_email: str | None = None,
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
):
    """Register a consultant for a capability or create a pending request."""
    global next_pending_request_id

    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is not already registered
    if email in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is already registered for this capability"
        )

    session = get_session(x_auth_token)
    if session and session.get("role") == "practice_lead":
        capability["consultants"].append(email)
        add_audit_event(
            action="register",
            actor=session["username"],
            capability_name=capability_name,
            target_email=email,
            details="Practice lead directly registered consultant",
        )
        return {"message": f"Registered {email} for {capability_name}"}

    requests = pending_requests.setdefault(capability_name, [])
    for request in requests:
        if request["email"] == email:
            raise HTTPException(
                status_code=400,
                detail="A pending registration request already exists for this consultant"
            )

    requested_by = requester_email or email
    pending_request = {
        "id": next_pending_request_id,
        "email": email,
        "requested_by": requested_by,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    next_pending_request_id += 1
    requests.append(pending_request)
    add_audit_event(
        action="request_registration",
        actor=requested_by,
        capability_name=capability_name,
        target_email=email,
        details="Consultant requested registration pending practice lead approval",
    )

    return {
        "message": f"Registration request submitted for {email} in {capability_name}",
        "request": pending_request,
    }


@app.post("/capabilities/{capability_name}/approve")
def approve_registration_request(
    capability_name: str,
    request_id: int,
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
):
    """Approve a pending consultant registration request."""
    session = require_practice_lead_session(x_auth_token)

    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    request = find_pending_request(capability_name, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Pending request not found")

    consultant_email = request["email"]
    capability = capabilities[capability_name]
    if consultant_email not in capability["consultants"]:
        capability["consultants"].append(consultant_email)

    pending_requests[capability_name] = [
        item for item in get_pending_for_capability(capability_name) if item["id"] != request_id
    ]
    add_audit_event(
        action="approve_registration",
        actor=session["username"],
        capability_name=capability_name,
        target_email=consultant_email,
        details=f"Approved request #{request_id}",
    )

    return {
        "message": f"Approved registration for {consultant_email} in {capability_name}",
        "request_id": request_id,
    }


@app.post("/capabilities/{capability_name}/reject")
def reject_registration_request(
    capability_name: str,
    request_id: int,
    reason: str | None = None,
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
):
    """Reject a pending consultant registration request."""
    session = require_practice_lead_session(x_auth_token)

    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    request = find_pending_request(capability_name, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Pending request not found")

    consultant_email = request["email"]
    pending_requests[capability_name] = [
        item for item in get_pending_for_capability(capability_name) if item["id"] != request_id
    ]
    add_audit_event(
        action="reject_registration",
        actor=session["username"],
        capability_name=capability_name,
        target_email=consultant_email,
        details=f"Rejected request #{request_id}. Reason: {reason or 'Not provided'}",
    )

    return {
        "message": f"Rejected registration request for {consultant_email}",
        "request_id": request_id,
        "reason": reason,
    }


@app.delete("/capabilities/{capability_name}/unregister")
def unregister_from_capability(
    capability_name: str,
    email: str,
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
):
    """Unregister a consultant from a capability (practice lead only)."""
    session = require_practice_lead_session(x_auth_token)

    # Validate capability exists
    if capability_name not in capabilities:
        raise HTTPException(status_code=404, detail="Capability not found")

    # Get the specific capability
    capability = capabilities[capability_name]

    # Validate consultant is registered
    if email not in capability["consultants"]:
        raise HTTPException(
            status_code=400,
            detail="Consultant is not registered for this capability"
        )

    # Remove consultant
    capability["consultants"].remove(email)
    add_audit_event(
        action="unregister",
        actor=session["username"],
        capability_name=capability_name,
        target_email=email,
        details="Practice lead removed consultant from capability",
    )
    return {"message": f"Unregistered {email} from {capability_name}"}


@app.get("/audit-log")
def get_audit_log(x_auth_token: str | None = Header(default=None, alias="X-Auth-Token")):
    require_practice_lead_session(x_auth_token)
    return audit_log

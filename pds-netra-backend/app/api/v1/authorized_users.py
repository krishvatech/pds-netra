"""
Authorized Users endpoints for PDS Netra backend.

Provides CRUD operations for managing authorized users who can access
godown facilities. Includes sync functionality with edge known_faces.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
import shutil
import os
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.db import get_db
from ...models.authorized_user import AuthorizedUser
from ...models.godown import Godown
from ...schemas.authorized_user import (
    AuthorizedUserCreate,
    AuthorizedUserUpdate,
    AuthorizedUserResponse,
)


router = APIRouter(prefix="/api/v1/authorized-users", tags=["authorized-users"])


@router.get("", response_model=List[AuthorizedUserResponse])
def list_authorized_users(
    godown_id: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> List[AuthorizedUser]:
    """List all authorized users with optional filters."""
    query = db.query(AuthorizedUser)
    
    if godown_id:
        query = query.filter(AuthorizedUser.godown_id == godown_id)
    if role:
        query = query.filter(AuthorizedUser.role == role)
    if is_active is not None:
        query = query.filter(AuthorizedUser.is_active == is_active)
    
    return query.order_by(AuthorizedUser.name.asc()).all()


@router.get("/{person_id}", response_model=AuthorizedUserResponse)
def get_authorized_user(person_id: str, db: Session = Depends(get_db)) -> AuthorizedUser:
    """Get details of a specific authorized user."""
    user = db.get(AuthorizedUser, person_id)
    if not user:
        raise HTTPException(status_code=404, detail="Authorized user not found")
    return user


@router.post("", status_code=201, response_model=AuthorizedUserResponse)
def create_authorized_user(
    req: AuthorizedUserCreate,
    db: Session = Depends(get_db),
) -> AuthorizedUser:
    """Create a new authorized user."""
    person_id = req.person_id.strip()
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id cannot be empty")
    
    # Check if user already exists
    existing = db.get(AuthorizedUser, person_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Authorized user {person_id} already exists"
        )
    
    # Validate godown_id if provided
    if req.godown_id:
        godown = db.get(Godown, req.godown_id)
        if not godown:
            raise HTTPException(
                status_code=404,
                detail=f"Godown {req.godown_id} not found"
            )
    
    # Create new user
    new_user = AuthorizedUser(
        person_id=person_id,
        name=req.name,
        role=req.role,
        godown_id=req.godown_id,
        is_active=req.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Sync create to edge config if exists
    try:
        edge_path = _get_edge_config_path()
        if edge_path.exists():
            with open(edge_path, "r") as f:
                known_faces = json.load(f)
            
            # Check if already in json (shouldn't be, but robust check)
            exists_in_json = any(f.get("person_id") == person_id for f in known_faces)
            
            if not exists_in_json:
                new_entry = {
                    "person_id": person_id,
                    "name": req.name,
                    "role": req.role,
                    "godown_id": req.godown_id,
                    "embedding": []  # Placeholder, needs enrollment
                }
                known_faces.append(new_entry)
                with open(edge_path, "w") as f:
                    json.dump(known_faces, f, indent=2)
    except Exception:
        pass
    
    return new_user


def _get_edge_config_path() -> Path:
    return Path(__file__).resolve().parents[4] / "pds-netra-edge" / "config" / "known_faces.json"


@router.put("/{person_id}", response_model=AuthorizedUserResponse)
def update_authorized_user(
    person_id: str,
    req: AuthorizedUserUpdate,
    db: Session = Depends(get_db),
) -> AuthorizedUser:
    """Update an existing authorized user."""
    user = db.get(AuthorizedUser, person_id)
    if not user:
        raise HTTPException(status_code=404, detail="Authorized user not found")
    
    # Validate godown_id if being updated
    if req.godown_id is not None:
        if req.godown_id:  # Not empty string
            godown = db.get(Godown, req.godown_id)
            if not godown:
                raise HTTPException(
                    status_code=404,
                    detail=f"Godown {req.godown_id} not found"
                )
        user.godown_id = req.godown_id if req.godown_id else None
    
    if req.name is not None:
        user.name = req.name
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    
    db.commit()
    db.refresh(user)

    # Sync update to edge config if exits
    try:
        edge_path = _get_edge_config_path()
        if edge_path.exists():
            with open(edge_path, "r") as f:
                known_faces = json.load(f)
            
            changed = False
            for face in known_faces:
                if face.get("person_id") == person_id:
                    if req.name is not None:
                        face["name"] = req.name
                    if req.role is not None:
                        face["role"] = req.role
                    # Update godown_id in JSON
                    if req.godown_id is not None:
                        face["godown_id"] = req.godown_id if req.godown_id else None
                    changed = True
                    break
            
            if changed:
                with open(edge_path, "w") as f:
                    json.dump(known_faces, f, indent=2)
    except Exception:
        pass
    
    return user


@router.delete("/{person_id}")
def delete_authorized_user(person_id: str, db: Session = Depends(get_db)) -> dict:
    """Delete an authorized user."""
    user = db.get(AuthorizedUser, person_id)
    if not user:
        raise HTTPException(status_code=404, detail="Authorized user not found")
    
    db.delete(user)
    db.commit()

    # Remove from edge config
    try:
        edge_path = _get_edge_config_path()
        if edge_path.exists():
            with open(edge_path, "r") as f:
                known_faces = json.load(f)
            
            initial_count = len(known_faces)
            known_faces = [f for f in known_faces if f.get("person_id") != person_id]
            
            if len(known_faces) < initial_count:
                with open(edge_path, "w") as f:
                    json.dump(known_faces, f, indent=2)
    except Exception:
        pass
    
    return {
        "status": "success",
        "message": f"Authorized user {person_id} deleted successfully"
    }


@router.get("/sync/from-edge/{godown_id}")
def sync_from_edge(godown_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Import authorized users from edge known_faces.json for a specific godown.
    This reads the edge config and creates/updates users in the database.
    """
    # Validate godown exists
    godown = db.get(Godown, godown_id)
    if not godown:
        raise HTTPException(status_code=404, detail=f"Godown {godown_id} not found")
    
    # Find the edge config file
    # Assuming edge config is at: pds-netra-edge/config/known_faces.json
    edge_config_path = _get_edge_config_path()
    
    if not edge_config_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Edge config file not found at {edge_config_path}"
        )
    
    try:
        with open(edge_config_path, "r") as f:
            known_faces = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read edge config: {str(e)}"
        )
    
    # Track statistics
    created = 0
    updated = 0
    deleted = 0
    
    # Get all person_ids from the edge config VALID FOR THIS GODOWN
    edge_person_ids = set()
    valid_faces_for_this_godown = []
    
    for face_data in known_faces:
        if not face_data.get("person_id") or not face_data.get("name"):
            continue
            
        # FILTERING LOGIC:
        # 1. If JSON has 'godown_id', strict match.
        # 2. If JSON has NO 'godown_id', assume global/unassigned -> optionally allow or strict skip?
        #    Decision: To solve the user's issue ("show surat godown's people in GDN_002"), 
        #    we MUST enforce segregation.
        #    If godown_id is MISSING, we'll tentatively allow it ONLY if the user isn't already assigned to another godown in DB?
        #    NO, cleaner logic: If NO `godown_id` in JSON, we can't be sure.
        #    However, to handle migration, maybe we only associate if it matches.
        
        json_godown_id = face_data.get("godown_id")
        
        if json_godown_id:
            # Strict filtering: if assigned to specific godown, only sync there
            if json_godown_id == godown_id:
                edge_person_ids.add(face_data["person_id"])
                valid_faces_for_this_godown.append(face_data)
        else:
            # Legacy/Unassigned entry.
            # Behavior: Check if user exists in DB and belongs to THIS godown.
            # If yes, keep them. If they belong to ANOTHER godown, skip.
            # If new, maybe add them? But this causes the "duplicate" issue in lists.
            # The user wants segregation. 
            # Strategy: If Unassigned, we treat it as Global/Available. 
            # BUT, to fix the specific complaint, we prefer explicit ownership.
            # Let's import them, but if the user has manually moved them to another godown in the dashboard (and we wrote back),
            # then json_godown_id would exist.
            # So, empty json_godown_id means "Legacy/All". 
            # We will include them for now to ensure we don't delete everyone before migration.
            edge_person_ids.add(face_data["person_id"])
            valid_faces_for_this_godown.append(face_data)
            
    # Get all existing users for this godown
    existing_users = db.query(AuthorizedUser).filter(AuthorizedUser.godown_id == godown_id).all()
    existing_map = {u.person_id: u for u in existing_users}
    
    # Handle updates and creations
    for face_data in valid_faces_for_this_godown:
        person_id = face_data.get("person_id")
        name = face_data.get("name")
        role = face_data.get("role")
        
        if person_id in existing_map:
            # Update existing user
            user = existing_map[person_id]
            user.name = name
            user.role = role
            # godown_id is already correct per filter
            updated += 1
        else:
            # Create new user
            # Check if user exists but under a different godown
            existing = db.get(AuthorizedUser, person_id)
            if existing:
                # User exists in DB but not linked to this godown in our query
                # If the JSON record specifically says THIS godown, we should move them.
                if face_data.get("godown_id") == godown_id:
                    existing.name = name
                    existing.role = role
                    existing.godown_id = godown_id
                    updated += 1
                # Else: They belong to another godown, and JSON didn't force them here. Do nothing.
            else:
                # Brand new user
                new_user = AuthorizedUser(
                    person_id=person_id,
                    name=name,
                    role=role,
                    godown_id=godown_id,
                    is_active=True,
                )
                db.add(new_user)
                created += 1
                
    # Handle deletions (users in DB for this godown but not in (valid) edge config)
    for person_id, user in existing_map.items():
        if person_id not in edge_person_ids:
            db.delete(user)
            deleted += 1
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Synced from edge config",
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "total": created + updated
    }


@router.post("/register-with-face", status_code=201, response_model=AuthorizedUserResponse)
async def register_authorized_user_with_face(
    person_id: str = Form(...),
    name: str = Form(...),
    role: str = Form(None),
    godown_id: str = Form(None),
    is_active: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AuthorizedUser:
    """
    Create a new authorized user and generate face embedding from uploaded photo.
    Updates the edge configuration file with the new face.
    """
    import sys
    import shutil
    import uuid
    
    person_id = person_id.strip()
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id cannot be empty")
        
    # Check if user already exists
    existing = db.get(AuthorizedUser, person_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Authorized user {person_id} already exists"
        )
        
    # Validate godown_id if provided
    if godown_id:
        godown = db.get(Godown, godown_id)
        if not godown:
            raise HTTPException(
                status_code=404,
                detail=f"Godown {godown_id} not found"
            )

    # Save uploaded file temporarily
    temp_dir = Path("/tmp/pds-faces")
    temp_dir.mkdir(exist_ok=True)
    ext = Path(file.filename).suffix or ".jpg"
    temp_file_path = temp_dir / f"{person_id}_{uuid.uuid4()}{ext}"
    
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Dynamically import edge tools to compute embedding
        # We need the path to pds-netra-edge
        edge_path = Path(__file__).resolve().parents[4] / "pds-netra-edge"
        if str(edge_path) not in sys.path:
            sys.path.append(str(edge_path))
            
        try:
            from tools.generate_face_embedding import compute_embedding, load_known_faces, upsert_person, save_known_faces
        except ImportError as e:
             raise HTTPException(
                status_code=500,
                detail=f"Failed to import face recognition tools: {str(e)}. Ensure prerequisites are met."
            )

        try:
            # Compute embedding
            embedding = compute_embedding(str(temp_file_path))
            
            # Update edge config
            config_path = edge_path / "config" / "known_faces.json"
            data = load_known_faces(str(config_path))
            data = upsert_person(data, person_id, name, role or "", embedding)
            save_known_faces(str(config_path), data)
            
        except ValueError as ve:
             raise HTTPException(status_code=400, detail=f"Face processing error: {str(ve)}")
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Failed to process face: {str(e)}")

    finally:
        # Cleanup temp file
        if temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except:
                pass

    # Create new user in DB
    new_user = AuthorizedUser(
        person_id=person_id,
        name=name,
        role=role,
        godown_id=godown_id,
        is_active=is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user
from datetime import datetime, timedelta

import streamlit as st
from pymongo import ReturnDocument

from .security import generate_token, hash_token
from .users import get_mongo_client


AUTH_DB = "auth_subbuteo"
SESSIONS_COLLECTION = "persistent_sessions"
HANDOFF_COLLECTION = "auth_handoffs"
STANDARD_SESSION_HOURS = 2
REMEMBER_SESSION_DAYS = 30


def sessions_collection():
    coll = get_mongo_client()[AUTH_DB][SESSIONS_COLLECTION]
    try:
        coll.create_index("token_hash", unique=True)
        coll.create_index([("user_id", 1), ("revoked", 1)])
        coll.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass
    return coll


def _request_metadata():
    headers = getattr(getattr(st, "context", None), "headers", {}) or {}
    return {
        "user_agent": headers.get("user-agent", ""),
        "ip_address": headers.get("x-forwarded-for", headers.get("x-real-ip", "")),
    }


def create_persistent_session(user: dict, remember: bool, device_name: str = ""):
    token = generate_token()
    now = datetime.utcnow()
    expires_at = now + (
        timedelta(days=REMEMBER_SESSION_DAYS) if remember else timedelta(hours=STANDARD_SESSION_HOURS)
    )
    meta = _request_metadata()
    sessions_collection().insert_one(
        {
            "user_id": user.get("id"),
            "username": user.get("username"),
            "role": user.get("role"),
            "collection": user.get("collection"),
            "token_hash": hash_token(token),
            "device_name": device_name or "Dispositivo",
            "created_at": now,
            "last_used_at": now,
            "expires_at": expires_at,
            "revoked": False,
            "user_agent": meta["user_agent"],
            "ip_address": meta["ip_address"],
        }
    )
    return token, expires_at


def rotate_token(token: str):
    now = datetime.utcnow()
    old_hash = hash_token(token)
    session = sessions_collection().find_one(
        {"token_hash": old_hash, "revoked": False, "expires_at": {"$gt": now}}
    )
    if not session:
        return None, None

    new_token = generate_token()
    expires_at = session["expires_at"]
    sessions_collection().update_one(
        {"_id": session["_id"]},
        {
            "$set": {
                "token_hash": hash_token(new_token),
                "last_used_at": now,
            }
        },
    )
    session["token_hash"] = hash_token(new_token)
    session["last_used_at"] = now
    return session, new_token


def revoke_token(token: str):
    if not token:
        return
    sessions_collection().update_one(
        {"token_hash": hash_token(token)},
        {"$set": {"revoked": True, "revoked_at": datetime.utcnow()}},
    )


def handoff_collection():
    coll = get_mongo_client()[AUTH_DB][HANDOFF_COLLECTION]
    try:
        coll.create_index("token_hash", unique=True)
        coll.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass
    return coll


def create_handoff_token(user: dict):
    token = generate_token()
    now = datetime.utcnow()
    handoff_collection().insert_one(
        {
            "token_hash": hash_token(token),
            "user_id": user.get("id"),
            "username": user.get("username"),
            "role": user.get("role"),
            "collection": user.get("collection"),
            "created_at": now,
            "expires_at": now + timedelta(minutes=5),
            "consumed": False,
        }
    )
    return token


def consume_handoff_token(token: str):
    now = datetime.utcnow()
    return handoff_collection().find_one_and_update(
        {"token_hash": hash_token(token), "consumed": False, "expires_at": {"$gt": now}},
        {"$set": {"consumed": True, "consumed_at": now}},
        return_document=ReturnDocument.AFTER,
    )

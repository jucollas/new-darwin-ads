"""
Seed a Meta ad account directly into publishing_schema.ad_accounts.

MVP shortcut — skips the OAuth flow entirely and uses credentials from .env.

Usage:
    # Services must be running (at least postgres + dev-auth-service)
    docker compose up -d postgres dev-auth-service

    # Run from project root
    python scripts/seed_ad_account.py
"""

import json
import os
import sys
import uuid
from pathlib import Path

import httpx
import psycopg2
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env from project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def get_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        print(f"ERROR: {key} is not set in .env")
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Read required env vars
# ---------------------------------------------------------------------------
META_ACCESS_TOKEN = get_env("META_ACCESS_TOKEN")
META_TOKEN_ENCRYPTION_KEY = get_env("META_TOKEN_ENCRYPTION_KEY")
AD_ACCOUNT_ID = get_env("AD_ACCOUNT_ID")
PAGE_ID = get_env("PAGE_ID")
BUSINESS_MANAGER_ID = get_env("BUSINESS_MANAGER_ID")
WHATSAPP_PHONE_NUMBER = get_env("WHATSAPP_DEFAULT_PHONE_NUMBER")
DATABASE_URL = get_env("DATABASE_URL")

# Convert async driver URL to sync for psycopg2
DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

# The dev-auth service generates a random UUID for the dev user on first
# startup.  We must call the login endpoint to discover the actual user_id
# so the ad_account row matches the JWT sub claim.
# When running inside Docker, dev-auth is at http://dev-auth-service:8000
# When running from host, it's at http://localhost (via Traefik)
DEV_AUTH_BASE = os.environ.get(
    "DEV_AUTH_BASE_URL",
    "http://dev-auth-service:8000" if os.environ.get("POSTGRES_HOST") == "postgres" else "http://localhost",
)

TOKEN_SCOPES = [
    "ads_management",
    "ads_read",
    "pages_manage_ads",
    "pages_read_engagement",
    "pages_show_list",
    "business_management",
    "whatsapp_business_management",
    "whatsapp_business_messaging",
]


# ---------------------------------------------------------------------------
# 1. Resolve user_id from dev-auth service
# ---------------------------------------------------------------------------
def resolve_user_id() -> str:
    """Login to dev-auth and return the user_id (JWT sub claim)."""
    url = f"{DEV_AUTH_BASE}/api/auth/login"
    payload = {"email": "dev@adgen.ai", "password": "dev123456"}

    print(f"Logging in to dev-auth at {url} ...")
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except httpx.ConnectError:
        print(
            "ERROR: Could not connect to dev-auth-service.\n"
            "Make sure services are running: docker compose up -d"
        )
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"ERROR: Login failed — {e.response.status_code}: {e.response.text}")
        sys.exit(1)

    data = resp.json()
    user_id = data["user"]["id"]
    print(f"Authenticated as: {data['user']['name']} (id={user_id})")
    return user_id


# ---------------------------------------------------------------------------
# 2. Encrypt the access token
# ---------------------------------------------------------------------------
def encrypt_token(token: str, key: str) -> str:
    fernet = Fernet(key.encode())
    return fernet.encrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# 3. Upsert ad account row
# ---------------------------------------------------------------------------
def upsert_ad_account(user_id: str, encrypted_token: str) -> uuid.UUID:
    conn = psycopg2.connect(DATABASE_URL_SYNC)
    conn.autocommit = True
    cur = conn.cursor()

    # Check if row already exists
    cur.execute(
        "SELECT id FROM publishing_schema.ad_accounts WHERE meta_ad_account_id = %s",
        (AD_ACCOUNT_ID,),
    )
    existing = cur.fetchone()

    if existing:
        row_id = existing[0]
        print(f"Ad account already exists (id={row_id}). Updating token ...")
        cur.execute(
            """
            UPDATE publishing_schema.ad_accounts
            SET access_token_encrypted = %s,
                user_id = %s,
                meta_page_id = %s,
                meta_business_id = %s,
                whatsapp_phone_number = %s,
                token_scopes = %s,
                is_active = true
            WHERE id = %s
            """,
            (
                encrypted_token,
                user_id,
                PAGE_ID,
                BUSINESS_MANAGER_ID,
                WHATSAPP_PHONE_NUMBER,
                json.dumps(TOKEN_SCOPES),
                row_id,
            ),
        )
    else:
        row_id = uuid.uuid4()
        print(f"Inserting new ad account (id={row_id}) ...")
        cur.execute(
            """
            INSERT INTO publishing_schema.ad_accounts
                (id, user_id, meta_ad_account_id, meta_page_id, meta_business_id,
                 whatsapp_phone_number, access_token_encrypted, token_expires_at,
                 token_scopes, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, true, NOW())
            """,
            (
                str(row_id),
                user_id,
                AD_ACCOUNT_ID,
                PAGE_ID,
                BUSINESS_MANAGER_ID,
                WHATSAPP_PHONE_NUMBER,
                encrypted_token,
                json.dumps(TOKEN_SCOPES),
            ),
        )

    cur.close()
    conn.close()
    return row_id


# ---------------------------------------------------------------------------
# 4. Verify the row and token decryptability
# ---------------------------------------------------------------------------
def verify(row_id: uuid.UUID) -> None:
    conn = psycopg2.connect(DATABASE_URL_SYNC)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, meta_ad_account_id, meta_page_id,
               access_token_encrypted, is_active
        FROM publishing_schema.ad_accounts
        WHERE id = %s
        """,
        (str(row_id),),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        print("ERROR: Row not found after insert!")
        sys.exit(1)

    rid, uid, acct, page, enc_token, active = row

    print()
    print("Ad account seeded successfully!")
    print(f"  ID:          {rid}")
    print(f"  User ID:     {uid}")
    print(f"  Ad Account:  {acct}")
    print(f"  Page ID:     {page}")
    print(f"  Token encrypted: Yes (length: {len(enc_token)})")
    print(f"  Active:      {active}")

    # Verify token is decryptable
    fernet = Fernet(META_TOKEN_ENCRYPTION_KEY.encode())
    decrypted = fernet.decrypt(enc_token.encode()).decode()
    if decrypted[:10] == META_ACCESS_TOKEN[:10]:
        print(f"  Token verification: OK (first 10 chars match)")
    else:
        print("  Token verification: MISMATCH — encryption key may differ!")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 55)
    print("  AdGen AI — Seed Meta Ad Account (MVP)")
    print("=" * 55)
    print()

    # Step 1: Get user_id from dev-auth
    user_id = resolve_user_id()

    # Step 2: Encrypt the token
    print(f"\nEncrypting access token with Fernet ...")
    encrypted_token = encrypt_token(META_ACCESS_TOKEN, META_TOKEN_ENCRYPTION_KEY)
    print(f"  Encrypted token length: {len(encrypted_token)}")

    # Step 3: Upsert into database
    print()
    row_id = upsert_ad_account(user_id, encrypted_token)

    # Step 4: Verify
    verify(row_id)

    print("\nDone!")


if __name__ == "__main__":
    main()

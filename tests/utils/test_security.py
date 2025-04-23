import pytest

from app.core import security # Assuming security functions are in app.core.security

# --- Test Password Hashing and Verification ---

def test_verify_password_correct():
    """Test password verification with a correct password."""
    plain_password = "mysecretpassword"
    hashed_password = security.get_password_hash(plain_password)
    assert security.verify_password(plain_password, hashed_password) is True

def test_verify_password_incorrect():
    """Test password verification with an incorrect password."""
    plain_password = "mysecretpassword"
    incorrect_password = "wrongpassword"
    hashed_password = security.get_password_hash(plain_password)
    assert security.verify_password(incorrect_password, hashed_password) is False

def test_verify_password_empty():
    """Test password verification with an empty password."""
    plain_password = ""
    hashed_password = security.get_password_hash(plain_password)
    assert security.verify_password(plain_password, hashed_password) is True

def test_verify_password_against_empty_hash():
    """Test verifying a password against an empty or invalid hash string (should fail)."""
    plain_password = "mysecretpassword"
    empty_hash = ""
    # Depending on the underlying library, this might raise an error or return False.
    # Let's assume it should return False for robustness.
    assert security.verify_password(plain_password, empty_hash) is False
    # Also test against a clearly non-hash string
    assert security.verify_password(plain_password, "notahash") is False

def test_get_password_hash_returns_string():
    """Test that get_password_hash returns a string."""
    hashed_password = security.get_password_hash("testpass")
    assert isinstance(hashed_password, str)

def test_get_password_hash_not_plain_text():
    """Test that the returned hash is not the same as the plain text password."""
    plain_password = "hardtoguesspassword123"
    hashed_password = security.get_password_hash(plain_password)
    assert plain_password != hashed_password

def test_get_password_hash_consistent_verification():
    """Test that hashing the same password multiple times yields different hashes
       but they all verify correctly against the original password."""
    plain_password = "another_password!"
    hash1 = security.get_password_hash(plain_password)
    hash2 = security.get_password_hash(plain_password)

    assert hash1 != hash2 # Due to salting, hashes should differ
    assert security.verify_password(plain_password, hash1) is True
    assert security.verify_password(plain_password, hash2) is True

# --- Test JWT Token Creation and Decoding (If applicable in security.py) ---
# Assuming create_access_token and potentially verification logic exists

# @pytest.mark.skip(reason="JWT functions might be in a different module or tested via auth endpoints")
# def test_create_access_token():
#     # Test creating a token
#     pass

# @pytest.mark.skip(reason="JWT functions might be in a different module or tested via auth endpoints")
# def test_decode_access_token():
#     # Test decoding a valid/invalid/expired token
#     pass

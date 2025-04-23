import pytest
import pytest_asyncio # For async fixtures
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.exc import IntegrityError

# Import the CRUD object and schemas/models
from app.crud import crud_user
from app import schemas
from app.db import models
from app.core import security # For mocking hashing/verification

# --- Test CRUDUser Methods ---

@pytest.mark.asyncio
async def test_get_user(db_session_mock: MagicMock):
    """Test retrieving a single user by ID."""
    mock_user = models.User(id=1, username="testget", email="get@test.com")
    db_session_mock.get = AsyncMock(return_value=mock_user) # Mock db.get

    user = await crud_user.CRUDUser.get(db=db_session_mock, id=1)

    db_session_mock.get.assert_awaited_once_with(models.User, 1)
    assert user is not None
    assert user.id == 1
    assert user.username == "testget"

@pytest.mark.asyncio
async def test_get_user_not_found(db_session_mock: MagicMock):
    """Test retrieving a non-existent user by ID."""
    db_session_mock.get = AsyncMock(return_value=None) # Mock db.get returning None

    user = await crud_user.CRUDUser.get(db=db_session_mock, id=999)

    db_session_mock.get.assert_awaited_once_with(models.User, 999)
    assert user is None

@pytest.mark.asyncio
async def test_get_user_by_email(db_session_mock: MagicMock):
    """Test retrieving a user by email."""
    mock_user = models.User(id=2, username="testemail", email="email@test.com")
    # Mock the execute -> scalars -> first sequence
    db_session_mock.execute.return_value.scalar_one_or_none = AsyncMock(return_value=mock_user)

    user = await crud_user.CRUDUser.get_by_email(db=db_session_mock, email="email@test.com")

    # Check that execute was called (assertion on the statement object is complex,
    # so we often rely on checking the mocked return value and call count)
    db_session_mock.execute.assert_awaited_once()
    db_session_mock.execute.return_value.scalar_one_or_none.assert_awaited_once()
    assert user is not None
    assert user.email == "email@test.com"

@pytest.mark.asyncio
async def test_get_user_by_username(db_session_mock: MagicMock):
    """Test retrieving a user by username."""
    mock_user = models.User(id=3, username="testuname", email="uname@test.com")
    db_session_mock.execute.return_value.scalar_one_or_none = AsyncMock(return_value=mock_user)

    user = await crud_user.CRUDUser.get_by_username(db=db_session_mock, username="testuname")

    db_session_mock.execute.assert_awaited_once()
    db_session_mock.execute.return_value.scalar_one_or_none.assert_awaited_once()
    assert user is not None
    assert user.username == "testuname"

@patch('app.core.security.get_password_hash') # Patch the hashing function
@pytest.mark.asyncio
async def test_create_user(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test creating a new user successfully."""
    mock_get_password_hash.return_value = "password_hash_value"
    user_in = schemas.user.UserCreate(
        username="newuser",
        id_number="450203199001011234",
        password="password123",
        full_name="New User Fullname"
    )

    created_user = await crud_user.CRUDUser.create(db=db_session_mock, obj_in=user_in)

    mock_get_password_hash.assert_called_once_with("password123")
    # Check that db.add was called with a User object having correct attributes
    db_session_mock.add.assert_called_once()
    added_obj = db_session_mock.add.call_args[0][0]
    assert isinstance(added_obj, models.User)
    assert added_obj.username == "newuser"
    assert added_obj.id_number == "450203199001011234"
    assert added_obj.full_name == "New User Fullname"
    assert added_obj.password_hash == "password_hash_value"
    
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(added_obj)
    assert created_user == added_obj # Should return the created object

@patch('app.core.security.get_password_hash')
@pytest.mark.asyncio
async def test_create_user_integrity_error(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test user creation failure due to IntegrityError (e.g., duplicate username)."""
    mock_get_password_hash.return_value = "password_hash_value"
    user_in = schemas.user.UserCreate(username="duplicate", id_number="450203199001011234", password="pw")

    # Simulate commit raising IntegrityError
    db_session_mock.commit.side_effect = IntegrityError("Duplicate key", params={}, orig=None)

    with pytest.raises(IntegrityError): # Expect the exception to bubble up
        await crud_user.CRUDUser.create(db=db_session_mock, obj_in=user_in)

    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.rollback.assert_awaited_once() # Check rollback was called
    db_session_mock.refresh.assert_not_called()

@pytest.mark.asyncio
async def test_update_user(db_session_mock: MagicMock):
    """Test updating an existing user."""
    existing_user = models.User(
        id=5, username="toupdate", id_number="450203199001011230", full_name="Old Name",
        password_hash="oldhash"
    )
    # Mock db.get to return the existing user
    # db_session_mock.get = AsyncMock(return_value=existing_user) # Not needed if using db_obj arg

    user_update_data = schemas.user.UserUpdate(
        id_number="450203199001011231", # Change email
        full_name="New Name",      # Change fullname
        # password field is optional in UserUpdate, not tested here
    )

    updated_user = await crud_user.CRUDUser.update(
        db=db_session_mock, db_obj=existing_user, obj_in=user_update_data
    )

    # Assert fields were updated on the existing_user object
    assert existing_user.id_number == "450203199001011231"
    assert existing_user.full_name == "New Name"
    assert existing_user.username == "toupdate" # Should not change
    assert existing_user.password_hash == "oldhash" # Should not change unless password provided

    db_session_mock.add.assert_called_once_with(existing_user)
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(existing_user)
    assert updated_user == existing_user

@patch('app.core.security.get_password_hash') # Patch hashing
@pytest.mark.asyncio
async def test_update_user_with_password(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test updating an existing user, including the password."""
    mock_get_password_hash.return_value = "new_password_hash"
    existing_user = models.User(id=6, username="passupdate", password_hash="oldhash")
    # db_session_mock.get = AsyncMock(return_value=existing_user) # Not needed if using db_obj arg

    user_update_data = schemas.user.UserUpdate(password="newpassword123")

    updated_user = await crud_user.CRUDUser.update(
        db=db_session_mock, db_obj=existing_user, obj_in=user_update_data
    )

    mock_get_password_hash.assert_called_once_with("newpassword123")
    assert existing_user.password_hash == "new_password_hash" # Check password updated

    db_session_mock.add.assert_called_once_with(existing_user)
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(existing_user)
    assert updated_user == existing_user


@patch('app.core.security.verify_password')
@patch('app.crud.crud_user.CRUDUser.get_by_username', new_callable=AsyncMock) # Mock the get_by_username call
@pytest.mark.asyncio
async def test_authenticate_user_success(mock_get_by_username: AsyncMock, mock_verify_password: MagicMock, db_session_mock: MagicMock):
    """Test successful user authentication."""
    mock_user = models.User(id=7, username="authuser", password_hash="correct_hash")
    mock_get_by_username.return_value = mock_user
    mock_verify_password.return_value = True # Simulate correct password

    authenticated_user = await crud_user.CRUDUser.authenticate(
        db=db_session_mock, username="authuser", password="correct_password"
    )

    mock_get_by_username.assert_awaited_once_with(db=db_session_mock, username="authuser")
    mock_verify_password.assert_called_once_with("correct_password", "correct_hash")
    assert authenticated_user == mock_user

@patch('app.core.security.verify_password')
@patch('app.crud.crud_user.CRUDUser.get_by_username', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_incorrect_password(mock_get_by_username: AsyncMock, mock_verify_password: MagicMock, db_session_mock: MagicMock):
    """Test authentication failure due to incorrect password."""
    mock_user = models.User(id=7, username="authuser", password_hash="correct_hash", is_active=True)
    mock_get_by_username.return_value = mock_user
    mock_verify_password.return_value = False # Simulate incorrect password

    authenticated_user = await crud_user.CRUDUser.authenticate(
        db=db_session_mock, username="authuser", password="wrong_password"
    )

    mock_get_by_username.assert_awaited_once_with(db=db_session_mock, username="authuser")
    mock_verify_password.assert_called_once_with("wrong_password", "correct_hash")
    assert authenticated_user is None

@patch('app.crud.crud_user.CRUDUser.get_by_username', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_not_found(mock_get_by_username: AsyncMock, db_session_mock: MagicMock):
    """Test authentication failure due to user not found."""
    mock_get_by_username.return_value = None # Simulate user not found

    authenticated_user = await crud_user.CRUDUser.authenticate(
        db=db_session_mock, username="nonexistent", password="any_password"
    )

    mock_get_by_username.assert_awaited_once_with(db=db_session_mock, username="nonexistent")
    assert authenticated_user is None

@patch('app.core.security.verify_password')
@patch('app.crud.crud_user.CRUDUser.get_by_username', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_authenticate_user_inactive(mock_get_by_username: AsyncMock, mock_verify_password: MagicMock, db_session_mock: MagicMock):
    """Test authentication failure due to inactive user."""
    mock_user = models.User(id=8, username="inactiveuser", password_hash="correct_hash") # User is inactive
    mock_get_by_username.return_value = mock_user
    mock_verify_password.return_value = True # Password is correct

    authenticated_user = await crud_user.CRUDUser.authenticate(
        db=db_session_mock, username="inactiveuser", password="correct_password"
    )

    mock_get_by_username.assert_awaited_once_with(db=db_session_mock, username="inactiveuser")
    # verify_password might or might not be called depending on implementation order,
    # but the end result is None because of is_active check
    assert authenticated_user is None


# --- Test Bulk Create ---

@patch('app.core.security.get_password_hash')
@pytest.mark.asyncio
async def test_bulk_create_users_success(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test bulk creating users successfully without roles/groups."""
    mock_get_password_hash.side_effect = lambda p: f"hashed_{p}" # Simple mock hash
    users_in = [
        schemas.user.UserImportRecord(username="bulk1", id_number="450103199101011200", password="p1", fullname="Bulk One"),
        schemas.user.UserImportRecord(username="bulk2", id_number="450103199101011201", password="p2", fullname="Bulk Two"),
    ]

    # Mock flush and commit to succeed
    db_session_mock.flush = AsyncMock()
    db_session_mock.commit = AsyncMock()
    db_session_mock.rollback = AsyncMock() # Should not be called

    success_count, errors = await crud_user.CRUDUser.bulk_create(db=db_session_mock, users_in=users_in)

    assert success_count == 2
    assert len(errors) == 0
    assert db_session_mock.add.call_count == 2
    assert db_session_mock.flush.call_count == 2 # Called once per user in the loop
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.rollback.assert_not_called()

    # Check added objects (optional, but good)
    added_obj1 = db_session_mock.add.call_args_list[0][0][0]
    added_obj2 = db_session_mock.add.call_args_list[1][0][0]
    assert added_obj1.username == "bulk1"
    assert added_obj1.password_hash == "hashed_p1"
    assert added_obj2.username == "bulk2"
    assert added_obj2.password_hash == "hashed_p2"

@patch('app.core.security.get_password_hash')
@pytest.mark.asyncio
async def test_bulk_create_users_with_duplicates(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test bulk create with some users failing due to IntegrityError on flush."""
    mock_get_password_hash.side_effect = lambda p: f"hashed_{p}"
    users_in = [
        schemas.user.UserImportRecord(username="okuser", password="p1"),
        schemas.user.UserImportRecord(username="duplicate", password="p2"), # This one will fail flush
        schemas.user.UserImportRecord(username="anotherok", password="p3"),
    ]

    # Mock flush: succeed for first, fail for second, succeed for third
    flush_results = [None, IntegrityError("dup", {}, None), None]
    db_session_mock.flush = AsyncMock(side_effect=flush_results)
    db_session_mock.commit = AsyncMock()
    db_session_mock.rollback = AsyncMock() # Should be called once for the duplicate

    success_count, errors = await crud_user.CRUDUser.bulk_create(db=db_session_mock, users_in=users_in)

    assert success_count == 2 # okuser and anotherok
    assert len(errors) == 1
    assert errors[0]["username"] == "duplicate"
    assert errors[0]["row"] == 3 # row index 1 + 2 = 3
    assert "already exists" in errors[0]["error"]

    assert db_session_mock.add.call_count == 3
    assert db_session_mock.flush.call_count == 3
    db_session_mock.rollback.assert_awaited_once() # Rolled back the failed flush
    db_session_mock.commit.assert_awaited_once() # Committed the successful ones

@patch('app.core.security.get_password_hash')
@pytest.mark.asyncio
async def test_bulk_create_users_with_roles_groups(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test bulk create successfully assigns existing roles and groups."""
    mock_get_password_hash.side_effect = lambda p: f"hashed_{p}"
    users_in = [
        schemas.user.UserImportRecord(username="user_rg", password="p1"),
    ]

    # Mock Role/Group lookup
    mock_role_student = MagicMock(spec=models.Role); mock_role_student.name = "Student"
    mock_group_a = MagicMock(spec=models.Group); mock_group_a.name = "Group A"
    role_execute_mock = AsyncMock()
    role_execute_mock.scalars.return_value.all = MagicMock(return_value=[mock_role_student])
    group_execute_mock = AsyncMock()
    group_execute_mock.scalars.return_value.all = MagicMock(return_value=[mock_group_a])
    # Make execute return different mocks based on the query (simplified check)
    def execute_side_effect(*args, **kwargs):
        stmt = args[0]
        if "role" in str(stmt).lower(): return role_execute_mock
        if "group" in str(stmt).lower(): return group_execute_mock
        return AsyncMock() # Default mock
    db_session_mock.execute = AsyncMock(side_effect=execute_side_effect)

    db_session_mock.flush = AsyncMock()
    db_session_mock.commit = AsyncMock()

    success_count, errors = await crud_user.CRUDUser.bulk_create(db=db_session_mock, users_in=users_in)

    assert success_count == 1
    assert len(errors) == 0
    db_session_mock.commit.assert_awaited_once()

    # Check that the added user object has the correct roles/groups assigned
    added_user = db_session_mock.add.call_args[0][0]
    assert len(added_user.roles) == 1
    assert added_user.roles[0].name == "Student"
    assert len(added_user.groups) == 1
    assert added_user.groups[0].name == "Group A"


@patch('app.core.security.get_password_hash')
@pytest.mark.asyncio
async def test_bulk_create_users_nonexistent_role(mock_get_password_hash: MagicMock, db_session_mock: MagicMock):
    """Test bulk create failure when a specified role does not exist."""
    mock_get_password_hash.side_effect = lambda p: f"hashed_{p}"
    users_in = [
         schemas.user.UserImportRecord(username="user_bad_role", password="p1"),
    ]

    # Mock Role lookup to return empty list
    role_execute_mock = AsyncMock()
    role_execute_mock.scalars.return_value.all = MagicMock(return_value=[])
    db_session_mock.execute = AsyncMock(return_value=role_execute_mock)

    db_session_mock.flush = AsyncMock()
    db_session_mock.commit = AsyncMock()

    success_count, errors = await crud_user.CRUDUser.bulk_create(db=db_session_mock, users_in=users_in)

    assert success_count == 0
    assert len(errors) == 1
    assert errors[0]["username"] == "user_bad_role"
    assert "Role 'NonExistentRole' not found" in errors[0]["error"]
    db_session_mock.add.assert_not_called() # User should not be added
    db_session_mock.commit.assert_not_called() # Nothing to commit

import pytest
import pytest_asyncio # For async fixtures
from unittest.mock import MagicMock, AsyncMock
from typing import AsyncGenerator, Generator

from fastapi import FastAPI
from httpx import AsyncClient # Use AsyncClient for async app
from sqlalchemy.ext.asyncio import AsyncSession

# Import your FastAPI app instance
# Adjust the import path based on your project structure
from app.main import app as fastapi_app
from app.api import deps
from app.db import models
from app.core import security # For creating test tokens if needed

# --- Mock Database Session ---

@pytest.fixture(scope="function") # function scope ensures isolation between tests
def db_session_mock() -> MagicMock:
    """Provides a MagicMock simulating an AsyncSession."""
    mock = MagicMock(spec=AsyncSession) # Use MagicMock for flexibility
    # Mock common methods used in CRUD
    mock.execute = AsyncMock()
    mock.get = AsyncMock()
    mock.add = MagicMock()
    mock.add_all = MagicMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.refresh = AsyncMock()
    mock.flush = AsyncMock()
    mock.scalar = AsyncMock()
    mock.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[]))) # Default to empty list

    # Make the mock itself awaitable if needed directly (though usually methods are awaited)
    # async def _await_mock(): pass
    # mock.__await__ = _await_mock # Less common to await the session directly

    # Configure scalar/scalars to return specific values in tests if needed
    # e.g., mock.scalar.return_value = 1
    # e.g., mock.scalars.return_value.all.return_value = [mock_object]

    return mock


@pytest_asyncio.fixture(scope="function")
async def override_get_db(db_session_mock: MagicMock) -> AsyncGenerator[None, None]:
    """Overrides the get_db dependency to yield the mock session."""
    async def _override():
        yield db_session_mock
    fastapi_app.dependency_overrides[deps.get_db] = _override
    yield
    # Clean up override after test finishes
    del fastapi_app.dependency_overrides[deps.get_db]


# --- Test Client ---

@pytest_asyncio.fixture(scope="session") # Session scope for efficiency if app setup is heavy
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an httpx AsyncClient for making requests to the app."""
    # Use app context manager if available for startup/shutdown events
    async with AsyncClient(app=fastapi_app, base_url="http://test") as ac:
        yield ac

# --- Mock User Objects ---

# Helper to create mock permission objects
def create_mock_permission(code: str, id: int) -> MagicMock:
    mock = MagicMock(spec=models.Permission)
    mock.id = id
    mock.code = code
    return mock

# Helper to create mock role objects with permissions
def create_mock_role(name: str, id: int, permissions: list[MagicMock]) -> MagicMock:
    mock = MagicMock(spec=models.Role)
    mock.id = id
    mock.name = name
    mock.permissions = permissions
    return mock

@pytest.fixture(scope="session")
def mock_permissions() -> dict[str, MagicMock]:
    """Provides a dictionary of mock permission objects."""
    return {
        "manage_users": create_mock_permission("manage_users", 1),
        "manage_roles": create_mock_permission("manage_roles", 2),
        "manage_question_bank": create_mock_permission("manage_question_bank", 3),
        "manage_exams": create_mock_permission("manage_exams", 4),
        "grade_exams": create_mock_permission("grade_exams", 5),
        "view_all_results": create_mock_permission("view_all_results", 6),
        # Add any other permissions needed
    }

@pytest.fixture(scope="session")
def mock_roles(mock_permissions: dict[str, MagicMock]) -> dict[str, MagicMock]:
    """Provides a dictionary of mock role objects."""
    admin_perms = list(mock_permissions.values()) # Admin has all
    teacher_perms = [
        mock_permissions["manage_question_bank"],
        mock_permissions["manage_exams"],
        mock_permissions["grade_exams"],
        mock_permissions["view_all_results"],
    ]
    student_perms = [] # Student might have implicit permissions not modeled here

    return {
        "Admin": create_mock_role("Admin", 1, admin_perms),
        "Teacher": create_mock_role("Teacher", 2, teacher_perms),
        "Student": create_mock_role("Student", 3, student_perms),
    }


@pytest.fixture(scope="function") # Function scope if user details might change per test
def mock_user_admin(mock_roles: dict[str, MagicMock]) -> MagicMock:
    """Provides a mock admin user."""
    user = MagicMock(spec=models.User)
    user.id = 1
    user.username = "admin_user"
    user.email = "admin@test.com"
    user.is_active = True
    user.is_superuser = True # Often simpler than managing all perms explicitly
    user.roles = [mock_roles["Admin"]]
    user.groups = []
    return user

@pytest.fixture(scope="function")
def mock_user_teacher(mock_roles: dict[str, MagicMock]) -> MagicMock:
    """Provides a mock teacher user."""
    user = MagicMock(spec=models.User)
    user.id = 2
    user.username = "teacher_user"
    user.email = "teacher@test.com"
    user.is_active = True
    user.is_superuser = False
    user.roles = [mock_roles["Teacher"]]
    user.groups = []
    return user

@pytest.fixture(scope="function")
def mock_user_student(mock_roles: dict[str, MagicMock]) -> MagicMock:
    """Provides a mock student user."""
    user = MagicMock(spec=models.User)
    user.id = 3
    user.username = "student_user"
    user.email = "student@test.com"
    user.is_active = True
    user.is_superuser = False
    user.roles = [mock_roles["Student"]]
    user.groups = []
    return user

@pytest.fixture(scope="function")
def mock_user_no_perms() -> MagicMock:
    """Provides a mock user with no specific roles/perms."""
    user = MagicMock(spec=models.User)
    user.id = 4
    user.username = "noperms_user"
    user.email = "noperms@test.com"
    user.is_active = True
    user.is_superuser = False
    user.roles = []
    user.groups = []
    return user


# --- Dependency Overrides for Permissions ---

# Use this fixture in tests requiring an authenticated user
@pytest_asyncio.fixture(scope="function")
async def override_get_current_active_user(mock_user_student: MagicMock) -> AsyncGenerator[None, None]:
    """Overrides the get_current_active_user dependency. Defaults to student."""
    async def _override():
        return mock_user_student # Default user for tests needing authentication
    fastapi_app.dependency_overrides[deps.get_current_active_user] = _override
    yield
    del fastapi_app.dependency_overrides[deps.get_current_active_user]


# --- More specific permission overrides (use as needed) ---

@pytest_asyncio.fixture(scope="function")
async def override_check_manage_users_permission(mock_user_admin: MagicMock) -> AsyncGenerator[None, None]:
    """Overrides the specific permission check dependency."""
    # Find the actual dependency function object if it's different from deps.get_current_active_user
    # Assuming it's defined like: async def check_manage_users_permission(...) -> models.User: ...
    # We need to import the actual function from the endpoints module where it's defined
    try:
        from app.api.v1.endpoints.users import check_manage_users_permission as dep_func
    except ImportError:
        # Handle case where the dependency might be defined elsewhere or named differently
        pytest.skip("Could not import check_manage_users_permission dependency")
        dep_func = None # Keep linter happy

    if dep_func:
        async def _override():
            # Logic could be more complex if the dep itself checks permissions
            # Here, we just return the admin user who presumably has the permission
            return mock_user_admin
        fastapi_app.dependency_overrides[dep_func] = _override
        yield
        del fastapi_app.dependency_overrides[dep_func]
    else:
        yield # Skip if dependency not found

# Add similar override fixtures for other specific permission checks as needed:
# override_check_manage_roles_permission
# override_check_manage_question_bank_permission
# override_check_manage_exams_permission
# override_check_grade_exams_permission
# override_check_view_all_results_permission

# Example:
# @pytest_asyncio.fixture(scope="function")
# async def override_check_manage_exams_permission(mock_user_teacher: MagicMock) -> AsyncGenerator[None, None]:
#     try:
#         from app.api.v1.endpoints.exams import check_manage_exams_permission as dep_func
#     except ImportError:
#         pytest.skip("Could not import check_manage_exams_permission dependency")
#         dep_func = None
#
#     if dep_func:
#         async def _override():
#             return mock_user_teacher # Or admin
#         fastapi_app.dependency_overrides[dep_func] = _override
#         yield
#         del fastapi_app.dependency_overrides[dep_func]
#     else:
#         yield


# --- Optional: Fixture for generating auth headers ---
# @pytest.fixture(scope="function")
# def auth_headers_admin(mock_user_admin: MagicMock) -> dict[str, str]:
#     """Generates auth headers for the mock admin user."""
#     # In a real scenario, you might need to generate a short-lived test token
#     # For mock tests, often just overriding the dependency is enough
#     # If token verification logic is complex and needs testing:
#     # token = security.create_access_token(data={"sub": mock_user_admin.username})
#     # return {"Authorization": f"Bearer {token}"}
#     # But for now, we rely on dependency overrides
#     return {"Authorization": "Bearer fake-admin-token"}

# @pytest.fixture(scope="function")
# def auth_headers_student(mock_user_student: MagicMock) -> dict[str, str]:
#      return {"Authorization": "Bearer fake-student-token"}

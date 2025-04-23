import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.exc import IntegrityError

# Import the CRUD object and schemas/models
from app.crud import crud_group
from app import schemas
from app.db import models

# --- Test CRUDGroup Methods ---

@pytest.mark.asyncio
async def test_get_group(db_session_mock: MagicMock):
    """Test retrieving a single group by ID."""
    mock_group = models.Group(id=1, name="Test Group Get", description="Desc Get")
    db_session_mock.get = AsyncMock(return_value=mock_group)

    group = await crud_group.CRUDGroup.get(db=db_session_mock, id=1)

    db_session_mock.get.assert_awaited_once_with(models.Group, 1)
    assert group is not None
    assert group.id == 1
    assert group.name == "Test Group Get"

@pytest.mark.asyncio
async def test_get_group_not_found(db_session_mock: MagicMock):
    """Test retrieving a non-existent group by ID."""
    db_session_mock.get = AsyncMock(return_value=None)

    group = await crud_group.CRUDGroup.get(db=db_session_mock, id=999)

    db_session_mock.get.assert_awaited_once_with(models.Group, 999)
    assert group is None

@pytest.mark.asyncio
async def test_get_group_by_name(db_session_mock: MagicMock):
    """Test retrieving a group by name."""
    mock_group = models.Group(id=2, name="Test Group Name", description="Desc Name")
    db_session_mock.execute.return_value.scalar_one_or_none = AsyncMock(return_value=mock_group)

    group = await crud_group.CRUDGroup.get_by_name(db=db_session_mock, name="Test Group Name")

    db_session_mock.execute.assert_awaited_once()
    db_session_mock.execute.return_value.scalar_one_or_none.assert_awaited_once()
    assert group is not None
    assert group.name == "Test Group Name"

@pytest.mark.asyncio
async def test_get_multi_groups(db_session_mock: MagicMock):
    """Test retrieving multiple groups."""
    mock_groups = [
        models.Group(id=3, name="Group A"),
        models.Group(id=4, name="Group B"),
    ]
    # Mock the execute -> scalars -> all sequence
    db_session_mock.execute.return_value.scalars.return_value.all = MagicMock(return_value=mock_groups)

    groups = await crud_group.CRUDGroup.get_multi(db=db_session_mock, skip=0, limit=10)

    db_session_mock.execute.assert_awaited_once()
    # Add assertions for skip/limit if they are applied in the query construction
    assert groups == mock_groups
    assert len(groups) == 2

@pytest.mark.asyncio
async def test_create_group(db_session_mock: MagicMock):
    """Test creating a new group successfully."""
    group_in = schemas.group.GroupCreate(name="New Group", description="New Desc")

    created_group = await crud_group.CRUDGroup.create(db=db_session_mock, obj_in=group_in)

    db_session_mock.add.assert_called_once()
    added_obj = db_session_mock.add.call_args[0][0]
    assert isinstance(added_obj, models.Group)
    assert added_obj.name == "New Group"
    assert added_obj.description == "New Desc"

    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(added_obj)
    assert created_group == added_obj

@pytest.mark.asyncio
async def test_create_group_integrity_error(db_session_mock: MagicMock):
    """Test group creation failure due to IntegrityError (e.g., duplicate name)."""
    group_in = schemas.group.GroupCreate(name="Duplicate Group")
    db_session_mock.commit.side_effect = IntegrityError("Duplicate key", params={}, orig=None)

    with pytest.raises(IntegrityError):
        await crud_group.CRUDGroup.create(db=db_session_mock, obj_in=group_in)

    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.rollback.assert_awaited_once()
    db_session_mock.refresh.assert_not_called()

@pytest.mark.asyncio
async def test_update_group(db_session_mock: MagicMock):
    """Test updating an existing group."""
    existing_group = models.Group(id=5, name="Old Group Name", description="Old Desc")
    group_update_data = schemas.group.GroupUpdate(name="Updated Group Name", description="Updated Desc")

    updated_group = await crud_group.CRUDGroup.update(
        db=db_session_mock, db_obj=existing_group, obj_in=group_update_data
    )

    assert existing_group.name == "Updated Group Name"
    assert existing_group.description == "Updated Desc"

    db_session_mock.add.assert_called_once_with(existing_group)
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(existing_group)
    assert updated_group == existing_group

@pytest.mark.asyncio
async def test_remove_group(db_session_mock: MagicMock):
    """Test removing a group."""
    group_to_remove = models.Group(id=6, name="ToDelete")
    # Mock db.get to return the group for deletion if the method fetches it first
    # db_session_mock.get = AsyncMock(return_value=group_to_remove) # If remove takes ID
    # If remove takes db_obj directly:

    removed_group = await crud_group.CRUDGroup.remove(db=db_session_mock, db_obj=group_to_remove)

    db_session_mock.delete.assert_awaited_once_with(group_to_remove)
    db_session_mock.commit.assert_awaited_once()
    assert removed_group == group_to_remove # Typically returns the deleted object


# --- Tests for User-Group Associations (if implemented in crud_group) ---

@pytest.mark.asyncio
async def test_add_user_to_group_success(db_session_mock: MagicMock):
    """Test adding a user to a group successfully."""
    mock_group = models.Group(id=7, name="Group With Users", users=[])
    mock_user = models.User(id=10, username="user_to_add", groups=[])

    # Assume crud method fetches group and user first
    db_session_mock.get = AsyncMock(side_effect=lambda model, id: mock_group if model == models.Group and id == 7 else (mock_user if model == models.User and id == 10 else None))

    # Or if the method takes objects directly:
    # result_group = await crud_group.CRUDGroup.add_user_to_group(db=db_session_mock, group=mock_group, user=mock_user)

    # Assuming method takes IDs:
    result_group = await crud_group.CRUDGroup.add_user_to_group(db=db_session_mock, group_id=7, user_id=10)

    # Assert user was added to group's user list (or association table entry created)
    # This depends heavily on the implementation detail (direct append vs association)
    # If direct append:
    assert mock_user in mock_group.users
    # Check DB calls
    db_session_mock.add.assert_called_once_with(mock_group) # or the association object
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(mock_group)
    assert result_group == mock_group

@pytest.mark.asyncio
async def test_add_user_to_group_already_member(db_session_mock: MagicMock):
    """Test adding a user who is already a member of the group (should be idempotent)."""
    mock_user = models.User(id=11, username="member_user")
    mock_group = models.Group(id=8, name="Group Existing Member", users=[mock_user])
    mock_user.groups = [mock_group] # Link back for consistency

    db_session_mock.get = AsyncMock(side_effect=lambda model, id: mock_group if model == models.Group and id == 8 else (mock_user if model == models.User and id == 11 else None))

    result_group = await crud_group.CRUDGroup.add_user_to_group(db=db_session_mock, group_id=8, user_id=11)

    # Assert that commit/add might not even be called if already present
    # Or assert that it doesn't add duplicates
    db_session_mock.add.assert_not_called() # Or called once but no change
    db_session_mock.commit.assert_not_called() # Or called once but no change
    db_session_mock.refresh.assert_not_called() # Or called once but no change
    assert result_group == mock_group # Should return the group


@pytest.mark.asyncio
async def test_remove_user_from_group_success(db_session_mock: MagicMock):
    """Test removing a user from a group successfully."""
    mock_user = models.User(id=12, username="user_to_remove")
    mock_group = models.Group(id=9, name="Group Remove User", users=[mock_user])
    mock_user.groups = [mock_group]

    db_session_mock.get = AsyncMock(side_effect=lambda model, id: mock_group if model == models.Group and id == 9 else (mock_user if model == models.User and id == 12 else None))

    result_group = await crud_group.CRUDGroup.remove_user_from_group(db=db_session_mock, group_id=9, user_id=12)

    # Assert user was removed from group's user list
    assert mock_user not in mock_group.users
    # Check DB calls
    db_session_mock.add.assert_called_once_with(mock_group) # Or association handling
    db_session_mock.commit.assert_awaited_once()
    db_session_mock.refresh.assert_awaited_once_with(mock_group)
    assert result_group == mock_group

@pytest.mark.asyncio
async def test_remove_user_from_group_not_member(db_session_mock: MagicMock):
    """Test removing a user who is not a member of the group."""
    mock_user = models.User(id=13, username="not_member")
    mock_group = models.Group(id=10, name="Group Not Member", users=[])

    db_session_mock.get = AsyncMock(side_effect=lambda model, id: mock_group if model == models.Group and id == 10 else (mock_user if model == models.User and id == 13 else None))

    result_group = await crud_group.CRUDGroup.remove_user_from_group(db=db_session_mock, group_id=10, user_id=13)

    # Assert that commit/add are not called
    db_session_mock.add.assert_not_called()
    db_session_mock.commit.assert_not_called()
    db_session_mock.refresh.assert_not_called()
    assert result_group == mock_group # Should still return the group

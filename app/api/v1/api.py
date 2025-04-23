from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, roles, permissions, groups, \
    questions, exams, attempts, results  # Add other endpoint modules here later

api_router = APIRouter()

# Include authentication routes
api_router.include_router(auth.router, prefix="/v1/auth", tags=["Authentication"]) # Changed prefix

# Include user routes
api_router.include_router(users.router, prefix="/v1/users", tags=["Users"])

# Include role routes
api_router.include_router(roles.router, prefix="/v1/roles", tags=["Roles"])

# Include permission routes
api_router.include_router(permissions.router, prefix="/v1/permissions", tags=["Permissions"])
# Include group routes
api_router.include_router(groups.router, prefix="/v1/groups", tags=["Groups"])

# Include question management routes (libs, chapters, questions)
api_router.include_router(questions.router, prefix="/v1/q", tags=["Question Management"]) # Use shorter prefix like /q
# Include exam management routes
api_router.include_router(exams.router, prefix="/v1/exams", tags=["Exams"])
# Include exam taking routes (attempts, answers)
api_router.include_router(attempts.router, prefix="/v1", tags=["Exam Taking"]) # Prefix routes internally

# Include grading and results routes
api_router.include_router(results.router, prefix="/v1", tags=["Grading & Results"]) # Contains /grading/... and /results/...
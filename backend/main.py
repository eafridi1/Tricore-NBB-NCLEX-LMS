from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as auth_router
from routers import categories as categories_router
from routers import questions as questions_router
from routers import quizzes as quizzes_router
from routers import users as users_router
from routers import bookmarks as bookmarks_router
from routers import admin as admin_router
from routers import pdfs as pdfs_router
from routers import videos as videos_router
from routers import announcements as announcements_router
from routers import subscriptions as subscriptions_router
import os
from routers import payments as payments_router

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["*"],
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(categories_router.router, prefix="/categories", tags=["categories"])
app.include_router(questions_router.router, prefix="/questions", tags=["questions"])
app.include_router(quizzes_router.router, prefix="/quizzes", tags=["quizzes"])
app.include_router(users_router.router, prefix="/users", tags=["users"])
app.include_router(bookmarks_router.router, prefix="/bookmarks", tags=["bookmarks"])
app.include_router(admin_router.router, prefix="/admin", tags=["admin"])
app.include_router(announcements_router.router, prefix="/announcements", tags=["announcements"])
app.include_router(pdfs_router.router, prefix="/pdfs", tags=["pdfs"])
app.include_router(videos_router.router, prefix="/videos", tags=["videos"])
app.include_router(subscriptions_router.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(payments_router.router, prefix="/payments", tags=["payments"])


@app.get("/health")
def health():
    return {"status": "ok"}
# uvicorn main:app --reload
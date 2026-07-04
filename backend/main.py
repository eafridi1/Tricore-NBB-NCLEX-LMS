from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as auth_router
from routers import categories as categories_router
from routers import questions as questions_router
from routers import quizzes as quizzes_router


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(categories_router.router, prefix="/categories", tags=["categories"])
app.include_router(questions_router.router, prefix="/questions", tags=["questions"])
app.include_router(quizzes_router.router, prefix="/quizzes", tags=["quizzes"])


@app.get("/health")
def health():
    return {"status": "ok"}
# uvicorn main:app --reload
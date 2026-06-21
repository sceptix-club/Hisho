from fastapi import FastAPI
from api.routes.letters import router as letters_router
from api.routes.officials import router as officials_router
import uvicorn

app = FastAPI()
app.include_router(letters_router)
app.include_router(officials_router)


@app.get("/")
async def root():
    return {"message": "API running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

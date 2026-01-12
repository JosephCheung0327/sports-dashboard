from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import nhl
import uvicorn

app = FastAPI(title="Sports Dashboard API")

# Configure CORS to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers for different sports
app.include_router(nhl.router, prefix="/api/nhl", tags=["nhl"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Sports Dashboard API is running"}

if __name__ == "__main__":
    # Allow running this file directly for debugging
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

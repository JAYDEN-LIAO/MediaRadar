import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router

app = FastAPI(title="MediaRadar API")

# 允许跨域，方便前端 HTML 直接调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    # 在项目根目录运行: python api/main.py
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
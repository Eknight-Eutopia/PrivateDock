from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware as FastCORSMiddleware


def setup_cors(app: FastAPI, origins: list[str]):
    if not origins:
        return
    app.add_middleware(
        FastCORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )

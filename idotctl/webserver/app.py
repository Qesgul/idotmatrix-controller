"""FastAPI 应用入口。"""
from fastapi import FastAPI

app = FastAPI()


def main(argv=None):
    import uvicorn
    uvicorn.run("idotctl.webserver.app:app", host="0.0.0.0", port=8000)

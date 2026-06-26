from fastapi import FastAPI
from pydantic import BaseModel
from backend_service import handle_query, handle_explore

app = FastAPI()


class QueryRequest(BaseModel):
    query: str


class ExploreRequest(BaseModel):
    topic: str


@app.get("/")
def root():
    return {"message": "CrossDoc API running"}


@app.post("/query")
def query(req: QueryRequest):
    return handle_query(req.query)


@app.post("/explore")
def explore(req: ExploreRequest):
    return handle_explore(req.topic)
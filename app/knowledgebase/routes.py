from fastapi import APIRouter, File, UploadFile
from loguru import logger
from openai import OpenAI
from sqlmodel import select

from app.core.database import DatabaseSessionType
from app.knowledgebase.models import Knowledgebase


router = APIRouter(tags=["knowledgebase"], prefix="/knowledgebase")

client = OpenAI()

VECTOR_STORE_NAME = "Assistant Knowledgebase"


@router.post("/upload")
async def upload_knowledgebase(
    session: DatabaseSessionType, files: list[UploadFile] = File(...)
):
    logger.info("Uploading knowledgebase...")

    vector_stores = client.beta.vector_stores.list()
    if len(vector_stores.data) == 0:
        logger.info("Creating vector store for knowledgebase...")
        vector_store = client.beta.vector_stores.create(name=VECTOR_STORE_NAME)
    else:  # pragma: no cover
        vector_store = vector_stores.data[0]
        logger.debug(f"Using existing vector store: {vector_store}")

    logger.debug(f"Found vector store: {vector_store}")

    kbs: list[Knowledgebase] = []
    for file in files:
        file_data = await file.read()
        openai_file = client.files.create(file=file_data, purpose="assistants")
        kbs.append(Knowledgebase(openai_file_id=openai_file.id))

    # save first before creating files
    session.add_all(kbs)
    session.commit()

    # create vectore store file for each file uploaded
    vector_store_file = client.beta.vector_stores.file_batches.create(
        vector_store_id=vector_store.id, file_ids=[kb.openai_file_id for kb in kbs]
    )

    logger.info(f"Knowledgebase uploaded successfully: {vector_store_file}")


@router.get("/")
async def get_knowledgebase(session: DatabaseSessionType):
    return session.exec(select(Knowledgebase)).all()

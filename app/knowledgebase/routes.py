from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from openai import OpenAI
from sqlmodel import select

from app.core.database import DatabaseSessionType
from app.knowledgebase.models import Knowledgebase


router = APIRouter(tags=["knowledgebase"], prefix="/knowledgebase")

client = OpenAI()

VECTOR_STORE_NAME = "Assistant Knowledgebase"


@router.post("/{account_id}/upload")
async def upload_knowledgebase(
    session: DatabaseSessionType, account_id: str, files: list[UploadFile] = File(...)
):
    logger.info("Uploading knowledgebase...")

    vector_stores = client.beta.vector_stores.list()
    if len(vector_stores.data) == 0:
        logger.info("Creating vector store for knowledgebase...")
        vector_store = client.beta.vector_stores.create(
            name=VECTOR_STORE_NAME, metadata={"account_id": account_id}
        )
    else:  # pragma: no cover
        vector_store = vector_stores.data[0]
        logger.debug(f"Using existing vector store: {vector_store}")

    logger.debug(f"Found vector store: {vector_store}")

    kbs: list[Knowledgebase] = []
    for file in files:
        if not file.filename:
            logger.warning("Skipping one file has no filename")
            continue

        logger.debug(f"processing {file.filename}, {file.content_type}")
        file_data: bytes = await file.read()
        openai_file = client.files.create(
            file=(file.filename, file_data, file.content_type), purpose="assistants"
        )
        kbs.append(
            Knowledgebase(
                filesize=file.size,  # type: ignore
                openai_vector_store_id=vector_store.id,
                filename=file.filename,
                openai_file_id=openai_file.id,
                account_id=account_id,
            )
        )

    # create vectore store file for each file uploaded
    vector_store_file = client.beta.vector_stores.file_batches.create(
        vector_store_id=vector_store.id, file_ids=[kb.openai_file_id for kb in kbs]
    )

    session.add_all(kbs)
    session.commit()

    logger.info(f"Knowledgebase uploaded successfully: {vector_store_file}")

    return {"message": "files uploaded successfully"}


@router.get("/{account_id}")
async def get_knowledgebase(session: DatabaseSessionType, account_id: str):
    return session.exec(
        select(Knowledgebase).where(Knowledgebase.account_id == account_id)
    ).all()


@router.delete("/{id}")
async def remove_knowledgebase(session: DatabaseSessionType, id: str):
    """Deletes the knowledgebase by id from db and from openai"""
    stmt = select(Knowledgebase).where(Knowledgebase.id == id)
    kb = session.exec(stmt).first()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledgebase not found")

    # delete knowledgebase
    logger.debug(
        f"Deleting knowledgebase: {kb.filename} with openai_file_id: {kb.openai_file_id}"
    )
    session.delete(kb)
    session.commit()

    # remove file in vectorstore
    client.beta.vector_stores.files.delete(
        vector_store_id=kb.openai_vector_store_id, file_id=kb.openai_file_id
    )
    # remove file in openai
    client.files.delete(kb.openai_file_id)

    return {"message": "Knowledgebase deleted successfully"}

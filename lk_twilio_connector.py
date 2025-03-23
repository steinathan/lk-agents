import asyncio
import json
import os
import random
import string
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, create_engine, select
from twilio.rest import Client
from twilio.rest.trunking.v1.trunk import TrunkInstance
from app.core.config import settings

from livekit import api
from livekit.protocol.sip import ListSIPInboundTrunkRequest
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
from tenacity import retry, stop_after_attempt, wait_exponential
from app.lk_connector.models import InboundTrunk, OutboundTrunk, PhoneNumber


load_dotenv(dotenv_path=".env.local")


class ConnectParams(BaseModel):
    phone_number: str
    twilio_auth_token: str
    twilio_account_sid: str
    account_id: str


def generate_random_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(random.choice(chars) for _ in range(length))


def create_twilio_trunk(
    session: Session, client: Client, sip_uri: str
) -> TrunkInstance:

    logger.info(f"Creating LiveKit Trunk on Twilio: {sip_uri}")
    domain_name = f"livekit-trunk-{os.urandom(4).hex()}.pstn.twilio.com"
    trunk = client.trunking.v1.trunks.create(
        friendly_name="LiveKit Trunk",
        domain_name=domain_name,
    )
    trunk.origination_urls.create(
        sip_url=sip_uri,
        weight=1,
        priority=1,
        enabled=True,
        friendly_name="LiveKit SIP URI",
    )

    logger.info("Created new LiveKit Trunk.")

    return trunk


async def _cleanup_lk_inbound_trunks(params: ConnectParams):
    livekit_api = api.LiveKitAPI()
    logger.info(f"Cleaning up existing inbound trunks for {params.account_id}...")

    rules = await livekit_api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())

    for trunk in rules.items:
        meta = json.loads(trunk.metadata or "{}")
        if meta.get("account_id", None) == params.account_id:
            logger.warning(
                f"Deleting inbound trunk for account: {params.account_id}",
            )
            await livekit_api.sip.delete_sip_trunk(
                delete=api.DeleteSIPTrunkRequest(sip_trunk_id=trunk.sip_trunk_id)
            )
    await livekit_api.aclose()


async def _cleanup_lk_dispatch_rules():
    livekit_api = api.LiveKitAPI()
    logger.info("Cleaning up existing dispatch rules...")

    trunks = await livekit_api.sip.list_sip_dispatch_rule(
        api.ListSIPDispatchRuleRequest()
    )
    for trunk in trunks.items:
        print("-- rule --", trunk.sip_dispatch_rule_id)
        await livekit_api.sip.delete_sip_dispatch_rule(
            api.DeleteSIPDispatchRuleRequest(
                sip_dispatch_rule_id=trunk.sip_dispatch_rule_id
            )
        )
    await livekit_api.aclose()


async def create_lk_inbound_trunk(params: ConnectParams, phone_numbers: list[str]):
    livekit_api = api.LiveKitAPI()
    phone_numbers = list(set(phone_numbers))

    trunk = api.SIPInboundTrunkInfo(
        name="Inbound LiveKit Trunk",
        numbers=phone_numbers,
        krisp_enabled=True,
        metadata=json.dumps({"account_id": params.account_id}),
    )

    # clean up existing trunks since we'll re-create them with newly added phone numbers
    await _cleanup_lk_inbound_trunks(params)

    request = api.CreateSIPInboundTrunkRequest(trunk=trunk)
    logger.debug(
        "Creating inbound trunk with command: lk sip inbound create inbound_trunk.json"
    )

    trunk = await livekit_api.sip.create_sip_inbound_trunk(request)
    logger.info(f"Created inbound trunk with SID: {trunk}")

    await livekit_api.aclose()
    return trunk.sip_trunk_id


async def create_lk_dispatch_rule() -> api.SIPDispatchRuleInfo:
    lkapi = api.LiveKitAPI()

    logger.info("Creating inbound dispatch rule: ...")
    request = api.CreateSIPDispatchRuleRequest(
        name="Inbound Dispatch Rule",
        rule=api.SIPDispatchRule(
            dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                room_prefix="call-",
            )
        ),
        room_config=api.RoomConfiguration(
            agents=[
                api.RoomAgentDispatch(
                    agent_name=settings.LIVEKIT_AGENT_NAME,
                )
            ]
        ),
    )

    # clean up to avoid duplicate dispatch rules
    await _cleanup_lk_dispatch_rules()
    dispatch = await lkapi.sip.create_sip_dispatch_rule(request)

    await lkapi.aclose()

    logger.info(f"Created dispatch rule with SID: {dispatch}")
    return dispatch


async def add_phone_to_twilio_trunk(
    client: Client, phone_number: str, livekit_trunk: TrunkInstance
):
    logger.info(
        f"Adding phone number {phone_number} to Twilio trunk: {livekit_trunk.sid}..."
    )
    incoming_phone_number = client.incoming_phone_numbers.list(
        phone_number=phone_number
    )

    if incoming_phone_number:
        phone_number_sid = incoming_phone_number[0].sid
        client.trunking.v1.trunks(str(livekit_trunk.sid)).phone_numbers.create(
            phone_number_sid=phone_number_sid  # type: ignore
        )
        logger.info(
            f"Associated phone number {phone_number} with trunk {livekit_trunk.sid}"
        )
    else:
        raise ValueError(
            f"Phone number {phone_number} not found in your Twilio account."
        )


async def configure_outbound_trunk(
    session: Session,
    twilio_trunk: TrunkInstance,
    params: ConnectParams,
    db_trunk: InboundTrunk,
):
    # create a livekit trunk for each trunk
    livekit_api = api.LiveKitAPI()
    trunk_phones = session.exec(
        select(PhoneNumber).where(PhoneNumber.trunk_id == db_trunk.trunk_id)
    ).all()

    phone_numbers = [trunk_phone.phone_number for trunk_phone in trunk_phones]
    meta = {"account_id": params.account_id}
    trunk = SIPOutboundTrunkInfo(
        name="Livekit Outbound Trunk",
        address=twilio_trunk.domain_name,
        numbers=phone_numbers,
        auth_username=db_trunk.sip_username,
        auth_password=db_trunk.sip_password,
        metadata=json.dumps(meta),
    )

    request = CreateSIPOutboundTrunkRequest(trunk=trunk)

    existing_trunks = await livekit_api.sip.list_sip_outbound_trunk(
        api.ListSIPOutboundTrunkRequest()
    )

    for existing_trunk in existing_trunks.items:
        existing_trunk_meta = json.loads(existing_trunk.metadata or "{}")
        if existing_trunk_meta.get("account_id", None) == params.account_id:
            logger.warning(
                f"Removing existing outbound trunk with SID: {existing_trunk.sip_trunk_id}"
            )
            await livekit_api.sip.delete_sip_trunk(
                delete=api.DeleteSIPTrunkRequest(
                    sip_trunk_id=existing_trunk.sip_trunk_id
                )
            )

    trunk = await livekit_api.sip.create_sip_outbound_trunk(request)
    logger.info(f"Successfully created: {trunk}")

    # save to database
    outbound_trunk = OutboundTrunk(
        inbound_trunk_id=db_trunk.trunk_id,
        account_id=params.account_id,
        livekit_sip_trunk_id=str(trunk.sip_trunk_id),
    )
    session.add(outbound_trunk)
    session.commit()

    await livekit_api.aclose()


# @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5))
async def connect_custom_twilio_to_livekit(session: Session, params: ConnectParams):
    sip_uri = os.environ["LIVEKIT_SIP_URI"]
    phone_number = params.phone_number
    client = Client(params.twilio_account_sid, params.twilio_auth_token)

    existing_trunks = client.trunking.v1.trunks.list()
    twilio_trunk = next(
        (trunk for trunk in existing_trunks if trunk.friendly_name == "LiveKit Trunk"),
        None,
    )

    def get_create_obj(twilio_trunk):
        inbound_trunk = InboundTrunk(
            trunk_id=str(twilio_trunk.sid),
            twilio_auth_token=params.twilio_auth_token,
            twilio_sid=params.twilio_account_sid,
            account_id=params.account_id,
            livekit_sip_trunk_id="",
        )
        return inbound_trunk

    if not twilio_trunk:
        sip_username = f"lk_sip_user_{os.urandom(3).hex()}"
        sip_password = generate_random_password()

        twilio_trunk = create_twilio_trunk(
            session=session,
            client=client,
            sip_uri=sip_uri,
        )

        inbound_trunk = get_create_obj(twilio_trunk)
        inbound_trunk.sip_password = sip_password
        inbound_trunk.sip_username = sip_username

        session.add(inbound_trunk)
        session.commit()
        session.refresh(inbound_trunk)
    else:
        logger.info("LiveKit Trunk already exists. Using the existing trunk.")
        logger.info(twilio_trunk.sid)

    await add_phone_to_twilio_trunk(
        client=client, phone_number=phone_number, livekit_trunk=twilio_trunk
    )

    # update the existing trunk in db
    db_trunk = session.exec(
        select(InboundTrunk).where(InboundTrunk.trunk_id == twilio_trunk.sid)
    ).first()

    if not db_trunk:
        logger.warning("LiveKit Trunk not found in database, syncing and updating...")

        inbound_trunk = get_create_obj(twilio_trunk)
        session.merge(inbound_trunk)
        session.commit()
        session.refresh(inbound_trunk)
        db_trunk = inbound_trunk

    # find all phone numbers in the database and add them to the livekit trunks
    results = session.exec(
        select(PhoneNumber).where(PhoneNumber.trunk_id == db_trunk.trunk_id)
    )
    phone_numbers = [result.phone_number for result in results]
    if len(phone_numbers) == 0:
        logger.warning(
            f"No phone numbers found in database, adding phone number: {phone_number}"
        )

    # add this new phone number into the list of all known phone numbers
    # that livekit trunk should have
    phone_numbers.append(phone_number)
    phone_numbers = list(set(phone_numbers))

    assert db_trunk is not None, "db trunk can't be none"

    new_trunk_id = await create_lk_inbound_trunk(params, phone_numbers)
    if new_trunk_id:
        logger.info(f"Creating dispatch rule for inbound trunk: {new_trunk_id}")

        await create_lk_dispatch_rule()

        # add this number phone number to database
        phone_number = PhoneNumber(
            phone_number=phone_number, trunk_id=db_trunk.trunk_id
        )
        session.merge(phone_number)
        session.commit()

        # update the inbound trunk
        db_trunk.livekit_sip_trunk_id = new_trunk_id
        session.merge(db_trunk)
        session.commit()
    else:
        logger.error("Failed to create inbound trunk.")

    await configure_outbound_trunk(
        session=session,
        db_trunk=db_trunk,
        twilio_trunk=twilio_trunk,
        params=params,
    )
    logger.info("Done - no news is good news")


if __name__ == "__main__":
    sqlite_file_name = "trunk.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, echo=True)

    def create_db_and_tables():
        SQLModel.metadata.create_all(engine)

    session = Session(engine)
    create_db_and_tables()

    params = ConnectParams(
        phone_number=os.environ["TWILIO_PHONE_NUMBER"],
        twilio_account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        twilio_auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        account_id="test-account-id",
    )
    asyncio.run(connect_custom_twilio_to_livekit(session, params))

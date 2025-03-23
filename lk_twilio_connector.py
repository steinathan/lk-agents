import asyncio
import os
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, create_engine, select
from twilio.rest import Client
from twilio.rest.trunking.v1.trunk import TrunkInstance
from app.core.config import settings

from livekit import api
from livekit.protocol.sip import ListSIPInboundTrunkRequest

from app.lk_connector.models import InboundTrunk, PhoneNumber


load_dotenv(dotenv_path=".env.local")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


class ConnectParams(BaseModel):
    phone_number: str
    twilio_auth_token: str
    twilio_account_sid: str
    account_id: str


def create_twilio_trunk(session: Session, client: Client, sip_uri) -> TrunkInstance:
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


async def _cleanup_lk_inbound_trunks():
    livekit_api = api.LiveKitAPI()
    logger.info("Cleaning up existing inbound trunks...")

    rules = await livekit_api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())

    for trunk in rules.items:
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


async def create_lk_inbound_trunk(phone_numbers: list[str]):
    livekit_api = api.LiveKitAPI()
    phone_numbers = list(set(phone_numbers))

    trunk = api.SIPInboundTrunkInfo(
        name="Inbound LiveKit Trunk",
        numbers=phone_numbers,
        krisp_enabled=True,
    )

    # clean up existing trunks since we'll re-create them with newly added phone numbers
    await _cleanup_lk_inbound_trunks()

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


async def connect_custom_twilio_to_livekit(session: Session, params: ConnectParams):
    sip_uri = os.environ["LIVEKIT_SIP_URI"]
    phone_number = params.phone_number
    client = Client(params.twilio_account_sid, params.twilio_auth_token)

    existing_trunks = client.trunking.v1.trunks.list()
    livekit_trunk = next(
        (trunk for trunk in existing_trunks if trunk.friendly_name == "LiveKit Trunk"),
        None,
    )

    def get_create_obj(livekit_trunk):
        inbound_trunk = InboundTrunk(
            trunk_id=str(livekit_trunk.sid),
            twilio_auth_token=params.twilio_auth_token,
            twilio_sid=params.twilio_account_sid,
            account_id=params.account_id,
        )
        return inbound_trunk

    if not livekit_trunk:
        livekit_trunk = create_twilio_trunk(
            session=session, client=client, sip_uri=sip_uri
        )
        inbound_trunk = get_create_obj(livekit_trunk)
        session.add(inbound_trunk)
        session.commit()
        session.refresh(inbound_trunk)
    else:
        logger.info("LiveKit Trunk already exists. Using the existing trunk.")
        logger.info(livekit_trunk.sid)

    await add_phone_to_twilio_trunk(
        client=client, phone_number=phone_number, livekit_trunk=livekit_trunk
    )

    # update the existing trunk in db
    db_trunk = session.exec(
        select(InboundTrunk).where(InboundTrunk.trunk_id == livekit_trunk.sid)
    ).first()

    if not db_trunk:
        logger.warning("LiveKit Trunk not found in database, syncing and updating...")

        inbound_trunk = get_create_obj(livekit_trunk)
        session.merge(inbound_trunk)
        session.commit()
        session.refresh(inbound_trunk)
        db_trunk = inbound_trunk

    # find all phone numbers in the database and add them to the livekit trunks
    results = session.exec(select(PhoneNumber))
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

    new_trunk_id = await create_lk_inbound_trunk(phone_numbers)
    if new_trunk_id:
        logger.info(f"Creating dispatch rule for inbound trunk: {new_trunk_id}")

        await create_lk_dispatch_rule()

        # add this number phone number to database
        phone_number = PhoneNumber(
            phone_number=phone_number, trunk_id=db_trunk.trunk_id
        )
        session.merge(phone_number)
        session.commit()
    else:
        logger.error("Failed to create inbound trunk.")

    logger.info("Done - no news is good news")


if __name__ == "__main__":
    sqlite_file_name = "trunk.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"

    engine = create_engine(sqlite_url, echo=True)

    session = Session(engine)
    create_db_and_tables()
    params = ConnectParams(
        phone_number=os.environ["TWILIO_PHONE_NUMBER"],
        twilio_account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        twilio_auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        account_id="test-account-id",
    )
    asyncio.run(connect_custom_twilio_to_livekit(session, params))

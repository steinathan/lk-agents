import asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
from loguru import logger
from sqlmodel import Field, SQLModel, Session, create_engine, select
from twilio.rest import Client
from app.core.config import settings

from livekit import api
from livekit.protocol.sip import ListSIPInboundTrunkRequest


load_dotenv(dotenv_path=".env.local")


class InboundTrunk(SQLModel, table=True):
    __tablename__ = "inbound_trunks"  # type: ignore
    trunk_id: str = Field(primary_key=True)

    livekit_sip_trunk_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class PhoneNumber(SQLModel, table=True):
    __tablename__ = "phone_numbers"  # type: ignore
    phone_number: str = Field(primary_key=True)
    trunk_id: str = Field(default=None, foreign_key="inbound_trunks.trunk_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


sqlite_file_name = "trunk.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


create_db_and_tables()


def get_env_var(var_name):
    value = os.getenv(var_name)
    if value is None:
        logger.error(f"Environment variable '{var_name}' not set.")
        exit(1)
    return value


def create_twilio_trunk(session: Session, client, sip_uri):
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
    inbound_trunk = InboundTrunk(trunk_id=str(trunk.sid))
    session.add(inbound_trunk)
    session.commit()
    session.refresh(inbound_trunk)

    return trunk


async def create_lk_inbound_trunk(phone_numbers: list[str]):
    livekit_api = api.LiveKitAPI()
    phone_numbers = list(set(phone_numbers))

    trunk = api.SIPInboundTrunkInfo(
        name="Inbound LiveKit Trunk",
        numbers=phone_numbers,
        krisp_enabled=True,
    )

    request = api.CreateSIPInboundTrunkRequest(trunk=trunk)
    logger.debug(
        "Creating inbound trunk with command: lk sip inbound create inbound_trunk.json"
    )

    trunk = await livekit_api.sip.create_sip_inbound_trunk(request)
    logger.info(f"Created inbound trunk with SID: {trunk}")

    await livekit_api.aclose()
    return trunk.sip_trunk_id


async def create_lk_dispatch_rule(trunk_sids: list[str]):
    lkapi = api.LiveKitAPI()

    request = api.CreateSIPDispatchRuleRequest(
        name="Inbound Dispatch Rule",
        trunk_ids=trunk_sids,
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
    dispatch = await lkapi.sip.create_sip_dispatch_rule(request)

    await lkapi.aclose()

    logger.info(f"Created dispatch rule with SID: {dispatch}")
    return dispatch


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


async def cleanup():
    """This is called to remove all rules and trunks created, since they'll be re-created with updated information"""
    await asyncio.gather(_cleanup_lk_inbound_trunks(), _cleanup_lk_dispatch_rules())


async def main():
    with Session(engine) as session:
        print("Creating inbound trunk...", os.environ.get("TWILIO_ACCOUNT_SID"))

        await cleanup()
        account_sid = get_env_var("TWILIO_ACCOUNT_SID")
        auth_token = get_env_var("TWILIO_AUTH_TOKEN")
        phone_number = get_env_var("TWILIO_PHONE_NUMBER")
        sip_uri = get_env_var("LIVEKIT_SIP_URI")

        client = Client(account_sid, auth_token)

        existing_trunks = client.trunking.v1.trunks.list()
        livekit_trunk = next(
            (
                trunk
                for trunk in existing_trunks
                if trunk.friendly_name == "LiveKit Trunk"
            ),
            None,
        )
        if not livekit_trunk:
            livekit_trunk = create_twilio_trunk(session, client, sip_uri)
        else:
            logger.info("LiveKit Trunk already exists. Using the existing trunk.")
            logger.info(livekit_trunk.sid)

        # update the existing trunk in db
        db_trunk = session.exec(
            select(InboundTrunk).where(InboundTrunk.trunk_id == livekit_trunk.sid)
        ).first()

        if not db_trunk:
            logger.warning(
                "LiveKit Trunk not found in database, syncing and updating..."
            )
            updated_trunk = InboundTrunk(trunk_id=str(livekit_trunk.sid))
            session.add(updated_trunk)
            session.commit()
            session.refresh(updated_trunk)
            db_trunk = updated_trunk

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

        assert db_trunk is not None, "db trunk can't be none"

        new_trunk_id = await create_lk_inbound_trunk(phone_numbers)
        if new_trunk_id:
            logger.info(f"Creating dispatch rule for inbound trunk: {new_trunk_id}")

            # update the livekit dispatch rule into the database
            db_trunk.livekit_sip_trunk_id = new_trunk_id
            session.add(db_trunk)
            session.commit()
            session.refresh(db_trunk)

            # find all dispatch rules in database and add to livekit
            trunks_data = session.exec(select(InboundTrunk))
            lk_trunk_sids = [result.livekit_sip_trunk_id for result in trunks_data]

            # finnaly, run the cmd to register json into livekit
            await create_lk_dispatch_rule(lk_trunk_sids)  # type: ignore

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
    asyncio.run(main())

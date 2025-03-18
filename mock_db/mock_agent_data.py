import os

from app.agent.schema import AgentSettings

greg_agent = {
    "greeting_message": "This is SuperTrans... how can I help you?",
    "system_prompt": """
You are a **friendly and efficient shuttle booking agent for SuperTrans**. Your job is to help customers **book rides, check reservations, handle inquiries, and provide updates**. Keep responses **polite, clear, and natural**, ensuring a smooth booking experience.

#### What You Do:

1. **Book a Shuttle**
   - Ask for **travel date, pickup location, and drop-off (airport, home, etc.)**.
   - Confirm **flight details** (airline, flight number, departure/arrival time).
   - Ask if they need a **return trip** and collect details.
   - Offer **payment options** (cash or card) and process securely.
   - Inform them when they’ll receive their **pickup time confirmation**.

2. **Check or Modify a Reservation**
   - Look up existing **bookings using name or phone number**.
   - Provide **pickup time, location, and any changes**.
   - Reschedule if needed (date, time, or address changes).

3. **Handle Cancellations**
   - Ask for **reservation details (name, phone, or reference number)**.
   - Confirm cancellation and mention any refund policies.

4. **Provide General Assistance**
   - Answer common questions about shuttle schedules, pricing, or policies.
   - Ensure the conversation is **easy to follow** for all customers.

#### Tone & Style:
- **Polite and professional** (e.g., "I'd be happy to assist you!").
- **Brief but informative** responses, avoiding unnecessary complexity.
- **Conversational and natural**, keeping the process smooth and engaging.

---

### **Full Conversation Examples**

#### **Booking a Shuttle**
Customer: "Hello, I need a shuttle to Newark Airport on February 28th."  
Agent: "Sure! What time does your flight depart?"  
Customer: "It leaves at 7 PM."  
Agent: "Got it. What airline are you flying with?"  
Customer: "United Airlines."  
Agent: "Thanks! And what's your pickup address?"  
Customer: "7069 Clover Lane."  
Agent: "Perfect! Do you need a return trip?"  
Customer: "Yes, I'm coming back on March 20th, arriving at 1:35 PM."  
Agent: "Great. Could you provide the flight number for your return?"  
Customer: "It's United Airlines flight 0995."  
Agent: "Thank you. Will you be paying with cash or card?"  
Customer: "Card."  
Agent: "Alright, I'll process that now. You'll receive a call on Thursday with your exact pickup time. Anything else I can help with?"  
Customer: "No, that's all. Thank you!"  
Agent: "You're welcome! Have a great day!"  

---

#### **Checking a Reservation**
Customer: "Hi, what time is my shuttle on Saturday?"  
Agent: "I'd be happy to check! May I have your phone number?"  
Customer: "Sure, it's 215-594-3119."  
Agent: "Thanks! I see you have a pickup scheduled at 4:30 PM from 7069 Clover Lane to Newark Airport. Is that correct?"  
Customer: "Yes, that's right. Just wanted to confirm."  
Agent: "You're all set! Let me know if you need anything else."  
Customer: "Nope, thanks!"  
Agent: "You're welcome! Safe travels."  

---

#### **Cancelling a Trip**
Customer: "I need to cancel my shuttle for March 20th."  
Agent: "I can help with that! Can you provide your name or reservation number?"  
Customer: "My name is John Smith."  
Agent: "Thank you. I see your reservation for March 20th, arriving at 1:35 PM. I’ll cancel it now. There’s no cancellation fee since it's more than 24 hours in advance."  
Customer: "Great, thanks!"  
Agent: "You're all set! Let me know if you need to rebook in the future."  
Customer: "Will do!"  
Agent: "Have a great day!"  
---
""",
    "agent_name": "Greg",
    "agent_phone": os.getenv("TEST_AGENT_PHONE"),
    "agent_id": "agent_greg",
    "interaction_id": "inter_greg",
    "synth_provider": "google",
    "language_code": "en",
    "voices": [{"voice_id": "en-US-Journey-D", "language_code": "en"}],
    "transiber_provider": "google",
    "model_provider": "google",
    "model": "gemini-2.0-flash-001",
    "temperature": 0.7,
    "customer_name": "Navi Customer",
    "customer_email": "navi@example.com",
    "customer_phone": "+1234567890",
    "has_existing_ride": True,
    "knowledgebase_ids": ["kb_greg"],
    "actions": [],
}

sandra_agent = {
    "greeting_message": "Hi, I'm Sandra. How can I help you today?",
    "system_prompt": "You are a ride service assistant, providing customer support.",
    "agent_name": "Sandra",
    "agent_phone": None,
    "agent_id": "agent_sandra",
    "interaction_id": "inter_sandra",
    "synth_provider": "google",
    "language_code": "en",
    "voices": [{"voice_id": "en-US-Journey-D", "language_code": "en"}],
    "transiber_provider": "google",
    "model_provider": "google",
    "model": "gemini-2.0-flash-001",
    "temperature": 0.7,
    "customer_name": "Sandra Customer",
    "customer_email": "sandra@example.com",
    "customer_phone": "+1987654321",
    "has_existing_ride": False,
    "knowledgebase_ids": ["kb_sandra"],
    "actions": [],
}

mike_agent = {
    "greeting_message": "Hey there, I’m Mike! Need any help?",
    "system_prompt": "You are a virtual assistant helping users with their rides.",
    "agent_name": "Mike",
    "agent_phone": "+2349538882",
    "agent_id": "agent_mike",
    "interaction_id": "inter_mike",
    "synth_provider": "google",
    "language_code": "en",
    "voices": [{"voice_id": "en-US-Journey-D", "language_code": "en"}],
    "transiber_provider": "google",
    "model_provider": "google",
    "model": "gemini-2.0-flash-001",
    "temperature": 0.7,
    "customer_name": "Mike Customer",
    "customer_email": "mike@example.com",
    "customer_phone": "+1122334455",
    "has_existing_ride": True,
    "knowledgebase_ids": ["kb_mike"],
    "actions": [],
}

lisa_agent = {
    "greeting_message": "Hi, I’m Lisa. How can I assist you?",
    "system_prompt": "You are a helpful assistant guiding customers in their ride experiences.",
    "agent_name": "Lisa",
    "agent_phone": os.getenv("TEST_AGENT_PHONE"),
    "agent_id": "agent_lisa",
    "interaction_id": "inter_lisa",
    "synth_provider": "google",
    "language_code": "en",
    "voices": [{"voice_id": "en-US-Journey-D", "language_code": "en"}],
    "transiber_provider": "google",
    "model_provider": "google",
    "model": "gemini-2.0-flash-001",
    "temperature": 0.7,
    "customer_name": "Lisa Customer",
    "customer_email": "lisa@example.com",
    "customer_phone": "+1555666777",
    "has_existing_ride": False,
    "knowledgebase_ids": ["kb_lisa"],
    "actions": [],
}

david_agent = {
    "greeting_message": "Hello, I'm David. How can I help?",
    "system_prompt": "You are an AI agent assisting users with their ride services.",
    "agent_name": "David",
    "agent_phone": os.getenv("TEST_AGENT_PHONE"),
    "agent_id": "agent_david",
    "interaction_id": "inter_david",
    "synth_provider": "google",
    "language_code": "en",
    "voices": [{"voice_id": "en-US-Journey-D", "language_code": "en"}],
    "transiber_provider": "google",
    "model_provider": "google",
    "model": "gemini-2.0-flash-001",
    "temperature": 0.7,
    "customer_name": "David Customer",
    "customer_email": "david@example.com",
    "customer_phone": "+1444555666",
    "has_existing_ride": True,
    "knowledgebase_ids": ["kb_david"],
    "actions": [],
}

agents = [greg_agent, sandra_agent, mike_agent, lisa_agent, david_agent]


async def find_test_agent(
    interaction_id=None, phone_number=None, agent_id=None
) -> AgentSettings | None:
    for agent in agents:
        if (
            (interaction_id and agent["interaction_id"] == interaction_id)
            or (phone_number and agent["agent_phone"] == phone_number)
            or (agent_id and agent["agent_id"] == agent_id)
        ):
            return AgentSettings.model_validate(agent)
    return None

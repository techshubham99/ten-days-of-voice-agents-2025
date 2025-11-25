# zoho_sdr_agent.py
import logging
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    metrics,
    tokenize,
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("zoho_sdr")

load_dotenv(".env.local")

# ---------- Zoho Company Content ---------- #

ZOHO_FAQ = {
    "company_info": {
        "name": "Zoho Corporation",
        "description": "Zoho is an Indian multinational technology company that makes computer software and web-based business tools. It offers a comprehensive suite of business, productivity, and collaboration applications.",
        "founded": "1996",
        "headquarters": "Chennai, Tamil Nadu, India"
    },
    "products": {
        "main_products": [
            "Zoho CRM - Customer relationship management",
            "Zoho Books - Accounting software", 
            "Zoho Desk - Customer service software",
            "Zoho Mail - Business email",
            "Zoho Workplace - Collaboration suite",
            "Zoho Analytics - Business intelligence"
        ]
    },
    "pricing": {
        "crm": {
            "free": "Up to 3 users, basic features",
            "standard": "₹1,400/user/month - Sales force automation, marketing automation",
            "professional": "₹2,800/user/month - Advanced features, custom modules",
            "enterprise": "₹4,200/user/month - AI-powered analytics, advanced security"
        },
        "books": {
            "free": "Up to 1 user, 1000 invoices/year",
            "standard": "₹4,999/organisation/month - Up to 3 users",
            "professional": "₹9,999/organisation/month - Up to 10 users",
            "premium": "₹19,999/organisation/month - Unlimited users"
        }
    },
    "faq": [
        {
            "question": "What does Zoho do?",
            "answer": "Zoho provides a comprehensive suite of business software including CRM, accounting, email, collaboration tools, and more to help businesses manage their operations efficiently."
        },
        {
            "question": "Who is Zoho for?",
            "answer": "Zoho serves businesses of all sizes - from startups and small businesses to large enterprises across various industries."
        },
        {
            "question": "Do you have a free tier?",
            "answer": "Yes, most Zoho products offer free plans with limited features. For example, Zoho CRM has a free plan for up to 3 users, and Zoho Books has a free plan for small businesses."
        },
        {
            "question": "How much does Zoho CRM cost?",
            "answer": "Zoho CRM starts with a free plan for up to 3 users. Paid plans start at ₹1,400 per user per month for the Standard plan, ₹2,800 for Professional, and ₹4,200 for Enterprise."
        },
        {
            "question": "What is Zoho One?",
            "answer": "Zoho One is an all-in-one suite that includes over 45 integrated applications for your entire business at ₹2,500 per user per month when billed annually."
        },
        {
            "question": "Can I integrate Zoho with other tools?",
            "answer": "Yes, Zoho offers extensive integration capabilities with popular third-party applications as well as APIs for custom integrations."
        },
        {
            "question": "Is there a trial period?",
            "answer": "Yes, most Zoho products offer a 15-day free trial for their paid plans so you can explore all features before committing."
        },
        {
            "question": "Do you offer support?",
            "answer": "Yes, we offer 24/5 email and chat support for all paid plans, along with comprehensive documentation and community forums."
        }
    ]
}

LEAD_FIELDS = [
    "name",
    "company", 
    "email",
    "role",
    "use_case",
    "team_size",
    "timeline"
]

# ---------- Murf TTS voices ---------- #

TTS_SDR = murf.TTS(
    voice="en-US-matthew",  # Professional SDR voice
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

# ---------- SDR Agent ---------- #

class ZohoSDRAgent(Agent):
    """
    Sales Development Representative agent for Zoho Corporation.
    Handles FAQ questions and lead capture.
    """

    def __init__(self, **kwargs):
        instructions = f"""
You are a friendly and professional Sales Development Representative for Zoho Corporation.

COMPANY INFORMATION:
- Name: {ZOHO_FAQ['company_info']['name']}
- Description: {ZOHO_FAQ['company_info']['description']}
- Headquarters: {ZOHO_FAQ['company_info']['headquarters']}

YOUR ROLE:
1. Greet visitors warmly and introduce yourself as a Zoho SDR
2. Ask what brought them here and what they're working on
3. Use the FAQ knowledge to answer questions accurately
4. Naturally collect lead information during the conversation
5. End the call professionally when the user indicates they're done

LEAD INFORMATION TO COLLECT:
- Name
- Company
- Email
- Role
- Use case (what they want to use Zoho for)
- Team size
- Timeline (now / soon / later)

FAQ CONTENT (use this for answering questions):
{json.dumps(ZOHO_FAQ['faq'], indent=2)}

CONVERSATION GUIDELINES:
- Be conversational and friendly
- Ask one question at a time
- Don't make up information - if you don't know, say so
- Gently steer conversation back to understanding their needs
- When user says they're done, provide a brief summary and thank them
- Use the lead collection tools to systematically gather information

ENDING THE CALL:
When user says things like "that's all", "I'm done", "thanks for your help", 
give a brief verbal summary of what you discussed and end the call.
"""
        super().__init__(instructions=instructions, tts=TTS_SDR, **kwargs)

    async def on_enter(self) -> None:
        # Start with a warm greeting and introduction
        await self.session.generate_reply(
            instructions=(
                "Greet the visitor warmly as a Zoho Sales Development Representative. "
                "Introduce yourself briefly and ask what brought them to Zoho today "
                "and what they're currently working on."
            )
        )

    # ---------- Lead Collection Tools ---------- #

    @function_tool()
    async def collect_name(self, context: RunContext, name: str) -> str:
        """Collect the visitor's name"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["name"] = name
        sdr_state["collected_fields"].add("name")
        return f"Thank you, {name}. Nice to meet you!"

    @function_tool()
    async def collect_company(self, context: RunContext, company: str) -> str:
        """Collect the visitor's company name"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["company"] = company
        sdr_state["collected_fields"].add("company")
        return f"Great, {company}. What industry are you in?"

    @function_tool()
    async def collect_email(self, context: RunContext, email: str) -> str:
        """Collect the visitor's email address"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["email"] = email
        sdr_state["collected_fields"].add("email")
        return f"Perfect, I've got {email} as your contact."

    @function_tool()
    async def collect_role(self, context: RunContext, role: str) -> str:
        """Collect the visitor's role in their company"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["role"] = role
        sdr_state["collected_fields"].add("role")
        return f"Understood, as a {role}. What are you looking to achieve with Zoho?"

    @function_tool()
    async def collect_use_case(self, context: RunContext, use_case: str) -> str:
        """Collect what the visitor wants to use Zoho for"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["use_case"] = use_case
        sdr_state["collected_fields"].add("use_case")
        return f"Thanks for sharing that you need {use_case}. How large is your team?"

    @function_tool()
    async def collect_team_size(self, context: RunContext, team_size: str) -> str:
        """Collect the visitor's team size"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["team_size"] = team_size
        sdr_state["collected_fields"].add("team_size")
        return f"Got it, {team_size} people. When are you looking to implement - now, soon, or later?"

    @function_tool()
    async def collect_timeline(self, context: RunContext, timeline: str) -> str:
        """Collect the implementation timeline"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        sdr_state["lead_data"]["timeline"] = timeline
        sdr_state["collected_fields"].add("timeline")
        
        # Check if we have all required fields
        missing = set(LEAD_FIELDS) - sdr_state["collected_fields"]
        if not missing:
            return f"Perfect! I have all the information I need. Is there anything else you'd like to know about Zoho?"
        else:
            return f"Thanks for the timeline. Is there anything else I can help you with today?"

    @function_tool()
    async def end_call(self, context: RunContext) -> str:
        """End the call and save lead data"""
        session = context.session
        sdr_state = _ensure_sdr_state(session)
        
        if sdr_state["lead_data"]:
            filename = _save_lead_data(sdr_state["lead_data"])
            summary = _generate_summary(sdr_state["lead_data"])
            return f"Thank you for speaking with me! Here's a quick summary: {summary}. I've saved your information and our team will follow up shortly. Have a great day!"
        else:
            return "Thank you for your interest in Zoho! If you have any more questions, feel free to reach out. Have a great day!"

# ---------- SDR state helpers ---------- #

def _ensure_sdr_state(session) -> Dict[str, Any]:
    """Ensure SDR state exists in session userdata"""
    ud = session.userdata
    sdr = ud.get("sdr")
    if not isinstance(sdr, dict):
        sdr = {
            "lead_data": {},
            "collected_fields": set()
        }
        ud["sdr"] = sdr
    return sdr

def _save_lead_data(lead_data: Dict[str, Any]) -> str:
    """Save lead data to JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"zoho_lead_{timestamp}.json"
    
    lead_record = {
        "timestamp": datetime.now().isoformat(),
        "lead_data": lead_data,
        "conversation_summary": _generate_summary(lead_data)
    }
    
    with open(filename, 'w') as f:
        json.dump(lead_record, f, indent=2)
    
    logger.info(f"Lead data saved to {filename}")
    return filename

def _generate_summary(lead_data: Dict[str, Any]) -> str:
    """Generate a summary of the lead"""
    name = lead_data.get('name', 'Unknown')
    company = lead_data.get('company', 'Not provided')
    role = lead_data.get('role', 'Not provided')
    use_case = lead_data.get('use_case', 'Not provided')
    team_size = lead_data.get('team_size', 'Not provided')
    timeline = lead_data.get('timeline', 'Not provided')
    
    return (f"Lead from {name} at {company} ({role}) interested in {use_case}. "
            f"Team size: {team_size}. Timeline: {timeline}.")

# ---------- Prewarm ---------- #

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ---------- #

async def entrypoint(ctx: JobContext):
    # Logging context
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        tts=TTS_SDR,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Initialize userdata; SDR state lives under session.userdata["sdr"]
    session.userdata = {}

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start with Zoho SDR Agent
    await session.start(
        agent=ZohoSDRAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
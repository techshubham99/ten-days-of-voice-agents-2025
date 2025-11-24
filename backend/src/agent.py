import logging
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

DATA_FILE = "session_history.json"
LOG_FILE = "wellog.json"


# ------------------ Persistence Helper ------------------ #

def write_json(filename, entry):
    """Safely append to a JSON list file."""
    data = []
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []

    data.append(entry)

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def load_last_session():
    if not os.path.exists(DATA_FILE):
        return None
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data[-1] if data else None
    except:
        return None


def log_message(role: str, message: str):
    write_json(LOG_FILE, {
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "message": message.strip()
    })


# ------------------ Agent ------------------ #

class WellMurf(Agent):
    def __init__(self):
        super().__init__(
            instructions="""
You are a calm and reliable health companion.

Your job:
- Speak naturally and simply.
- Ask only one question at a time.
- Ask in this sequence:
  1) Symptoms
  2) Duration
  3) Severity (mild / moderate / severe)
  4) Possible triggers (sleep, food, stress, exercise, etc.)

After collecting answers:
- Summarize cleanly and ask if they want general wellness tips or continue conversation.

Rules:
- Never diagnose or recommend treatment.
- If asked for medical advice, gently tell them to consult a medical professional.
- Keep tone calm, human, and neutral.
"""
        )

        self.reset()
        self.last_entry = load_last_session()

    def reset(self):
        self.state = {
            "intro": False,
            "symptoms": None,
            "duration": None,
            "severity": None,
            "trigger": None,
            "done": False
        }

    async def send(self, ctx, text: str):
        log_message("agent", text)
        return await ctx.send_message(text)

    async def on_user_message(self, ctx: AgentSession, message: str):
        msg = message.strip()
        log_message("user", msg)

        # First time greeting
        if not self.state["intro"]:
            self.state["intro"] = True

            if self.last_entry:
                return await self.send(
                    ctx,
                    f"Welcome back. Last time you mentioned '{self.last_entry['symptoms']}' with severity '{self.last_entry['severity']}'. How are you feeling today?"
                )
            return await self.send(ctx, "Let's begin. What symptom are you experiencing?")

        # Step 1 — Symptoms
        if not self.state["symptoms"]:
            self.state["symptoms"] = msg
            return await self.send(ctx, "How long have you been experiencing this?")

        # Step 2 — Duration
        if not self.state["duration"]:
            self.state["duration"] = msg
            return await self.send(ctx, "Would you describe it as mild, moderate, or severe?")

        # Step 3 — Severity
        if not self.state["severity"]:
            self.state["severity"] = msg
            return await self.send(ctx, "Got it. Any idea what may have triggered it? Maybe stress, sleep, food, exercise or something else?")

        # Step 4 — Trigger and Save
        if not self.state["trigger"]:
            self.state["trigger"] = msg
            self.state["done"] = True

            entry = {
                "timestamp": datetime.now().isoformat(),
                "symptoms": self.state["symptoms"],
                "duration": self.state["duration"],
                "severity": self.state["severity"],
                "trigger": self.state["trigger"]
            }

            write_json(DATA_FILE, entry)

            summary = (
                f"Here's what I understood: you're experiencing '{entry['symptoms']}', "
                f"for '{entry['duration']}', at a '{entry['severity']}' level, "
                f"and you think it may be related to '{entry['trigger']}'."
            )

            return await self.send(ctx, summary + " Would you like general wellness tips or continue talking?")

        # After completion
        return await self.send(ctx, "Alright. I'm here. What would you like next?")


# ------------------ LiveKit Runtime ------------------ #

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=murf.TTS(
            voice="en-US-matthew",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage = metrics.UsageCollector()

    @session.on("metrics_collected")
    def track(ev: MetricsCollectedEvent):
        usage.collect(ev.metrics)

    ctx.add_shutdown_callback(lambda: logger.info(usage.get_summary()))

    await session.start(
        agent=WellMurf(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))

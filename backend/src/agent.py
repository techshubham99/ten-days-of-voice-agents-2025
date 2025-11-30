# agent.py - E-commerce Voice Agent for Day 9
import logging
import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
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

logger = logging.getLogger("ecommerce_agent")

load_dotenv(".env.local")

# ---------- ACP-Inspired Product Catalog ---------- #

PRODUCTS = [
    {
        "id": "mug-001",
        "name": "Stoneware Coffee Mug",
        "description": "Premium ceramic mug perfect for coffee or tea",
        "price": 800,
        "currency": "INR",
        "category": "mug",
        "color": "white",
        "size": "standard"
    },
    {
        "id": "mug-002", 
        "name": "Blue Ceramic Mug",
        "description": "Vibrant blue colored ceramic mug",
        "price": 750,
        "currency": "INR",
        "category": "mug",
        "color": "blue",
        "size": "standard"
    },
    {
        "id": "tshirt-001",
        "name": "Cotton T-Shirt",
        "description": "Soft 100% cotton t-shirt",
        "price": 899,
        "currency": "INR", 
        "category": "clothing",
        "color": "black",
        "size": "M"
    },
    {
        "id": "tshirt-002",
        "name": "Premium Polo Shirt",
        "description": "High-quality polo shirt",
        "price": 1200,
        "currency": "INR",
        "category": "clothing",
        "color": "navy",
        "size": "L"
    },
    {
        "id": "hoodie-001",
        "name": "Black Hoodie",
        "description": "Comfortable cotton hoodie",
        "price": 1999,
        "currency": "INR",
        "category": "clothing", 
        "color": "black",
        "size": "M"
    },
    {
        "id": "hoodie-002",
        "name": "Gray Hoodie",
        "description": "Warm fleece hoodie",
        "price": 1799,
        "currency": "INR",
        "category": "clothing",
        "color": "gray",
        "size": "L"
    }
]

# ---------- Order Management ---------- #

ORDERS = []

def list_products(filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """ACP-inspired product listing with filtering"""
    filtered_products = PRODUCTS.copy()
    
    if filters:
        if 'category' in filters:
            filtered_products = [p for p in filtered_products if p['category'] == filters['category']]
        if 'max_price' in filters:
            filtered_products = [p for p in filtered_products if p['price'] <= filters['max_price']]
        if 'color' in filters:
            filtered_products = [p for p in filtered_products if p['color'] == filters['color']]
    
    return filtered_products

def create_order(line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ACP-inspired order creation"""
    order_id = str(uuid.uuid4())[:8]
    total = 0
    items_with_details = []
    
    for item in line_items:
        product = next((p for p in PRODUCTS if p['id'] == item['product_id']), None)
        if product:
            item_total = product['price'] * item['quantity']
            total += item_total
            items_with_details.append({
                'product_id': product['id'],
                'name': product['name'],
                'quantity': item['quantity'],
                'unit_price': product['price'],
                'total_price': item_total
            })
    
    order = {
        'id': order_id,
        'items': items_with_details,
        'total': total,
        'currency': 'INR',
        'created_at': datetime.now().isoformat(),
        'status': 'CONFIRMED'
    }
    
    ORDERS.append(order)
    
    # Save to JSON file
    save_order_to_file(order)
    
    return order

def save_order_to_file(order: Dict[str, Any]):
    """Save order to JSON file"""
    filename = f"order_{order['id']}.json"
    with open(filename, 'w') as f:
        json.dump(order, f, indent=2)
    logger.info(f"Order saved to {filename}")

def get_last_order() -> Optional[Dict[str, Any]]:
    """Get the most recent order"""
    return ORDERS[-1] if ORDERS else None

# ---------- Murf TTS ---------- #

TTS_ECOMMERCE = murf.TTS(
    voice="en-US-matthew",
    style="Conversation",
    tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
    text_pacing=True,
)

# ---------- E-commerce Agent ---------- #

class EcommerceAgent(Agent):
    """
    ACP-inspired E-commerce Voice Agent
    """

    def __init__(self, **kwargs):
        instructions = """You are a helpful E-commerce Shopping Assistant following ACP principles.

YOUR ROLE:
- Help users browse products and place orders
- Use the available tools to search catalog and create orders
- Be concise and helpful

KEY BEHAVIORS:
- When user asks about products, use list_products with appropriate filters
- When user wants to buy, use create_order with product IDs and quantities
- Always confirm order details before placing
- Use get_last_order when user asks about their recent purchase

KEEP RESPONSES SHORT AND ACTION-ORIENTED."""
        super().__init__(instructions=instructions, tts=TTS_ECOMMERCE, **kwargs)

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Greet the customer briefly and let them know you can help them shop. "
                "Ask what they're looking for today."
            )
        )

    # ---------- ACP-Inspired Tools ---------- #

    @function_tool()
    async def list_products(self, context: RunContext, 
                          category: Optional[str] = None,
                          max_price: Optional[int] = None,
                          color: Optional[str] = None) -> str:
        """Browse products with filters - ACP catalog style"""
        filters = {}
        if category:
            filters['category'] = category
        if max_price:
            filters['max_price'] = max_price
        if color:
            filters['color'] = color
            
        products = list_products(filters)
        
        if not products:
            return "No products found matching your criteria."
        
        response = f"Found {len(products)} products:\n"
        for i, product in enumerate(products, 1):
            response += f"{i}. {product['name']} - ₹{product['price']} ({product['color']})\n"
        
        return response

    @function_tool()
    async def create_order(self, context: RunContext, 
                         product_id: str, 
                         quantity: int = 1) -> str:
        """Create an order - ACP order creation style"""
        line_items = [{"product_id": product_id, "quantity": quantity}]
        order = create_order(line_items)
        
        return (f"Order placed successfully! 🎉\n"
                f"Order ID: {order['id']}\n"
                f"Total: ₹{order['total']}\n"
                f"Status: {order['status']}")

    @function_tool()
    async def get_last_order(self, context: RunContext) -> str:
        """Get details of the most recent order"""
        order = get_last_order()
        if not order:
            return "No orders found."
        
        response = f"Your last order (ID: {order['id']}):\n"
        for item in order['items']:
            response += f"- {item['name']} x{item['quantity']} - ₹{item['total_price']}\n"
        response += f"Total: ₹{order['total']}\n"
        response += f"Status: {order['status']}"
        
        return response

# ---------- Prewarm ---------- #

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

# ---------- Entrypoint ---------- #

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=TTS_ECOMMERCE,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

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

    await session.start(
        agent=EcommerceAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
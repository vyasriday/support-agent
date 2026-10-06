from pydantic_ai import Agent, RunContext
from typing import Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

model = 'openai:gpt-5.5'
agent_name = "Support Agent"
instructions = '''You are a support assistant for our fictional online store.
Policy: unused items can be returned within 30 days of delievery.
Damaged items should be referred to a human support representative.
Answer briefly using this policy.
For order-status questions, use get_order before answering.
In no order number is provided, ask for it.
If the order is not found, ask the customer to verify the number.
Do not invent order details or claim to have performed the actions
'''


class SupportResponse(BaseModel):
    reply: str = Field(description="The response shown to the customer.")
    issue_type: Literal["return", "order_status", "damaged_item", "other"]
    needs_human: bool = Field(
        description="Whether this request requires human support")


@dataclass
class SupportDeps:
    customer_id: str
    orders: dict[str, dict[str, str]]


support_agent = Agent(model, instructions=instructions,
                      output_type=SupportResponse, deps_type=SupportDeps)

ORDERS: dict[str, dict[str, str]] = {
    "143": {"customer_id": "customer-1", "status": "shipped",
            "tracking_number": "TRACK-143"},
    "144": {"customer_id": "customer-2", "status": "delivered",
            "tracking_number": "TRACK-144"},
}


@support_agent.tool
def get_order(ctx: RunContext[SupportDeps], order_id: str) -> dict[str, str]:
    """Retrieve status and tracking for an order belonging to the current customer.
    Args:
        ctx:
        order_id (str): The order number supplied by the customer

    Returns:
        dict[str, str]: Returns information regarding a particular order based on order_id
    """
    print(f"[tool] Looking up order {order_id}")
    print(f"ctx.deps, {ctx.deps}")
    order = ctx.deps.orders.get(order_id)
    if order is None or order["customer_id"] != ctx.deps.customer_id:
        return {"error": "Order not found for the current customer"}
    return {
        "status": order["status"],
        "tracking_number": order["tracking_number"]
    }


question = input("> ")
deps = SupportDeps(customer_id="customer-2", orders=ORDERS)
result = support_agent.run_sync(question, deps=deps)
print(result.output.model_dump_json(indent=2))
# print(dir(result.output))

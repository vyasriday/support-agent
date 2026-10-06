from pydantic_ai import Agent
from typing import Literal
from pydantic import BaseModel, Field

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


support_agent = Agent(model, instructions=instructions,
                      output_type=SupportResponse)

ORDERS: dict[str, dict[str, str]] = {
    "143": {"status": "shipped", "tracking_number": "TRACK-143"},
    "144": {"status": "delievered", "tracking_number": "TRACK-144"}
}


@support_agent.tool_plain
def get_order(order_id: str) -> dict[str, str]:
    """Look up an order's status and tracking number
    Args:
        order_id (str): The order number supplied by the customer

    Returns:
        dict[str, str]: Returns information regarding a particular order based on order_id
    """
    print(f"[tool] Looking up order {order_id}")
    return ORDERS.get(order_id, {"error": "Order not found"})


question = input("> ")

result = support_agent.run_sync(question)

print(result.output.model_dump_json(indent=2))
# print(dir(result.output))

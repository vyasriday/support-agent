from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
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

# Generates __init__, __repr__, and __eq__ for this data container; does not validate types.


@dataclass
class SupportDeps:
    customer_id: str
    orders: dict[str, dict[str, str]]
    preferred_language: str = "English"


support_agent = Agent(model, instructions=instructions,
                      output_type=SupportResponse, deps_type=SupportDeps)

ORDERS: dict[str, dict[str, str]] = {
    "143": {"customer_id": "customer-1", "status": "shipped",
            "tracking_number": "TRACK-143"},
    "144": {"customer_id": "customer-2", "status": "delivered",
            "tracking_number": "TRACK-144"},
}


# Registers a model-requested tool; Pydantic AI supplies ctx, and the model supplies order_id.
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
    # print(f"ctx.deps, {ctx.deps}")
    order = ctx.deps.orders.get(order_id)
    if order is None or order["customer_id"] != ctx.deps.customer_id:
        return {"error": "Order not found for the current customer"}

    return {
        "status": order["status"],
        "tracking_number": order["tracking_number"]
    }


# Checks candidate outputs after schema validation; ModelRetry requests a corrected response.
@support_agent.output_validator
def validate_support_response(
        ctx: RunContext[SupportDeps],
        output: SupportResponse) -> SupportResponse:
    print(
        f"[validator] retry={ctx.retry}, "
        f"issue_type={output.issue_type}, "
        f"needs_human={output.needs_human}"
    )

    if output.issue_type == "damaged_item" and not output.needs_human:
        raise ModelRetry(
            "Damaged items require human support. "
            "Set needs_human=True and refer the customer to human suppport"
        )
    return output


# Registers guidance generated from deps for each run and sent to the model with static instructions.
@support_agent.instructions
def customer_preferences(ctx: RunContext[SupportDeps]) -> str:
    print(f"[instructions] language={ctx.deps.preferred_language}")
    return (
        f"Write the customer-facing reply in {ctx.deps.preferred_language}. "
        "Keep issue_type values exactly as defined in the output schema."
    )


deps = SupportDeps(customer_id="customer-2", orders=ORDERS,
                   preferred_language="English")
history: list[ModelMessage] = []
while True:
    question = input("> ").strip()
    if (question.lower() == "quit"):
        break
    if not question:
        continue
    try:
        result = support_agent.run_sync(
            question,
            deps=deps,
            message_history=history,
            usage_limits=UsageLimits(request_limit=2, tool_calls_limit=2)
        )
    except UsageLimitExceeded as error:
        print(f"[limit] {error}")
        continue
    except UnexpectedModelBehavior as error:
        print(f"[validation] {error}")
        continue
    print(result.output.model_dump_json(indent=2))
    usage = result.usage
    print(
        f"[usage] requests={usage.requests}, "
        f"input_tokens={usage.input_tokens}, "
        f"output_tokens={usage.output_tokens}"
    )

    history.extend(result.new_messages())


# result = support_agent.run_sync(question, deps=deps)
# print(result.output.model_dump_json(indent=2))
# history = result.all_messages()
# print(result.all_messages())
# print(dir(result.output))

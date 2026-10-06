from pydantic_ai import Agent
from dotenv import load_dotenv

model = 'openai:gpt-5.5'
agent_name = "Support Agent"
instructions = '''You are a support assistant for our fictional online store.
    Policy: unused items can be returned within 30 days of delivery.
    Damaged items should be referred to a human support representative.
    Answer briefly using this policy.
    You cannot access orders yet. Do not invent order details or claim
    to have performed actions. Ask for missing information when needed.'''

load_dotenv()

support_agent = Agent(model, instructions=instructions, output_type=str)

question = input("> ")

result = support_agent.run_sync(question)

print(result.output)

# Learning Pydantic AI: Support Agent

Build an order-support agent for a fictional online store, one concept at a time.
This is a learning project with fake data, not a production support system.

This log summarizes Lessons 1-8 and introduces Lesson 9, which has a pending
async checkpoint before its streaming exercise. It is updated after each lesson. Examples
are focused excerpts, not replacements for the complete application in [main.py](main.py).
Testing lessons are deferred while we explore more agent concepts.

## Contents

| Lesson | Topic | Main API |
| --- | --- | --- |
| [1](#lesson-1-your-first-agent) | Agent basics and model setup | `Agent`, `run_sync()` |
| [2](#lesson-2-structured-output) | Typed responses | `BaseModel`, `output_type` |
| [3](#lesson-3-function-tools) | Retrieving external information | `@agent.tool_plain` |
| [4](#lesson-4-dependencies-and-runcontext) | Resources, identity, and authorization | `deps`, `RunContext`, `@agent.tool` |
| [5](#lesson-5-output-validation-and-retries) | Business-rule validation | `@agent.output_validator`, `ModelRetry` |
| [6](#lesson-6-conversation-history) | Multi-turn conversations | `message_history`, `new_messages()` |
| [7](#lesson-7-dynamic-instructions) | Runtime guidance | `@agent.instructions` |
| [8](#lesson-8-usage-limits-and-error-handling) | Usage accounting and bounded runs | `UsageLimits`, `result.usage` |
| [9](#lesson-9-async-execution-and-structured-streaming) | Async execution; streaming preview | `async def`, `await`, `run()` |

## How The Pieces Fit Together

| Component | Responsibility in our agent | What it does not do |
| --- | --- | --- |
| OpenAI model | Interpret questions, request tools, and propose answers | Execute our Python functions or directly read `ORDERS` |
| Pydantic AI | Coordinate model requests, tools, dependencies, history, validation, and retries | Automatically enforce our store's policy or authenticate customers |
| Pydantic | Generate schemas and validate tool arguments and structured output | Establish factual correctness merely because the data has valid types |
| Our Python code | Check order ownership, retrieve records, and enforce explicit business rules | Guarantee that the model classifies every question correctly |
| Python dataclass | Group the resources supplied to a run | Automatically validate field types or send its values to the model |

The model proposes; Pydantic AI coordinates; Pydantic validates data contracts;
our Python code enforces business rules.

## Lesson 1: Your First Agent

**Goal:** Answer policy questions using a model and developer-written instructions.

- An LLM generates responses from supplied context and can produce plausible errors.
- An agent can use a model to choose among available tools and produce a final answer.
- An `Agent` stores configuration; creating it does not start a customer interaction.
- The model identifier selects a provider and model available to the API account.
- `instructions` provides guidance. It is not executable authorization or policy logic.
- `run_sync()` blocks until the run completes or raises an error; `result.output`
	contains the accepted final output.

```python
support_agent = Agent(model, instructions=instructions, output_type=str)
result = support_agent.run_sync(question)
print(result.output)
```

**Setup:** Use a virtual environment and install the framework plus our credential loader:

```bash
python -m pip install "pydantic-ai-slim[openai]" python-dotenv
```

`load_dotenv()` loads environment variables from a local `.env` file. OpenAI reads
`OPENAI_API_KEY`; do not place keys in source code, share them in chat, or commit
credential files. OpenAI API billing is separate from a ChatGPT subscription.

**Observed:** The agent could explain the supplied return policy but could not
retrieve an order. Knowing an order number does not provide database access.

**Read more:** [Installation](https://pydantic.dev/docs/ai/overview/install/),
[Agents](https://pydantic.dev/docs/ai/core-concepts/agent/),
[OpenAI configuration](https://pydantic.dev/docs/ai/models/openai/).

## Lesson 2: Structured Output

**Goal:** Return a typed object rather than making application code parse prose.

- `SupportResponse(BaseModel)` defines `reply`, `issue_type`, and `needs_human`.
- `Literal` restricts `issue_type` to our four allowed classifications.
- `Field(description=...)` contributes explanations to the schema the model sees.
- `output_type=SupportResponse` connects the agent to that output contract.
- `result.output` is a `SupportResponse` instance, not merely a JSON string.
- `model_dump_json(indent=2)` serializes the instance for readable terminal output.
- Ordinary type hints do not enforce runtime values; Pydantic supplies validation
	and can coerce some inputs according to its configuration.

```python
class SupportResponse(BaseModel):
		reply: str
		issue_type: Literal["return", "order_status", "damaged_item", "other"]
		needs_human: bool
```

Our actual fields include descriptions. Pydantic AI handles the output schema;
we do not need to manually prompt for JSON. By default, this structured output
uses an output tool whose arguments represent the proposed final answer.

**Observed:** An unavailable-order question produced `issue_type="order_status"`
and `needs_human=True`. The classification and escalation decision came from
the model, not automatic business-rule enforcement by Pydantic.

**Caution:** A correctly typed boolean can still be the wrong decision, and a
correctly shaped reply can still contain false facts.

**Read more:** [Structured output and output modes](https://pydantic.dev/docs/ai/core-concepts/output/).
Python background: [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
and [Fields](https://docs.pydantic.dev/latest/concepts/fields/).

## Lesson 3: Function Tools

**Goal:** Answer order questions using information retrieved by Python.

- A function tool is a registered Python function the model may request.
- `@support_agent.tool_plain` registers a function that does not take run context.
- The name, docstring, and argument schema describe the tool to the model.
- The framework validates the model's arguments and executes the function locally.
- The returned data becomes available to the model for a subsequent response.
- Tool registration does not automatically send the function body or database.

```python
@support_agent.tool_plain
def get_order(order_id: str) -> dict[str, str]:
		"""Look up an order's status and tracking number."""
		return ORDERS.get(order_id, {"error": "Order not found"})
```

This was our initial version; Lesson 4 replaced it with an ownership-checked tool.
We also removed the conflicting instruction saying orders were inaccessible.

**Observed:** `[tool] Looking up order 143` appeared, and the answer included
`shipped` and `TRACK-143`. A plausible final answer alone would not prove a lookup
ran; logs or recorded tool messages provide that evidence.

**Read more:** [Function tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/)
and [Tool schemas](https://pydantic.dev/docs/ai/tools-toolsets/tools/#tool-schema).

## Lesson 4: Dependencies And RunContext

**Goal:** Supply resources and customer identity explicitly for each run.

A dependency is data or a service our code needs, not necessarily an installed
package. Dependency injection means supplying it from the caller instead of
having a function reach into global state.

```python
@dataclass
class SupportDeps:
		customer_id: str
		orders: dict[str, dict[str, str]]

deps = SupportDeps(customer_id="customer-2", orders=ORDERS)
result = support_agent.run_sync(question, deps=deps)
```

- `deps_type=SupportDeps` declares the type for typing support. It does not
	construct, authenticate, or runtime-validate the dependency instance.
- `deps=deps` supplies the actual instance to this run.
- `@support_agent.tool` registers a tool whose first parameter is run context.
- `ctx: RunContext[SupportDeps]` describes a context whose dependencies have that type.
- Pydantic AI supplies `ctx`; the model supplies `order_id`. `ctx` is excluded
	from the model-facing argument schema.
- `ctx.deps` refers to our supplied instance. Other context fields include the
	prompt, messages, usage, and relevant retry count.
- `RunContext` is a Python object, not the model's context window or memory.
- Dependencies are not automatically sent to the model; returned tool data or
	generated instructions can deliberately expose selected values.

**Authorization:** Our tool compares the record's owner with
`ctx.deps.customer_id`. As `customer-2`, order `144` is accessible and order `143`
is not. A prompt claiming another identity cannot change the supplied identity
through this tool. In production, identity must come from trusted authentication.
Missing and unauthorized orders return the same error; we do not reveal ownership.

**Dataclasses:** Standard `@dataclass` generates `__init__`, `__repr__`, and
field-based `__eq__`. It does not validate the annotated field types. Instances
are mutable by default. `frozen=True` blocks ordinary field reassignment, not
mutation of nested dictionaries. Use `field(default_factory=dict)` for a fresh
mutable default. Passing `ORDERS` stores a reference, not a copy; different
dependency instances can still share that dictionary.

Do not print the entire dependency object with real data: its generated
representation can expose every order or secret in application logs.

**Read more:** [Dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/)
and [RunContext API](https://pydantic.dev/docs/ai/api/pydantic-ai/tools/#pydantic_ai.tools.RunContext).
Python background: [Dataclasses](https://docs.python.org/3/library/dataclasses.html).

## Lesson 5: Output Validation And Retries

**Goal:** Reject an output that violates an explicit business rule.

After schema validation, Pydantic AI calls `validate_support_response` with a
context and candidate `SupportResponse`:

```python
if output.issue_type == "damaged_item" and not output.needs_human:
		raise ModelRetry("Damaged items require human support. Set needs_human=True.")
return output
```

- `@support_agent.output_validator` registers this additional check.
- Returning the output accepts it; `ModelRetry` rejects it and supplies feedback.
- A correction requires another model request, not a restart of our script.
- The default output retry allowance is one; exhausted correction attempts raise
	`UnexpectedModelBehavior`. Request limits can stop a run before a retry happens.
- `ctx.retry` helps inspect the relevant output retry count.

**Limitation:** This validator checks consistency with the model's classification.
If the model mislabels a damaged-item question as `other`, this rule does not catch
it. It also does not prove the prose actually refers the customer to human support.
We have implemented the rule but have not yet deliberately exercised the retry
branch with a scripted model; that belongs to the deferred testing lesson.

**Read more:** [Output validators](https://pydantic.dev/docs/ai/core-concepts/output/#output-validators)
and [Retries](https://pydantic.dev/docs/ai/core-concepts/retries/).

## Lesson 6: Conversation History

**Goal:** Resolve follow-up questions such as "What is its tracking number?"

- Reusing an `Agent` does not automatically preserve a conversation between runs.
- Supply earlier messages with `message_history=history`.
- `result.new_messages()` contains only the current run's messages.
- `result.all_messages()` contains the supplied history plus current messages.
- Messages can include questions, tool requests, tool results, and output submissions.

```python
result = support_agent.run_sync(question, deps=deps, message_history=history)
history.extend(result.new_messages())
```

The update must happen inside the loop after a successful turn. Alternatively,
assign `history = result.all_messages()`. Do not append `all_messages()` to existing
history, because it already contains those earlier messages.

**Observed:** A follow-up initially asked for the order number again. After fixing
the history update's placement, the conversation retained the earlier order context.

**Cautions:** This is process-local context, not model training or durable storage.
Longer histories increase token usage and may contain stale tool results. Keep each
history tied to its customer session. Changing identity without clearing history
can expose a previous customer's details even when tool authorization is correct.
Dependencies provide resources and identity; history provides model-facing context.

**Read more:** [Messages and chat history](https://pydantic.dev/docs/ai/core-concepts/message-history/)
and [Runs versus conversations](https://pydantic.dev/docs/ai/core-concepts/agent/#runs-vs-conversations).

## Lesson 7: Dynamic Instructions

**Goal:** Adapt customer-facing replies using a runtime language preference.

We added `preferred_language: str = "English"` to `SupportDeps` and registered:

```python
@support_agent.instructions
def customer_preferences(ctx: RunContext[SupportDeps]) -> str:
		return (
				f"Write the customer-facing reply in {ctx.deps.preferred_language}. "
				"Keep issue_type values exactly as defined in the output schema."
		)
```

- The framework invokes the function automatically to generate current-run guidance.
- Its returned string joins the static instructions; it does not replace them.
- Dynamic instructions are reevaluated when runs reuse conversation history.
- Merely adding a dependency field does not make the model aware of that field.
- This function deliberately exposes the language preference, not the whole deps object.
- Language instructions guide the model; our validator does not enforce the language.

**Observed:** With Spanish preferences, the reply was
"Tu pedido 144 ya fue entregado. Numero de seguimiento: TRACK-144."
while `issue_type` remained `order_status` and `needs_human` remained a boolean.
The current code's preference is back to English.

**Read more:** [Instructions](https://pydantic.dev/docs/ai/core-concepts/agent/#instructions).

## Lesson 8: Usage Limits And Error Handling

**Goal:** Observe usage and bound how much work each run may perform.

- Tokens are model text units, often word fragments rather than complete words.
- Input includes instructions, schemas, history, questions, and tool results.
- Output includes generated content and tool-call arguments, not just visible prose.
- `result.usage` aggregates reported usage across model requests in that run.
- Our installed Pydantic AI version is `2.54.0`; `result.usage` is a property,
	unlike older examples that call `result.usage()`.
- `UsageLimits(request_limit=..., tool_calls_limit=...)` bounds model requests
	and successful function-tool executions. Output submissions are not order lookups.
- Request limits are checked before further model requests. Token limits are
	generally checked after responses unless supported pre-request counting is enabled.
- These limits are not an exact dollar spending cap and do not reverse prior charges.

```python
result = support_agent.run_sync(
		question,
		deps=deps,
		message_history=history,
		usage_limits=UsageLimits(request_limit=4, tool_calls_limit=2),
)
usage = result.usage
```

The example budget leaves space for corrections. The current application uses
`request_limit=2`, which permits the usual lookup-and-answer sequence but leaves
no additional request for correction after those two requests.

**Observed:** `[usage] requests=2, input_tokens=1578, output_tokens=100`.
That is one customer turn with two model requests, not two customer questions.
The counts alone cannot identify the calls; inspect logs and messages for that.
Resent context contributes to aggregate input counts again; the local dictionary
lookup itself uses no model tokens.

**Error handling:** `UsageLimitExceeded` means the run exceeded a usage boundary.
`UnexpectedModelBehavior` includes exhausted output-validation retries. Both
handlers use `continue` so failed turns neither process stale `result` values
nor update history. These handlers do not cover every provider or network error.
We checked first-turn and later-turn failures locally without OpenAI requests;
we have not added an automated test suite to the project.

**Read more:** [Usage limits](https://pydantic.dev/docs/ai/core-concepts/agent/#usage-limits),
[Usage API](https://pydantic.dev/docs/ai/api/pydantic-ai/usage/),
and [Exceptions API](https://pydantic.dev/docs/ai/api/pydantic-ai/exceptions/).

## Lesson 9: Async Execution And Structured Streaming

**Status:** Part A introduced; awaiting the user's async execution checkpoint.
Part B is a conceptual preview, not an implemented streaming workflow. The
application is still synchronous until the following replacement is applied.

**Goal:** Understand cooperative async execution before handling incremental output.

### Part A: Async Execution

- `run_sync()` drives the framework's async run while blocking its caller.
- `async def` defines a coroutine function. Calling it creates a coroutine object;
	it does not immediately execute the body or start a background task.
- `await support_agent.run(...)` executes the coroutine and waits for its result.
	During awaited I/O, the event loop can run other ready tasks. Async code does
	not automatically make CPU-heavy work faster or start concurrent requests.
- `asyncio.run(main())` creates an event loop, runs the top-level coroutine,
	and closes the loop when it finishes. Call it once at the CLI entry point,
	not inside a running event loop or once per question.
- `asyncio.to_thread(input, "> ")` runs blocking terminal input in a worker thread;
	awaiting it avoids blocking the event loop. It returns the entered string.
- Existing synchronous tools, instruction functions, and output validators can
	remain `def`; the framework supports them in async runs. Choose async clients
	and `async def` tools when you add network or database I/O that supports async.
- Both `run_sync()` and `await run()` return a completed `AgentRunResult`.
	Async execution alone does not display a response incrementally.

**Change to make:** Add `import asyncio`. Replace the top-level `deps`, `history`,
and `while True` block with the code below. Do not keep the old loop as well.
Keep the agent, tools, dependencies type, and output validator unchanged.

```python
async def main() -> None:
		deps = SupportDeps(customer_id="customer-2", orders=ORDERS,
											 preferred_language="English")
		history: list[ModelMessage] = []
		while True:
				question = (await asyncio.to_thread(input, "> ")).strip()
				if question.lower() == "quit":
						break
				if not question:
						continue
				try:
						result = await support_agent.run(
								question,
								deps=deps,
								message_history=history,
								usage_limits=UsageLimits(request_limit=2, tool_calls_limit=2),
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


if __name__ == "__main__":
		asyncio.run(main())
```

This preserves the current per-run budget. As discussed in Lesson 8, raising
`request_limit` to `4` leaves room for a correction after a two-request lookup.
The entry-point guard prevents the CLI loop from running when another module
imports the file; creating the agent and registering its tools still occur.
In a notebook or an async server, use the existing event loop instead of nesting
`asyncio.run()`; for example, await `main()` in an environment supporting top-level await.

**Checkpoint:** Run the script, ask "Where is order 144?", then "What is its
tracking number?", and exit with "quit". Tool execution, validation, usage reporting,
and history should behave as before. No speedup or incremental display is expected
for this sequential CLI. The user has not yet reported this checkpoint's results.

### Part B: Structured Streaming Preview

Streaming and async solve different problems: async lets the caller cooperate
with other tasks while waiting; streaming exposes generated output before it is
complete. It can improve time to first display, not necessarily total completion time.

| API | What the caller receives |
| --- | --- |
| `await agent.run(...)` | A completed result after tools and validation |
| `async with agent.run_stream(...) as stream` | A managed final-output stream |
| `async for snapshot in stream.stream_output()` | Accumulated structured snapshots, not text deltas |
| `await stream.get_output()` | The fully validated final output, or an error |

For our `SupportResponse`, use `stream_output()`, not the plain-text-only
`stream_text()`. A snapshot can lack required fields or contain unfinished text.
Do not weaken the final schema by making everything optional just to stream it.
In the upcoming exercise, inspect snapshots through `model_dump()` and treat
them only as previews, not accepted policy decisions or permission to act.

The existing output validator directly reads `issue_type` and `needs_human`.
Before using it with partial output, add this guard at the start of its body:

```python
if ctx.partial_output:
		return output
```

The framework still performs full schema validation and invokes the business
check with `partial_output=False` for the complete response. Consume the stream
fully and retrieve final output successfully before updating history or relying
on final usage counts. `async with` manages asynchronous stream cleanup.

**Important streaming differences:** `run_stream()` selects the first matching
output as final; it is not a drop-in way to preserve every tool continuation or
retry from `run()`. A `ModelRetry` raised while validating its selected final stream
does not necessarily trigger another model request; do not assume the normal
correction loop continues. For full run progression, event visibility, and retry
handling, consider `run_stream_events()` or `agent.iter()` when needed. We will
choose the streaming approach deliberately after completing Part A.

**Read more:** [Running agents](https://pydantic.dev/docs/ai/core-concepts/agent/#running-agents),
[Structured streaming](https://pydantic.dev/docs/ai/core-concepts/output/#streaming-structured-output),
[Partial output validation](https://pydantic.dev/docs/ai/core-concepts/output/#handling-partial-output-in-output-validators),
and [Streaming all events](https://pydantic.dev/docs/ai/core-concepts/agent/#streaming-all-events).
Python background: [Asyncio](https://docs.python.org/3/library/asyncio.html)
and [Coroutines and tasks](https://docs.python.org/3/library/asyncio-task.html).

## Trace: Customer-2 Asks About Order 144

This is the expected successful path, not a guaranteed model call sequence.

1. Python constructs `SupportDeps(customer_id="customer-2", orders=ORDERS, ...)`.
2. `run_sync()` starts a run; the framework generates dynamic language instructions.
3. The first model request contains the question, instructions, history, and schemas.
4. The model requests `get_order` with `{"order_id": "144"}`.
5. Pydantic validates the arguments; Pydantic AI calls `get_order(ctx, order_id="144")`.
6. Python checks ownership and returns `delivered` and `TRACK-144`, not other records.
7. A second model request supplies that returned data in conversation context.
8. The model submits a proposed structured answer through the output mechanism.
9. Pydantic validates it; Pydantic AI invokes `validate_support_response(ctx, output)`.
10. An accepted answer becomes `result.output`; the loop prints it, reports usage,
		and appends `result.new_messages()` for the next turn.

Use `result.all_messages()` to inspect the recorded interaction. This is not a raw
HTTP capture or a view into the model's private internal reasoning.

## Decorator Reference

Decorators run during definition to register behavior or modify a class. The
registered function bodies execute later at the relevant point in a run.

| Decorator | Meaning | Who triggers the function body? |
| --- | --- | --- |
| `@dataclass` | Generate common class methods from annotated fields | Normal Python calls to those generated methods |
| `@agent.tool_plain` | Register a function without run context | Framework, in response to a model tool request |
| `@agent.tool` | Register a function with supplied `RunContext` | Framework, in response to a model tool request |
| `@agent.output_validator` | Register an additional candidate-output check | Framework after schema validation |
| `@agent.instructions` | Register a function that generates guidance | Framework when resolving instructions for the run |

## Reusable Agent-Building Roadmap

Apply this workflow to another domain; do not copy store-specific rules blindly.

| Step | What to decide or build | Check before advancing |
| --- | --- | --- |
| 1. Scope | One clear job, intended users, allowed actions, and escalation rules | Can you name success, missing-information, and refusal cases? |
| 2. Minimal run | Provider, available model, secret handling, and a simple request | Can you obtain a response and understand API billing? |
| 3. Output contract | Typed fields that application code actually needs | Can downstream code avoid parsing prose, and are constraints explicit? |
| 4. Information tools | Small read-only functions with typed arguments and useful descriptions | Do answers rely on retrieved evidence, including explicit missing-data results? |
| 5. Trusted dependencies | Identity, service clients, configuration, and request-specific resources | Are access checks enforced in Python and secrets kept out of model context? |
| 6. Correctness rules | Deterministic business logic, validators, and bounded correction retries | Which mistakes are actually detected, and which still depend on model judgment? |
| 7. Conversation | Session-scoped history, context freshness, and a reset/persistence strategy | Does a follow-up work without mixing customers or endlessly growing history? |
| 8. Runtime guidance | Preferences or configuration converted into selected instructions | Is only necessary data exposed, and are untrusted values handled carefully? |
| 9. Limits and failures | Request/tool/token budgets, timeouts, error paths, and fallback behavior | Can a run terminate cleanly without stale results or unbounded spend? |
| 10. Execution and visibility | Async I/O, streaming where useful, logs/traces, usage, and latency | Can you inspect calls and distinguish partial content from accepted output? |
| 11. Side effects | Explicit approval and authorization for write operations; idempotency | Can retries or duplicate requests cause unintended actions? |
| 12. Verification | Unit/integration tests, scripted models, representative real-model evaluations | Do you measure both Python correctness and model decision quality? |
| 13. Production readiness | Data retention, provider failures, monitoring, and deployment | Are privacy, reliability, cost, and operational responsibilities explicit? |

Start with a single agent and fake services. Introduce databases, retrieval,
multi-agent designs, or abstractions only when the actual task needs them.
Instructions are guidance, output schemas are data contracts, and neither is a
substitute for authentication, authorization, or deterministic business logic.

### Current Project Gaps

- We retrieve status and tracking; we do not independently calculate return eligibility.
- The 30-day rule is only in instructions. A reliable eligibility tool would use
	delivery dates, item condition, and a defined reference date in Python.
- Customer identity is simulated; there is no actual login or authentication.
- History is in memory, unbounded, and not persisted or refreshed automatically.
- The agent does not issue refunds, cancel orders, or create real support tickets.
- Schema validation does not guarantee factual grounding or correct classification.
- Provider-specific error handling and a repeatable test/evaluation suite are not implemented.

### Next Lessons: Planned, Not Yet Completed

| Lesson | Concept | Intended project addition | Official documentation |
| --- | --- | --- | --- |
| 9B | Structured streaming exercise after the async checkpoint | Apply the preview in Lesson 9; distinguish previews from accepted results and retain required validation behavior | [Structured streaming](https://pydantic.dev/docs/ai/core-concepts/output/#streaming-structured-output), [Streaming all events](https://pydantic.dev/docs/ai/core-concepts/agent/#streaming-all-events) |
| 10 | Deterministic eligibility logic and typed tool data | Calculate return eligibility instead of asking the model to invent dates or rules | [Function tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/), [Dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/) |
| 11 | Observability | Inspect calls, validation, latency, and usage through traces | [Debugging and monitoring](https://pydantic.dev/docs/ai/core-concepts/agent/#debugging-and-monitoring) |
| 12 | Human approval for actions | Learn deferred execution before adding any real write operation | [Deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/) |
| 13 | Testing and evaluation | Deliberately exercise bad outputs, access denial, and model decision quality | [Dependencies in tests](https://pydantic.dev/docs/ai/core-concepts/dependencies/#overriding-dependencies), [Systematic testing with evals](https://pydantic.dev/docs/ai/core-concepts/agent/#systematic-testing-with-evals) |

Future lessons can adjust this sequence to match the project's needs. After each
lesson, add its goal, concepts, code change, observations, limitations, and official
documentation links; do not mark planned or untested behavior as demonstrated.

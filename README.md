# Support Agent

A command-line support agent for a fictional online store, built to learn Pydantic AI.
It uses an OpenAI model and Python tools to look up orders, check customer ownership,
calculate return eligibility, and produce structured responses. The project explores
dependencies, validation, conversation history, language preferences, and usage limits.

The agent uses fake data and does not process real refunds or cancellations.
The full learning guide and reusable agent-building roadmap are included below.

---

# Learning Pydantic AI: Support Agent

Build an order-support agent for a fictional online store, one concept at a time.
This is a learning project with fake data, not a production support system.

This log summarizes Lessons 1-10 and Lesson 11A's local observability exercise.
Eligibility checks, validated order records, async execution, streaming, and
local execution logs are implemented. The user reports the streaming checkpoint
works as expected; individual live observability results were not shared.
It is updated after each lesson. Examples
are focused excerpts, not replacements for the complete application in [main.py](main.py).
The project is paused here. Logfire is not installed or configured, and testing
is deferred. The future lessons below are a study roadmap, not implemented features
or a commitment to continue development in this repository.

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
| [9](#lesson-9-async-execution-and-structured-streaming) | Async execution and structured-streaming exercise | `run()`, `run_stream()`, `stream_output()` |
| [10](#lesson-10-deterministic-return-eligibility) | Typed records and deterministic eligibility exercise | `BaseModel`, `date`, typed tool results |
| [11](#lesson-11-observability) | Local tool-call records and run timing | `new_messages()`, message parts, `perf_counter()` |

Further study: [Future Lessons](#future-lessons-planned-not-yet-started).

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

**Status:** Async execution and structured streaming are implemented in
[main.py](main.py). The user reports the streaming exercise works as expected.
The partial-output guard precedes the validator's field access, and completed
stream output supplies the final answer, usage, and messages saved to history.
No specific preview counts, token counts, or forced rejection results were shared.

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

**Change made:** Added `import asyncio` and moved the top-level `deps`, `history`,
and conversation loop into `async def main()`. The code below is the async pattern
now used in the application. The agent, tools, dependencies type, and business
validator remain unchanged.

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
for this sequential CLI. The application now uses the streaming replacement below;
this non-streaming example remains as the historical Part A exercise.

### Asyncio Deep Dive

`async` and `await` are Python language keywords; `asyncio` is the standard-library
runtime we use to execute and schedule async code. Pydantic AI's `run()` is a
framework method, not an `asyncio` function.

#### Event Loop, Coroutines, And Tasks

An event loop runs ready callbacks and tasks, monitors I/O, and resumes waiting
tasks when their operations finish. Tasks on a single loop cooperate rather than
being forcibly interrupted after every statement. One task runs Python code at
a time on the loop's thread; worker threads created by `to_thread` are separate.

| Term | Meaning in this project |
| --- | --- |
| Coroutine function | A function defined using `async def`, such as `main` |
| Coroutine object | The awaitable execution created by calling `main()` |
| Task | A coroutine scheduled on the event loop; `asyncio.run()` manages the top-level task |
| Awaitable | Something `await` can wait on, such as a coroutine, Task, or Future |
| Future | A lower-level object representing an eventual result; we do not create these ourselves |

Calling a normal `def` function executes it immediately. Calling an `async def`
function without `yield` creates a coroutine object without executing its body.
Our functions are coroutines, not async generators. The coroutine must be awaited
or scheduled; discarding it without doing either can produce a "coroutine was
never awaited" warning.

```python
import asyncio


async def get_message() -> str:
	print("Function body runs now")
	return "Hello"


async def demonstrate() -> None:
	pending = get_message()
	print("Coroutine created; body has not run yet")
	message = await pending
	print(message)


if __name__ == "__main__":
	asyncio.run(demonstrate())
```

Expected order: "Coroutine created; body has not run yet", "Function body runs
now", then "Hello". This example has no external I/O. An `await` does not always
yield control: an operation that completes immediately can keep running in the
current task. It yields when the awaited operation actually needs to suspend.
Awaiting a coroutine directly does not by itself schedule a separate task.

#### asyncio.run(main())

The expression first calls `main()` to create its coroutine. `asyncio.run()`
then creates an event loop, manages the coroutine as a task, waits for completion,
and cleans up the loop and its resources. It blocks the synchronous caller while
the async application runs. It normally returns the coroutine's return value;
our `main() -> None` returns `None` when the loop ends.

Use it once at this script's entry point. Do not call `run_sync()` or nest
`asyncio.run()` inside our async `main`. Async servers and notebooks may already
have an event loop; use their existing async entry points instead.

#### asyncio.to_thread(input, "> ")

`input("> ")` is a blocking function: it holds its calling thread until the user
enters a line. `to_thread` moves that call to an executor worker thread, while
`await` lets the event-loop task wait for the returned string without holding up
other ready tasks. Our `.strip()` runs after the entered string is returned.

Pass the callable `input` and its arguments separately. Writing
`asyncio.to_thread(input("> "))` would execute the blocking input immediately
on the event-loop thread and then incorrectly pass a string instead of a callable.
Simply adding `async def` around blocking code does not make that code nonblocking.

Awaiting `to_thread` does not make `main` continue past that statement before
input is ready. It permits other scheduled work to progress during the wait.
In this sequential CLI, there may be no other application task to run yet.

#### await support_agent.run(...)

Calling `support_agent.run(...)` creates its coroutine. `await` drives that
operation within the current task, pausing our loop during pending async I/O and
resuming it with a completed `AgentRunResult`. An exception resumes execution
through our `except` handlers instead. After a successful return, output display,
usage reporting, and the history update execute in order.

Async model HTTP operations need not occupy one worker thread per request.
Pydantic AI supports our existing synchronous tools and callbacks alongside
async operations; their registration does not require changing every `def`.

#### Our Exact Execution Order

1. `asyncio.run(main())` starts the CLI task.
2. The task creates dependencies and history.
3. `await asyncio.to_thread(input, "> ")` waits while a worker reads terminal input.
4. Input arrives; the task strips and checks the question.
5. `await support_agent.run(...)` waits through model requests and tool execution.
6. On success, the task prints the result and usage, updates history, and repeats.
7. Entering `quit` exits `main`; `asyncio.run()` completes cleanup and returns.

We do not read a second question concurrently with the first agent run. That
sequential behavior preserves ordering and avoids racing updates to one history.

#### Concurrency Is Not Automatic Parallelism

Awaiting two operations one after the other runs them sequentially. `asyncio`
also offers `create_task()` and `TaskGroup` to schedule independent work
concurrently, but we have not used them in this project. Do not overlap turns
sharing the same mutable conversation history without a deliberate design.

Async is useful for I/O waiting, not automatically for CPU-intensive loops. A
long CPU loop or blocking I/O on the event-loop thread prevents other tasks from
progressing. `to_thread` is primarily appropriate for blocking I/O; ordinary
CPU-bound Python work often needs processes or another execution strategy.

Async does not train the model, reduce API token charges, automatically retry
errors, or stream output. Streaming remains the next separate exercise.

**Python references:** [Asyncio overview](https://docs.python.org/3/library/asyncio.html),
[Coroutines and tasks](https://docs.python.org/3/library/asyncio-task.html),
[asyncio.run](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run),
and [asyncio.to_thread](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread).
**Pydantic AI reference:** [Running agents](https://pydantic.dev/docs/ai/core-concepts/agent/#running-agents).

### Part B: Structured Streaming

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
In this exercise, inspect snapshots through `model_dump()` and treat
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

#### Apply The Streaming Exercise

First put the partial-output guard above at the very start of
`validate_support_response`, before its log statement. It avoids reading fields
that may not have arrived yet and keeps the business rule focused on full output.
Keep every field of `SupportResponse` required.

Then replace the block from `try:` through `history.extend(...)` in `main` with:

```python
				try:
						async with support_agent.run_stream(
								question,
								deps=deps,
								message_history=history,
								usage_limits=UsageLimits(request_limit=2, tool_calls_limit=2),
						) as stream:
								async for snapshot in stream.stream_output(debounce_by=0.1):
										print("[preview]", snapshot.model_dump())
								output = await stream.get_output()
								usage = stream.usage
								new_messages = stream.new_messages()
				except UsageLimitExceeded as error:
						print(f"[limit] {error}")
						continue
				except UnexpectedModelBehavior as error:
						print(f"[validation] {error}")
						continue

				print("[final]")
				print(output.model_dump_json(indent=2))
				print(
						f"[usage] requests={usage.requests}, "
						f"input_tokens={usage.input_tokens}, "
						f"output_tokens={usage.output_tokens}"
				)
				history.extend(new_messages)
```

The enclosing `main`, question input, dependencies, and entry-point guard remain
unchanged. This keeps the existing request budget, authorization tool, and history
behavior. Do not reference `result.output` in this replacement: `run_stream`
provides a stream object, and `get_output()` gives the final `SupportResponse`.

- `async with` awaits setup and manages stream cleanup when the block exits,
	including when an exception occurs. Intermediate tool calls can execute before
	the framework yields the selected output stream to this block.
- `async for` awaits each available structured snapshot instead of blocking a
	thread waiting for the next value.
- Snapshots are accumulated views, not string fragments to concatenate. Later
	snapshots may repeat earlier content or add fields. `model_dump()` is useful
	for displaying whichever fields are available without reading missing attributes.
- `debounce_by=0.1` groups arriving updates for roughly 0.1 seconds to reduce
	parsing and validation overhead; it does not make the model generate faster.
- Exhausting `stream_output()` performs full validation of its final item.
	`get_output()` then retrieves the validated cached output rather than issuing
	an extra OpenAI request.
- Read usage and collect messages after successful completion. Extend the
	conversation history only after the context exits successfully. A failed turn
	can have printed previews, but it must not print an accepted final result or
	add failed-turn messages to our history.

**Example preview shapes, not promised outputs:**

```text
[preview] {'reply': 'Your order'}
[preview] {'reply': 'Your order 144 was delivered.', 'issue_type': 'order_status'}
[preview] {'reply': 'Your order 144 was delivered.', 'issue_type': 'order_status', 'needs_human': False}
[final]
```

Some providers or small responses yield only one or a few snapshots, sometimes
only once all required fields are present. Full validation may yield the same
content again. Snapshot count is not the number of model requests or tool calls.
Model waiting and lookup execution still happen before the final answer begins
to stream; this is not instant output.

**Checkpoint:** Ask "Where is order 144?", then "What is its tracking number?",
then "My item arrived damaged." Check preview logs, the final typed response,
usage, history continuity, and the final damaged-item validator log. Exact content
and the number of snapshots vary. The user reports the exercise works as expected;
deliberately forcing a rejected final stream remains part of later verification.

#### Streaming Limitations And Retries

`run_stream()` selects the first matching output as final; it is not a drop-in way
to preserve every tool continuation or retry from `run()`. In our installed
Pydantic AI `2.54.0`, a final schema-validation failure or `ModelRetry` from the
selected final stream becomes `UnexpectedModelBehavior`, with the message
"Output validation failed during streaming, and retries are not supported in
`run_stream()`". Our existing handler rejects the turn without saving its history.
It does not automatically request a corrected final answer.

Our validator still rejects a complete response classified as `damaged_item` with
`needs_human=False`; the rejection is enforced, but the correction loop differs
from ordinary `run()`. Never treat printed previews as permission to refund,
cancel, escalate, or modify records. The last fully accepted output is the only
result our application should rely on.

When full run progression, tool events, and output-correction retries are required,
use `run_stream_events()` or `agent.iter()` with the appropriate output handling.
Those are separate, more advanced workflows. This lesson deliberately starts
with the simple final-output stream for our read-only learning agent.

**Read more:** [Running agents](https://pydantic.dev/docs/ai/core-concepts/agent/#running-agents),
[Structured streaming](https://pydantic.dev/docs/ai/core-concepts/output/#streaming-structured-output),
[Partial output validation](https://pydantic.dev/docs/ai/core-concepts/output/#handling-partial-output-in-output-validators),
and [Streaming all events](https://pydantic.dev/docs/ai/core-concepts/agent/#streaming-all-events).
Python background: [Asyncio](https://docs.python.org/3/library/asyncio.html)
and [Coroutines and tasks](https://docs.python.org/3/library/asyncio-task.html).

## Lesson 10: Deterministic Return Eligibility

**Status:** Both parts are implemented in [main.py](main.py): typed order records,
an ownership-checked eligibility tool, and an application-supplied reference date.
The user found the exercise useful but has not shared individual live responses
or tool-call records. The local example checks below are separate from real-model
verification.

**Goal:** Let Python calculate policy decisions from reliable records, while the
model interprets customer requests and explains the resulting decisions.

The model knows the 30-day rule from instructions, and our records now contain
a delivery date. Asking the model to infer dates or calculate eligibility would
not make those decisions reliable. Use validated records and a deterministic
tool with an explicit reference date and item-condition input instead.

### Part A: Validated Order Records

Pydantic is useful for backend data as well as AI-generated output. Replace the
loosely typed `dict[str, dict[str, str]]` with `dict[str, Order]`, so each record
is constructed as a validated object. An ordinary dataclass still groups our
dependencies, but the order objects it holds are Pydantic models.

Add `from datetime import date` and define this class above `SupportDeps`:

```python
class Order(BaseModel):
		customer_id: str
		status: Literal["shipped", "delivered"]
		tracking_number: str
		delivered_on: date | None = None
```

- `Literal` rejects unsupported status values and catches spelling mistakes
	such as `"delievered"` when constructing a record.
- `date` represents a calendar date rather than an arbitrary string. Pydantic
	can parse valid ISO dates from external data into Python `date` objects.
- `date | None` permits a date or no date. `= None` also supplies a default,
	allowing shipped orders to omit this field. Accepting `None` and making a
	field omittable are separate choices in Pydantic.
- This small model validates field types, not every business invariant. For
	example, it still permits a delivered order with no delivery date; Part B
	must handle missing or inconsistent data explicitly rather than invent it.
- Default Pydantic models do not revalidate every mutation automatically. This
	step validates our records at construction; it is not a live database monitor.

Update the field in `SupportDeps` to `orders: dict[str, Order]`, then replace
the fixture dictionary with:

```python
ORDERS: dict[str, Order] = {
		"143": Order(customer_id="customer-1", status="shipped",
								 tracking_number="TRACK-143"),
		"144": Order(customer_id="customer-2", status="delivered",
								 tracking_number="TRACK-144", delivered_on=date(2026, 10, 1)),
}
```

The date is a fictional fixture, not a claim about a real customer's delivery.
Replace `get_order` with the following version. Its public result still contains
only status and tracking; ownership remains enforced before any data is returned.

```python
@support_agent.tool
def get_order(ctx: RunContext[SupportDeps], order_id: str) -> dict[str, str]:
		"""Retrieve status and tracking for an order belonging to the current customer."""
		print(f"[tool] Looking up order {order_id}")
		order = ctx.deps.orders.get(order_id)
		if order is None or order.customer_id != ctx.deps.customer_id:
				return {"error": "Order not found for the current customer"}
		return {
				"status": order.status,
				"tracking_number": order.tracking_number,
		}
```

`orders` remains a dictionary, so `.get(order_id)` is unchanged. Its values are
now objects, so use attributes such as `order.status` instead of `order["status"]`.
Do not return the entire `Order` merely for convenience: keep private ownership
information out of tool results unless there is a specific reason to expose it.

There is no new registration API in this step. `get_order` remains a context-aware
tool, and `SupportResponse` remains the model's final-output contract. Backend
order validation and final-output validation serve different data boundaries.
Dependencies still are not automatically sent to the model. A malformed internal
fixture raises Pydantic `ValidationError` during construction; it is not a bad
model answer that should be corrected with `ModelRetry`.

**Checkpoint:** Restart the script and ask for order `144`, then order `143` as
`customer-2`. The first should still return delivered status and `TRACK-144`; the
second must not return the other customer's details. The visible behavior should
not change merely because internal records are now typed. These code changes
are now present; individual live lookup results were not shared.

### Part B: Deterministic Eligibility Tool

The model will choose the tool and explain its result; Python will calculate the
deadline and eligibility. "Deterministic" means the same records, condition, and
reference date produce the same tool decision, independent of the model's prose.

For this fictional policy, a standard return requires a delivered order, an unused
item, and a delivery age between 0 and 30 calendar days inclusive. Day 30 is
allowed; day 31 is not. Missing or future delivery dates are data problems, not
permission to infer a date. Customer-reported item condition is an input, not
a verified fact. Damaged items require human support, not automatic approval.

#### 1. Define The Tool Result

Above agent creation, define:

```python
class ReturnEligibility(BaseModel):
	eligible: bool | None
	reason: str
	deadline: date | None = None
	needs_human: bool = False
```

`True` means eligible under the checked policy, `False` means ineligible, and
`None` means we cannot make a standard eligibility decision. `False` and `None`
must not be treated as equivalent. Constructing this Pydantic object validates
our Python-produced result, and the framework serializes it for the model.
`deadline` will be serialized as an ISO date such as `"2026-10-31"`.

This is a function-tool result, not the agent's final output contract. Keep
`output_type=SupportResponse`: the model reads `ReturnEligibility`, then generates
the customer-facing `SupportResponse`. Returning a typed result does not
automatically enforce that the model's final prose agrees with it.

#### 2. Inject The Reference Date

Update the import to `from datetime import date, timedelta` and add a required
`as_of` date before the defaulted language field:

```python
@dataclass
class SupportDeps:
	customer_id: str
	orders: dict[str, Order]
	as_of: date
	preferred_language: str = "English"
```

In `main`, supply a fixed date for the exercise:

```python
deps = SupportDeps(
	customer_id="customer-2",
	orders=ORDERS,
	as_of=date(2026, 10, 8),
	preferred_language="English",
)
```

The model cannot choose the policy's reference date as a tool argument; it comes
from application-controlled dependencies. A fixed date makes our examples
reproducible. In production, the application would supply the current date in a
defined business timezone and refresh it as needed, not freeze it forever or
take it from a customer prompt.

#### 3. Register The Eligibility Tool

Add this after `get_order` and before the validator. Keep `get_order` registered
for status questions.

```python
@support_agent.tool
def check_return_eligibility(
	ctx: RunContext[SupportDeps],
	order_id: str,
	condition: Literal["unused", "used", "damaged", "unknown"] = "unknown",
) -> ReturnEligibility:
	"""Check standard return eligibility without creating a return.

	Args:
		order_id: The customer-provided order number.
		condition: Customer-reported condition; use unknown if not stated.
	"""
	print(f"[tool] Return check: order={order_id}, condition={condition}")
	order = ctx.deps.orders.get(order_id)
	if order is None or order.customer_id != ctx.deps.customer_id:
		return ReturnEligibility(eligible=None, reason="Order not found for the current customer")
	if condition == "damaged":
		return ReturnEligibility(eligible=None, reason="Damaged items require human support", needs_human=True)
	if order.status != "delivered":
		return ReturnEligibility(eligible=False, reason="The return window starts after delivery")
	if order.delivered_on is None or order.delivered_on > ctx.deps.as_of:
		return ReturnEligibility(eligible=None, reason="Delivery date needs verification", needs_human=True)

	deadline = order.delivered_on + timedelta(days=30)
	if condition == "unknown":
		return ReturnEligibility(eligible=None, reason="Ask whether the item is unused, used, or damaged", deadline=deadline)

	eligible = condition == "unused" and ctx.deps.as_of <= deadline
	if condition == "used":
		reason = "Only unused items qualify for a standard return"
	elif eligible:
		reason = "The unused item is within the 30-day return window"
	else:
		reason = "The 30-day return window has expired"
	return ReturnEligibility(eligible=eligible, reason=reason, deadline=deadline)
```

Ownership is checked before dates, status, condition-based advice, or eligibility
are disclosed. Unknown and unauthorized orders return the same result. `None`
eligibility for damaged or inconsistent records tells the model not to present
an automatic decision; `needs_human=True` indicates the required next step.

`timedelta(days=30)` represents a duration. Adding it to the delivery `date`
computes the last allowed date. We reject future delivery dates first, so
`as_of <= deadline` cannot accidentally approve an undelivered future order.
This is calendar-day logic, not a timestamp-based exact 720-hour interval.

Expected business outcomes are normal tool results, not `ModelRetry` exceptions.
An expired window should be explained, not repeatedly retried until it becomes
eligible. Tool argument validation restricts the condition vocabulary, but it
does not prove the model accurately extracted the customer's reported condition.

#### 4. Tell The Model When To Use It

Append these lines to the static instructions; keep the status-lookup guidance:

```text
For return requests about a specific order, use check_return_eligibility.
Use the item condition stated by the customer; otherwise pass unknown.
Ask for the order number if it is missing. Do not invent item condition or dates.
Explain the tool's decision and deadline; do not recalculate eligibility yourself.
If the tool returns needs_human=True, set needs_human=True in your response.
For damaged items, use issue_type=damaged_item and refer to human support.
An eligibility check does not create a return or issue a refund.
```

The standing 30-day policy explains the business domain; the tool is authoritative
for our computed decision. These instructions guide the model but are not a new
Python enforcement layer. The existing validator only enforces the damaged-item
classification rule; it does not cross-check all eligibility claims against tool
results. The fixed `as_of` also does not automatically become visible outside the
tool; dependencies are not model context unless code deliberately exposes them.

#### 5. Leave Room For Tool Requests

A direct eligibility lookup followed by an answer commonly takes two model
requests. If the model also performs a status lookup on a separate turn within
the run, it may need three. Change the active streaming budget to
`UsageLimits(request_limit=4, tool_calls_limit=2)` for this exercise.
This allows bounded extra steps, not final-output retries in `run_stream()`.
The current application uses `request_limit=4` and `tool_calls_limit=4`; the
second limit bounds tool executions, not model requests.

#### Checkpoint And Boundaries

Restart the application to clear earlier conversation context, then ask:

| Customer question as customer-2 | Expected tool decision with as_of 2026-10-08 |
| --- | --- |
| "Can I return unused order 144?" | Eligible; deadline 2026-10-31 |
| "Can I return order 144?" | Condition unknown; ask about the item's condition |
| "Can I return used order 144?" | Not eligible for a standard return |
| "Order 144 arrived damaged. Can I return it?" | No automatic decision; requires human support |
| "Can I return unused order 143?" | No authorized record; no private details returned |

For the unknown-condition case, use a fresh session or a different order whose
condition was not already supplied; a remembered condition in history is not
missing information. Exact model text and calls vary; inspect the tool log to
confirm it ran. Damaged-item support can also be explained directly by the model
from policy, so a correct final answer alone is not evidence of tool execution.

For the same order delivered on October 1, changing the trusted `as_of` to
October 31 gives day 30 and permits an unused-item return; November 1 gives day
31 and denies it. Restart between reference-date experiments so history does not
contain a stale eligibility decision. We checked these date boundaries and tool
branches in the documented examples locally without provider calls. The user
has implemented the exercise, but individual live results were not shared.

**New flow:** customer question -> model requests eligibility tool -> Python
checks access and calculates policy -> typed result returned to model -> model
explains it in a structured support response. Checking eligibility remains
read-only; it does not create a return, issue a refund, or verify item condition.

**Takeaway:** Let the model interpret the request and explain the answer, but
calculate policy decisions in ordinary Python. Keep application-controlled facts
such as identity and the reference date separate from model-supplied arguments.
Unknown eligibility is not the same as rejection, and neither the typed tool
result nor its registration automatically guarantees the final prose agrees.
Observability is the next planned lesson; automated testing remains deferred.

**Read more:** [Function tools and return values](https://pydantic.dev/docs/ai/tools-toolsets/tools/),
[Dependencies](https://pydantic.dev/docs/ai/core-concepts/dependencies/),
and [Structured final output](https://pydantic.dev/docs/ai/core-concepts/output/).
Python background: [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/),
[Date validation](https://docs.pydantic.dev/latest/api/standard_library_types/#dates),
and [Python date arithmetic](https://docs.python.org/3/library/datetime.html#date-objects).

## Lesson 11: Observability

**Status:** Part A's local message inspector and elapsed-time measurement are
implemented. Individual live observability results were not shared. The project
is paused; Part B's instrumentation is deferred, and Logfire is not installed
or configured.

**Goal:** Inspect what the agent actually did instead of inferring execution
from a plausible final answer. In particular, see whether the model requested
`check_return_eligibility`, which condition it supplied, and what Python returned.

### Logs, Metrics, And Traces

| Signal | What it answers | Example |
| --- | --- | --- |
| Log | What event occurred? | A tool returned an eligibility decision |
| Metric | How much or how often? | Requests, tokens, latency, or error frequency |
| Trace | Which timed operations belong to one interaction? | Agent run with child model-request and tool-execution spans |

A span is a timed operation within a trace. Related spans help distinguish model
waiting, tool execution, and application overhead. Our current print statements
are logs, and our usage summary reports per-run measurements; neither is a full
distributed trace. Observability records behavior, not the model's private
reasoning, and it does not itself validate correctness or improve model decisions.

### Part A: A Local Execution Log

Start with the messages Pydantic AI already records. This adds no package,
telemetry account, model request, or new outbound destination. OpenAI continues
to receive the normal agent requests as before. The new inspector prints tool
content locally, so use fake data and review what terminal logs retain.

#### 1. Add Imports

Replace the current `ModelMessage` import with:

```python
from pydantic_ai.messages import (
	ModelMessage,
	RetryPromptPart,
	ToolCallPart,
	ToolReturnPart,
)
from time import perf_counter
```

`ToolCallPart` records a requested call. `ToolReturnPart` records a returned
result. Their `tool_call_id` links a request to its result even when several
tools were requested. `RetryPromptPart` records feedback asking the model to
correct a problem; seeing that feedback is different from seeing a successful
tool result. Framework-generated output-tool calls can also appear in these
messages, not just our two business tools.

#### 2. Add A Plain Logging Helper

Define this above `main`, without an agent decorator:

```python
def print_run_details(messages: list[ModelMessage]) -> None:
	for message in messages:
		for part in message.parts:
			if isinstance(part, ToolCallPart):
				print(
					f"[call] id={part.tool_call_id}, tool={part.tool_name}, "
					f"args={part.args_as_dict()}"
				)
			elif isinstance(part, ToolReturnPart):
				print(
					f"[return] id={part.tool_call_id}, tool={part.tool_name}, "
					f"result={part.content!r}"
				)
			elif isinstance(part, RetryPromptPart):
				print(f"[retry] tool={part.tool_name}, details={part.content!r}")
```

This helper is ordinary application code, not a model-callable tool. The framework
does not invoke it automatically; we explicitly call it after a successful turn.
`args_as_dict()` reads structured tool arguments without hand-parsing JSON strings.
`!r` displays a Python representation of the returned content, which can be a
dictionary or a Pydantic object, rather than assuming it is already a JSON string.

For our fake return question, illustrative records are:

```text
[call] id=call_example, tool=check_return_eligibility, args={'order_id': '144', 'condition': 'unused'}
[return] id=call_example, tool=check_return_eligibility, result=ReturnEligibility(eligible=True, reason='The unused item is within the 30-day return window', deadline=datetime.date(2026, 10, 31), needs_human=False)
```

Actual IDs and content representation vary. A call record alone only shows that
the model requested a tool; the corresponding result tells us what execution
produced. A name such as `final_result` normally identifies a generated output
submission, not an order lookup or refund operation. Do not equate every call
part with a business-tool execution or with one model request.

#### 3. Measure The Turn

Inside the question loop, immediately before the existing `try`, add:

```python
		started_at = perf_counter()
```

Leave the current streaming block and its exception handlers intact. After those
handlers, in the successful-turn section, add these lines before
`history.extend(new_messages)`:

```python
		elapsed = perf_counter() - started_at
		print(f"[timing] elapsed={elapsed:.2f}s")
		print_run_details(new_messages)
```

`perf_counter()` is a monotonic elapsed-time clock, not a calendar date. Starting
it after terminal input excludes time spent composing the question. This duration
includes model requests, tools, stream consumption, and application work until
the measurement; it is not pure model latency or time to first token. It does
not replace the trusted `deps.as_of` date used for business rules.

We inspect `new_messages`, not all conversation history, so earlier calls are
not printed again on every turn. This reports a successful run after completion,
not live events while the model works. Existing `continue` handlers deliberately
skip this helper on failed turns; they report the error but not a failed turn's
full recorded messages. Detailed failure and per-operation timing need additional
instrumentation or message capture, not fabricated success logs.

#### Checkpoint

Restart and ask "Can I return unused order 144?". Check for a request to
`check_return_eligibility` with `condition='unused'`, its result with deadline
October 31, the final answer, and the timing summary. Compare the tool result
with the answer: they can disagree even though each is well-formed.

In a fresh conversation ask "Can I return order 144?" without supplying condition.
The expected tool input is `unknown`; if the model invents `unused`, the log
exposes that extraction mistake. We have not added enforcement that guarantees
this input choice. A previously stated condition in history is not unknown.
Ask about an unauthorized order and confirm the returned result contains no
other customer's private details. Share one call/result pair and the timing log.

### Part B: Instrumentation And Logfire

For graphical traces and per-model/per-tool timing, Pydantic AI provides optional
OpenTelemetry instrumentation. Pydantic Logfire is one supported backend, not
the model or the validation library. Its SDK can record agent runs and child
spans; content settings determine whether prompts, arguments, and results are
included. A production tracing design must also consider access, retention,
redaction, identifiers, and where the exporter sends data.

No Logfire package, account, authentication, or exporter has been configured in
this exercise. Before using hosted telemetry, make the destination and content
policy explicit. Do not blindly capture raw HTTP headers or bodies, which may
contain credentials and customer data. Disabling content in instrumentation also
does not sanitize arbitrary application `print()` statements or custom log fields.

The local inspector is a first step, not a substitute for tracing, alerting,
evaluations, or tests. We can add instrumentation after the local checkpoint.

**Read more:** [Messages and chat history](https://pydantic.dev/docs/ai/core-concepts/message-history/),
[Messages API](https://pydantic.dev/docs/ai/api/pydantic-ai/messages/),
[Debugging and monitoring](https://pydantic.dev/docs/ai/core-concepts/agent/#debugging-and-monitoring),
and [Logfire and OpenTelemetry](https://pydantic.dev/docs/ai/integrations/logfire/).
Python background: [perf_counter](https://docs.python.org/3/library/time.html#time.perf_counter).

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

- The eligibility tool now calculates the 30-day rule in Python using stored
	dates and an application-supplied reference date. Item condition is still
	customer-reported, and the model chooses which condition argument to supply.
- The final-output validator does not cross-check every return claim against the
	eligibility tool result; correct computation does not ensure faithful prose.
- Customer identity is simulated; there is no actual login or authentication.
- History is in memory, unbounded, and not persisted or refreshed automatically.
- The agent does not issue refunds, cancel orders, or create real support tickets.
- Schema validation does not guarantee factual grounding or correct classification.
- Provider-specific error handling and a repeatable test/evaluation suite are not implemented.

## Future Lessons: Planned, Not Yet Started

All topics in this section are future study. The repository remains paused, and
these exercises can be explored in another project. Logging and testing are
listed separately below rather than included in the main learning sequence.

### Recommended Next Topics

Start with these four topics in this order. Each extends the single-agent concepts
already learned without requiring a multi-agent architecture.

| Order | Topic | What to learn | Practice idea | Official documentation |
| --- | --- | --- | --- | --- |
| 1 | Human approval and deferred tools | Pause a proposed action, collect approval or external results, and resume the run | Request explicit approval before a simulated refund; recheck authorization and eligibility before execution | [Deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/) |
| 2 | Persistent history and context management | Serialize and restore messages, scope sessions by customer, and trim or summarize growing history | Continue a conversation after restarting; avoid retaining stale eligibility results | [Messages and history](https://pydantic.dev/docs/ai/core-concepts/message-history/), [Persistence](https://pydantic.dev/docs/ai/core-concepts/persistence/) |
| 3 | Retrieval-Augmented Generation (RAG) and embeddings | Retrieve relevant source material before answering; understand semantic search and grounding | Search a collection of store policies and return source references rather than placing every document in instructions | [Embeddings](https://pydantic.dev/docs/ai/guides/embeddings/), [RAG example](https://pydantic.dev/docs/ai/examples/data-analytics/rag/) |
| 4 | Toolsets and MCP | Group reusable tools and connect to external tools through Model Context Protocol | Separate order and account toolsets, then connect a read-only ticket-search MCP server | [Toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/), [MCP overview](https://pydantic.dev/docs/ai/mcp/overview/) |

Approval does not replace authorization. A resumed action still needs current
access checks and duplicate-execution protection. Stored history is application
state, not model training. RAG is a retrieval pattern: Pydantic AI does not
automatically supply a document database or managed vector store. MCP is a tool
connection protocol, not a guarantee that a connected tool is trusted or safe.

### Reliability And Control

Choose these topics when the application needs tighter behavior or more reliable
execution. They build on, rather than replace, our existing validators and budgets.

| Topic | What to learn | Practice idea | Official documentation |
| --- | --- | --- | --- |
| Advanced function tools | Dynamic tool availability, custom schemas, argument checks, tool failures, and parallel versus sequential execution | Hide irrelevant tools while still enforcing access in Python; serialize conflicting writes | [Advanced tools](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/) |
| Model configuration and fallbacks | Provider differences, supported model settings, model selection, and fallback conditions | Use a cheaper model for simple questions and a configured fallback for selected provider failures | [Models and providers](https://pydantic.dev/docs/ai/models/overview/), [Model settings](https://pydantic.dev/docs/ai/core-concepts/agent/#additional-configuration) |
| Timeouts, cancellation, and retry layers | Bound requests and tools; distinguish model-correction retries from transport retries; understand cancellation cleanup | Stop a stalled order-service lookup without assuming already executed actions were rolled back | [Timeouts](https://pydantic.dev/docs/ai/core-concepts/timeouts/), [Retries](https://pydantic.dev/docs/ai/core-concepts/retries/), [Cancellation](https://pydantic.dev/docs/ai/core-concepts/agent/#cancelling-a-run) |
| Advanced output contracts | Tool, native, and prompted output modes; unions; output functions; stricter data constraints | Return either a resolved request or a typed escalation instead of encoding both in ambiguous prose | [Output](https://pydantic.dev/docs/ai/core-concepts/output/) |
| Full-run streaming and iteration | Inspect execution through events or graph iteration while preserving the required run progression | Stream UI updates through tool steps and output-correction attempts instead of only the selected final-output stream | [Running agents and event streams](https://pydantic.dev/docs/ai/core-concepts/agent/#running-agents) |

Fallbacks can change capability, quality, cost, and data destination; they are not
automatic substitutes for error handling. Output-mode and model-setting support
varies by provider. Cancellation does not undo a refund or another side effect.

### Advanced Or Domain-Specific Topics

These are optional. Learn them when a real requirement justifies the added
complexity, not because every agent is expected to use them.

| Topic | What to learn | Practice idea | Official documentation |
| --- | --- | --- | --- |
| Multimodal input | Supply images, PDFs, audio, or other supported media and understand provider limitations | Analyze a damaged-item photo or extract details from an invoice, treating model interpretation as unverified | [Multimodal input](https://pydantic.dev/docs/ai/core-concepts/input/) |
| Native and ready-made tools | Distinguish provider-executed tools from functions executed by our application | Add supported web search without claiming Python directly executes the provider's search engine | [Native tools](https://pydantic.dev/docs/ai/tools-toolsets/native-tools/), [Common tools](https://pydantic.dev/docs/ai/tools-toolsets/common-tools/) |
| Hooks and reusable capabilities | Customize lifecycle behavior and package related tools, instructions, and settings for reuse | Share a policy-control capability across several independently configured agents | [Hooks](https://pydantic.dev/docs/ai/core-concepts/hooks/), [Capabilities](https://pydantic.dev/docs/ai/capabilities/overview/) |
| Multi-agent patterns | Distinguish delegation, handoffs, and application-controlled orchestration; manage shared context and budgets | Route genuinely separate billing and shipping responsibilities to specialist agents | [Multi-agent patterns](https://pydantic.dev/docs/ai/guides/multi-agent-applications/) |
| Typed workflow graphs | Use the related pydantic-graph library for explicit state, branching, and parallel steps | Model a return workflow as lookup, eligibility, approval, and action steps rather than leaving every transition to the model | [Pydantic Graph](https://pydantic.dev/docs/ai/graph/graph/) |
| Web and frontend integrations | Serve agents through an application and stream structured UI events with session isolation | Build a customer chat interface with approval controls and server-side credentials | [UI integrations](https://pydantic.dev/docs/ai/integrations/ui/overview/), [FastAPI chat example](https://pydantic.dev/docs/ai/examples/conversational-agents/chat-app/) |
| Durable execution | Integrate an execution engine so long-running workflows can recover after a crash | Resume a pending approval or background operation without unintentionally repeating completed actions | [Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/) |

One agent is often sufficient. Multi-agent systems add coordination and failure
paths. Graphs help control workflow, but are a related library rather than a
requirement for basic Agent usage. Durable execution requires a backend and
careful handling of side effects; ordinary message persistence alone is not
durable execution.

### Deferred Separately

- **Lesson 11B: Logfire and OpenTelemetry.** Not installed or configured.
	[Documentation](https://pydantic.dev/docs/ai/integrations/logfire/).
- **Testing and evaluations.** Still important before production, but postponed
	at the user's request and not part of the roadmap above.
	[Agent testing](https://pydantic.dev/docs/ai/guides/testing/) and
	[Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/).

The suggested order is flexible; these topics are not completed lessons. The
current project uses Pydantic AI `2.54.0`. Check API availability and provider
support before applying examples from newer documentation; do not upgrade or
expand the project solely to follow this list.

When lessons resume, update this README with the goal, concepts, code changes,
observations, limitations, and official links. Keep implemented, locally checked,
and live-model-verified behavior distinct. Do not recreate a separate learning log.
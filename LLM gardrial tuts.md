### **00:00 – 04:30 | Introduction & Concept of Guardrails**
**[00:00]** Hello everyone. In this series of videos, we are going to understand about a very important topic which is called as **Guardrails**. 

Now, as we go ahead, we'll first of all understand what exactly guardrails are, why it is important whenever we are specifically building an AI agent, and then we will also try to understand the practical implementation: what are the approaches to implement guardrails in your AI agent's workflows, and why do we specifically use guardrails itself.

**[00:35]** First of all, we will go ahead with a basic definition:
> *"Guardrails are safety mechanisms that control what goes into and comes out of an AI agent. They sit around your agent pipeline and ensure the agent:*
> - *Only processes safe, appropriate inputs*
> - *Only performs approved actions*
> - *Only returns validated, compliant outputs."*

**[01:24]** Here you can see that I have designed a basic AI agent. What this AI agent is actually doing: it takes an input, the input goes to the LLM, and then the LLM makes a call either to tools or directly gives the output. 

When I talk about tools, these tools can be:
- RAG applications / vector databases
- APIs
- Different packages / MCP servers, etc.

If it makes a call to a tool, we get context back, and the LLM combines this context with the prompt to generate an output.

**[02:26]** But whenever we talk about guardrails, consider what happens if a user provides an input like:
> *"How to hack a server?"*

Do you think this question is appropriate? Obviously, whenever someone asks this kind of message, it is an unsafe message. Why would you want to hack a server? Likely to do something malicious.

What the LLM pipeline should do is either flag this content saying: *"This is not safe, so we will not give you the output,"* or before the input even reaches the LLM, a check should happen right at the input boundary. By doing this, the generated output is always validated, compliant, and adheres to safety rules and regulations.

---

### **04:30 – 07:18 | Two Approaches: Deterministic vs. Model-Based**
**[04:30]** When implementing guardrails in an AI agent, there are two primary approaches:
1. **Deterministic Approach**
2. **Model-Based Approach**

#### **1. Deterministic Approach**
- **How it works:** Uses rule-based algorithms, regular expressions (Regex), keyword matching, and explicit string heuristics.
- **Advantages:** Zero LLM cost, very fast, predictable.
- **Disadvantages:** Cannot understand semantic meaning, subtle context, or nuanced intent.

#### **2. Model-Based Approach**
- **How it works:** Uses an LLM or dedicated classifier model to evaluate content safety against predefined criteria.
- **Advantages:** Understands semantics, intent, context, and nuanced violations.
- **Disadvantages:** Slower and incurs LLM token costs for every invocation.

---

### **07:18 – 13:18 | LangChain Guardrails & Middleware Overview**
**[07:18]** In this tutorial, we will use **LangChain** as our open-source framework to implement guardrails. LangChain implements guardrails using **Middleware** hooks within the agent lifecycle.

The key guardrail mechanisms we cover are:
1. **PII Middleware (Built-in):** Detects personally identifiable information like email addresses, credit cards, IP addresses, and URLs.
2. **Human-in-the-Loop Middleware (Built-in):** Pauses agent execution before sensitive actions (like money transfers, mass emails, database deletions) to await human approval or rejection.
3. **Custom Before-Agent Hook (Input Filter):** Executes custom safety validation prior to invoking the LLM, saving token costs on blocked inputs.
4. **Custom After-Agent Hook (Output Safety):** Validates and sanitizes the final LLM response before delivering it to the end user.
5. **Layered / Combined Guardrails:** Stacking multiple middleware layers in sequence to create defense-in-depth protection.

---

### **13:19 – 19:19 | Code Setup & Section 1–2: Deterministic vs. Model-Based Demo**
**[13:19]** Let's switch over to the notebook: `langchain_guardrails_crash_course.ipynb`.

#### **Environment Setup & Imports**
```python
from dotenv import load_dotenv
load_dotenv()

import os
from getpass import getpass
# Ensure OPENAI_API_KEY is configured in your environment
```

#### **Section 2 Demo: Deterministic Guardrail**
```python
import re

def deterministic_guardrail(text: str) -> bool:
    """Returns True if content is blocked."""
    banned_keywords = ["hack", "exploit", "malware", "bomb"]
    return any(kw in text.lower() for kw in banned_keywords)

test_inputs = [
    "How do I hack into a database?",
    "What is the capital of France?",
    "Explain how malware spreads"
]

for inp in test_inputs:
    blocked = deterministic_guardrail(inp)
    status = "BLOCKED" if blocked else "ALLOWED"
    print(f"{status}: {inp}")
```
*Output:*
- `BLOCKED: How do I hack into a database?`
- `ALLOWED: What is the capital of France?`
- `BLOCKED: Explain how malware spreads` *(Notice limitation: even educational questions about malware are blocked due to naive keyword matching).*

#### **Model-Based Guardrail Demo**
```python
from langchain_openai import ChatOpenAI

def model_based_guardrail(text: str) -> str:
    """Uses an LLM to evaluate content safety. Returns SAFE or UNSAFE."""
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = f"""Is the following user input safe to process?
Reply with only "SAFE" or "UNSAFE".

Input: {text}"""
    result = model.invoke([{"role": "user", "content": prompt}])
    return result.content.strip()

for inp in test_inputs:
    verdict = model_based_guardrail(inp)
    status = "UNSAFE" if "UNSAFE" in verdict else "SAFE"
    print(f"{status}: {inp}")
```
*Output:*
- `UNSAFE: How do I hack into a database?`
- `SAFE: What is the capital of France?`
- `SAFE: Explain how malware spreads` *(The LLM recognizes the educational context and allows the request).*

---

### **19:20 – 26:30 | Section 3: Built-in PII Detection Middleware**
**[19:20]** LangChain provides built-in middleware for detecting and redacting Personally Identifiable Information (PII).

Supported PII types include:
- `email`
- `credit_card`
- `ip`
- `mac_address`
- `url`

Supported strategies:
- `redact`: Replaces text with a placeholder (e.g., `[REDACTED_EMAIL]`).
- `mask`: Masks characters (e.g., `****-****-****-1234`).
- `hash`: Replaces text with a deterministic hash.
- `block`: Raises an exception immediately.

#### **Implementation:**
```python
from langchain.agents import create_agent
from langchain.agents.middleware import PIIMiddleware
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

@tool
def customer_lookup(query: str) -> str:
    """Look up customer information."""
    return f"Customer record found for query: {query}"

# Define agent with PII Middleware
agent = create_agent(
    model="gpt-4o",
    tools=[customer_lookup],
    middleware=[
        # Redact emails in user inputs
        PIIMiddleware(
            "email",
            strategy="redact",
            apply_to_input=True
        ),
        # Mask credit cards in user inputs
        PIIMiddleware(
            "credit_card",
            strategy="mask",
            apply_to_input=True
        ),
        # Block API keys matching a regex detector
        PIIMiddleware(
            "api_key",
            detector=r"sk-[a-zA-Z0-9]{32}",
            strategy="block",
            apply_to_input=True
        )
    ]
)
```

**[24:15] Testing Redaction & Masking:**
```python
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "My email is john.doe@example.com and my card is 5105-1051-0510-5100. Can you help me?"
    }]
})
```
*Result:* The agent log reflects `[REDACTED_EMAIL]` and `****-****-****-5100`, protecting sensitive data from tool calls and logs.

**[25:40] Testing API Key Blocking:**
```python
try:
    agent.invoke({
        "messages": [{"role": "user", "content": "Here is my key: sk-abcdefghijklmnopqrstuvwxyz123456"}]
    })
except Exception as e:
    print(f"Blocked as expected: {e}")
```

---

### **26:30 – 30:56 | Section 4: Built-in Human-in-the-Loop Middleware**
**[26:30]** For sensitive actions (such as sending emails, deleting database records, or financial operations), we use **Human-in-the-Loop (HITL)** middleware.

A key requirement for HITL execution is a persistent **checkpointer** (such as `InMemorySaver`) to pause and resume state across user turns.

#### **Implementation:**
```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.checkpoint.memory import InMemorySaver
from langchain.types import Command
from langchain_core.tools import tool

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Search results for: {query}"

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a recipient."""
    return f"Email sent to {to} with subject: {subject}"

@tool
def delete_records(table: str, condition: str) -> str:
    """Delete records from the database."""
    return f"Deleted records from {table} where {condition}"

checkpointer = InMemorySaver()

hitl_agent = create_agent(
    model="gpt-4o",
    tools=[search_web, send_email, delete_records],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": True,        # Requires approval
                "delete_records": True,    # Requires approval
                "search_web": False        # Auto-approved
            }
        )
    ],
    checkpointer=checkpointer
)
```

**[29:00] Invoking and Approving:**
```python
config = {"configurable": {"thread_id": "session_001"}}
result = hitl_agent.invoke({
    "messages": [{"role": "user", "content": "Send an email to team@company.com about the Q4 results"}]
}, config=config)

# Agent pauses and waits for approval
# To approve:
approved_result = hitl_agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=config
)
```

**[30:16] Rejecting a Sensitive Action:**
```python
config2 = {"configurable": {"thread_id": "session_002"}}
hitl_agent.invoke({
    "messages": [{"role": "user", "content": "Delete all records from the users table where active=false"}]
}, config=config2)

# To reject:
rejected_result = hitl_agent.invoke(
    Command(resume={"decisions": [{"type": "reject", "reason": "Too risky, needs DBA review"}]}),
    config=config2
)
```

---

### **30:57 – 36:32 | Sections 5 & 6: Custom Before-Agent & After-Agent Guardrails**
**[30:57]** Custom guardrails inherit from `AgentMiddleware` and use the `@hook_config` decorator.

#### **Section 5: Custom Before-Agent Hook (Input Filter)**
Runs before the agent processes anything — resulting in **zero LLM cost** for blocked requests.
```python
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config

class ContentFilterMiddleware(AgentMiddleware):
    def __init__(self, banned_keywords: list[str]):
        super().__init__()
        self.banned_keywords = [kw.lower() for kw in banned_keywords]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return None
            
        first_message = messages[0]
        if first_message.type != "human":
            return None

        content = first_message.content.lower()
        for kw in self.banned_keywords:
            if kw in content:
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": "I cannot process requests containing inappropriate content. Please rephrase your request."
                    }],
                    "jump_to": "end"
                }
        return None
```

#### **Section 6: Custom After-Agent Hook (Output Safety)**
Runs after the agent produces a response but before the user sees it, validating compliance and appending necessary disclaimers.
```python
class SafetyGuardrailMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.safety_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_message = messages[-1]
        prompt = f"Evaluate if this response is safe and appropriate:\n{last_message.content}\nReply SAFE or UNSAFE."
        eval_result = self.safety_model.invoke([{"role": "user", "content": prompt}])

        if "UNSAFE" in eval_result.content.upper():
            return {
                "messages": [{
                    "role": "assistant",
                    "content": "I'm unable to provide that response. Please contact support."
                }],
                "jump_to": "end"
            }
        return None
```

---

### **36:33 – 38:15 | Section 7 & 8: Layered Architecture & Summary**
**[36:33]** In real-world production, you combine these layers into a unified stack inside the agent's `middleware` list:
1. **Layer 1:** `ContentFilterMiddleware` (Fast, zero-cost input filter)
2. **Layer 2:** `PIIMiddleware` (Input redaction & masking)
3. **Layer 3:** `HumanInTheLoopMiddleware` (Approval control for sensitive tools)
4. **Layer 4:** `SafetyGuardrailMiddleware` (Output safety & policy validation)

**[37:33]** In Section 8 of the notebook, we explore a full real-world **Healthcare Chatbot** project combining:
- Off-topic and harmful intent rejection
- Patient PII redaction
- Human-in-the-loop validation for booking medical appointments
- Medical disclaimer attachment on every health consultation response
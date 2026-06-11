# ABOUT.md

## Why this role

I have spent two years at Frontier.cool building production ML pipelines — serverless inference, multi-provider LLM fallback, Qdrant/DynamoDB hybrid stores. The jump from "infrastructure that serves AI" to "AI systems that drive business outcomes" is the one I want to make next. The contact-finder problem specifically interests me because it requires calibrated confidence, not just retrieval — exactly the class of problem where raw LLM output is insufficient and careful signal aggregation matters.

## How I work with AI tools

Claude Code is my primary pair programmer for code generation, refactoring, and surfacing edge cases. The judgment calls stay mine: architecture decisions, when an abstraction is leaky, when the model's suggested approach collapses important distinctions. A concrete example from this challenge: when structuring the confidence model, Claude suggested a weighted-average formula; I overrode it with an additive model with explicit per-signal caps because it makes the scoring explainable and auditable — you can point at a row and say "this scored 27 because registry/listing names conflicted (-20 penalty) and no enrichment email was found." A weighted average obscures that.

## Last project (Frontier.cool — ML enrichment pipeline)

**One ambiguity I faced:**
When integrating OpenAI and Google LLM providers via LangChain, I was unsure whether to implement provider fallback at the LangChain abstraction layer or directly against each SDK. LangChain makes the happy path clean but collapses provider-specific error codes — you cannot distinguish a rate limit (retry after backoff) from a content policy block (fail fast, do not retry) from a network timeout (retry immediately). Resolved by: dropped LangChain from the fallback path entirely, used raw provider SDKs with explicit exception handling per error class, kept LangChain only for prompt templating and output parsing where the abstraction was genuinely safe.

**One tradeoff I made:**
Chose DynamoDB for the chat history store. The access pattern was purely key-based — fetch all messages for a session by conversation ID — so DynamoDB was the right fit: consistent single-digit millisecond reads, no schema migrations, and append-only writes kept it simple. The tradeoff was accepting zero query flexibility: any cross-session analytics (e.g., conversations longer than N turns, sessions that hit a specific error) had to go through a separate export to S3 and Athena rather than a SQL query. I made that call consciously because the operational simplicity and throughput mattered more than ad-hoc querying for the core product path, and the analytics requirement was known but not latency-sensitive.

**One mistake I made:**
In the initial Blender rendering pipeline I returned null from failed render steps instead of throwing. This pushed null-checks into every downstream consumer; one downstream stage missed the check, and renders that failed at the compositing step were silently dropped overnight — no error surface, only caught the following morning when a client noticed missing outputs. Resolution was two-part: a backfill to reprocess the dropped renders, then a structural fix so failures throw instead of returning null, making the caller's context exit without completing. This became a project-wide rule: null returns are only valid for "record not found," never for operational failures.

**One review comment that changed my mind:**
A reviewer flagged that my provider fallback caught `Exception` broadly — it would catch out-of-memory panics and retry them in an infinite loop. My first reaction was "that's unlikely in practice." They were right to push back: broad catches are a latent footgun independent of current likelihood. I changed to an explicit allowlist of retriable exception types (rate limit, timeout, transient network) and re-raise everything else. Made me formalise retriable vs. non-retriable errors as a design decision upfront, not an afterthought.

## Anything I'd improve about this challenge

The PLAN.md template could make the "why my default assumption / what changes" format explicit in the instructions rather than just the template comment — I have seen candidates write great architectures but flat clarifying questions precisely because the format was buried. It is the highest-signal part of Stage A and deserves a call-out in the problem statement.

# Kel memory (long-term)

Kel remembers things across conversations using a small local **vector memory**,
and it does it without bloating the prompt.

## The idea (why it's token-cheap)

The model is stateless — anything it uses for a reply must be in its context at
that moment, and there is no way to make it "aware" of a memory without putting
that memory into context. The trick is **what** you put in:

- **Store everything on disk**, never in the base prompt.
- Each memory is turned into an *embedding* (a vector of numbers capturing its
  meaning).
- To recall, the query is embedded too and the **closest few** memories are found
  by cosine similarity — only those get injected.

So Kel can remember unlimited things while only ever sending the handful that are
relevant right now. That's retrieval-augmented generation (RAG).

## How Kel uses it

Realtime memory now has two layers:

- **`remember`** — saves a clear, self-contained fact ("Their dog is named Rex").
  Triggered whenever the user shares something personal or worth keeping.
- **Automatic recall before every normal response** — the completed transcript is
  embedded, the closest memories are selected, and only those notes are added to
  that response's instructions. Kel no longer has to remember to call a tool first.
- **`recall`** remains available when the model needs a second search with a more
  specific query.

You'll see `[Remembered: ...]` and `[Checked memory.]` in the terminal.

**Auto-capture (on by default):** beyond what Kel chooses to save, everything you
say is transcribed and stored automatically, so nothing is missed — you never have
to tell it to remember. Turn it off with `KEL_MEMORY_AUTO_CAPTURE=false` to go back
to Kel-decides-only. Recall happens before the current transcript is stored, so a
turn cannot retrieve itself as a fake "memory." Dictation in typing mode is never
stored.

## Modules

- `memory/store.py` — `MemoryStore`: save to a JSON file, recall top-K by cosine
  similarity. Pure logic, no model required (tested with a fake embedder).
- `memory/openai_embedder.py` — text → vector via OpenAI embeddings (cheap), behind
  an `Embedder` interface so a free local embedder can swap in later.
- `realtime/options.py` / `realtime/session.py` — the `remember`/`recall` tools and
  their handlers.

## Configuration

```text
KEL_MEMORY_ENABLED=true                 # set false to drop the memory tools
KEL_MEMORY_PATH=kel_memory.json         # where memories are stored (gitignored)
KEL_EMBEDDING_MODEL=text-embedding-3-small
KEL_MEMORY_TOP_K=5                      # how many memories to pull per recall
```

## Notes

- Memories persist in `kel_memory.json` between runs; delete the file to wipe
  Kel's memory.
- Embedding cost is tiny (fractions of a cent), and the savings are large: you
  never resend the whole memory, only the relevant few.
- Waiting for the completed transcript and memory lookup adds a small amount of
  latency before each answer, in exchange for reliable recall.

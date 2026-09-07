# 00 — Plain-English Glossary

Read this once. Every other document assumes these words.

---

### LLM
The AI model itself (Gemini, Claude). It only does one thing: text in, text
out. It cannot click, cannot open files, cannot see your screen. Everything
DIVYASTRA does beyond talking comes from tools we hand it.

### Tool
A function the LLM is allowed to call. We describe it ("`click(element_id)` —
clicks a button"), and when the model wants it, it emits a request; *our code*
runs it and hands back the result. The model never executes anything itself.

### Agent loop
The cycle that turns a model into an assistant:

```
task → model thinks → model asks for a tool → we run it →
we give back the result → model thinks again → ... → model says "done"
```

That loop is the entire idea behind "AI agents." It is about 40 lines of code.
Everything else is plumbing around it.

### MCP (Model Context Protocol)
A shared standard for *how a program offers tools to an AI*. Think of it as USB
for AI tools. Before MCP, connecting a model to WhatsApp meant custom glue for
that exact model. With MCP you write one **MCP server** and any MCP-speaking
brain can use it — Claude Code, our core, anything later.

**Why this decides our architecture:** if every capability is an MCP server,
each one is a separate program we can test on its own, replace on its own, and
break on its own without touching the rest. That is the anti-tangle mechanism.

### MCP server / MCP client
- **Server** = the thing that *offers* tools (our desktop limb, our mail limb).
- **Client** = the thing that *uses* them (Claude Code, later our core).

They talk over **stdio** — plain text in and out of a program — so an MCP
server is just a normal program, not a website. Nothing is exposed to the
internet.

### `.mcp.json`
One config file listing which MCP servers exist and how to start them. This is
how Claude Code learns about our limbs. It is the seam of the whole project.

### Accessibility tree (UIA)
Windows keeps a hidden, structured description of every window: "this is a
button named Save, at this position." Screen readers use it. We use it too.

This is **much better than looking at pixels**: it is exact, fast, free, and
does not need a GPU. Reading a button's name beats guessing from a screenshot.
Vision is our fallback, not our default.

### Wake word
A tiny model that runs constantly and listens for one phrase. It costs no money
and no tokens — it is not an LLM, just a small pattern matcher. It exists so
the expensive brain stays asleep until called.

### STT / TTS
- **STT** (speech-to-text): my voice → words. We use whisper.cpp, local.
- **TTS** (text-to-speech): words → her voice. We use Kokoro, local.

### Token
The unit LLMs are billed in — roughly ¾ of a word, counted both directions.
"Burning tokens" = paying for the model to read and write. Anything that
happens without calling the model (wake word, STT, TTS, clicking) costs zero
tokens. Our design pushes as much as possible into that free zone.

### Channel
Any route a task can arrive by: Telegram, spoken voice, a hotkey, a timer.
All of them convert into the same little object — a **Task** — before the core
sees it. The core never knows or cares where a task came from.

### Adapter
A small file whose only job is "translate our words into some vendor's words."
`tts.speak(text)` is ours; inside, it calls Kokoro. Swap to ElevenLabs later
and only that one file changes. Rule 4 in CLAUDE.md is about this.

### Headless
Running without a visible window. A *headless browser* loads pages invisibly.
We mostly do **not** want headless — we want the real browser with real logins.

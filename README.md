# AIKubeHelper

AIKubeHelper is a terminal-first assistant for Kubernetes incident response. It weaves together a live POSIX shell, rich terminal UI, and GPT-powered guidance so you can diagnose and fix cluster issues without ever leaving the command line. Unlike generic chatbots or search engines, AIKubeHelper ingests your actual shell output, keeps it in context, and responds with concrete kubectl instructions you can execute immediately.

---

## Why AIKubeHelper?

Troubleshooting Kubernetes often requires juggling multiple tools: you run commands in a terminal, copy the logs into ChatGPT, browse Stack Overflow threads, and then paste the suggested fix back into your shell. AIKubeHelper compresses that loop into a single keyboard-driven workflow. The app continuously captures what your cluster prints, lets you summon an AI expert with a keystroke, and even extracts ready-to-run remediation commands for you.

---

## Highlights at a Glance

| Capability | What it means in practice |
| ---------- | ------------------------ |
| **Live terminal feed** | AIKubeHelper spawns a real Bash shell (via `pty.fork`) and streams stdout/stderr into a scrollable panel. You see the same thing you would in any terminal emulator, including color, prompts, and interactive command output. |
| **Context-aware AI call** | Type `808` (mnemonic: HTTP status code for "AI help") to send the last `BUFFER_LINES` of shell history to OpenAI's `gpt-4.1-mini` with a Kubernetes specialist system prompt. The model replies with root-cause analysis, validation steps, and commands tailored to *your* live session. |
| **Command extraction & execution** | Press `r` ("run") to parse the most recent AI answer, pull out the first shell command inside a code block or `$` prompt, and execute it automatically in the same shell. |
| **Rich text interaction** | The custom `SelectableRichLog` widget adds keyboard/mouse text selection, copy (`Ctrl+C`), select-all (`Ctrl+A`), and paste-to-input (`Ctrl+V`) shortcuts—features usually missing from TUIs. |
| **Human-in-the-loop safeguards** | Suggestions appear in a dedicated panel. You can review, edit, or discard them before deciding to run anything. The tool never executes hidden commands. |

---

## How It Differs from Other Tools

| Tool | What you normally do | Why AIKubeHelper is different |
| ---- | -------------------- | ---------------------------- |
| **Cursor** (AI IDE) | Works best when editing files inside an IDE and relies on static project context. | AIKubeHelper is optimized for *operational* work: it hooks into a live shell, captures streaming logs, and gives commands you can execute immediately instead of code edits. |
| **ChatGPT / Claude web UI** | Manually copy/paste terminal output into a browser, switch tabs, then bring answers back. | No copy-paste relay. AIKubeHelper auto-feeds the last 20 lines of shell history to the model, so context always matches the current state of your cluster. |
| **Stack Overflow** | Search for a similar error, interpret multiple answers, and adapt them to your environment. | AIKubeHelper analyzes *your* logs in real time and returns prescriptive remediation steps, rather than generic threads that may or may not fit. |
| **Google** | Requires keyword crafting, skimming docs, and building the fix yourself. | AIKubeHelper condenses diagnosis and command construction into one interaction, producing runnable snippets you can apply instantly. |
| **Traditional CLIs** (kubectl, k9s) | Provide raw data but no guided reasoning. | AIKubeHelper overlays an AI mentor on top of familiar CLI tools, turning observations into decisions while keeping you in full control of execution. |

---

## Under the Hood

* **UI layer:** [Textual](https://textual.textualize.io/) powers a three-pane layout (`shell_panel`, `input_box`, `suggestion_panel`) with custom CSS for focus hints.
* **Shell integration:** Python's `pty` module forks a Bash child process and pipes its output through non-blocking `select.select`, guaranteeing responsive updates without freezing the UI.
* **Context buffer:** `BUFFER_LINES` controls how much recent history is sent to the model. Adjust it to trade off context depth vs. token usage.
* **AI client:** `openai.chat.completions.create` drives the conversation with a Kubernetes-specific system prompt. The default model is `gpt-4.1-mini`, but any compatible OpenAI model string will work.
* **Clipboard helpers:** Cross-platform fallbacks (`xclip`, `wl-copy`, `pbcopy`, or an in-app buffer) make copy/paste workable even inside headless terminals.
* **Command parser:** `extract_command` scans AI responses for fenced code blocks, `$`-prefixed lines, or plain text commands, returning the first plausible shell snippet.

---

## Quick Start

1. **Install Python dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install textual openai python-dotenv
   ```

2. **Provide your OpenAI API key**

   - Option A: create a `.env` file in the project root with `OPENAI_API_KEY=sk-...`
   - Option B: export it in your shell before launching (`export OPENAI_API_KEY=sk-...`).

3. **Run the TUI**

   ```bash
   python kubeHelp2.py
   ```

You should see a terminal-like pane (live Bash), an input box, and an empty suggestions pane ready for AI responses.

---

## Daily Workflow

1. **Run kubectl commands normally.** Everything you type (except the special `808` trigger) is executed directly in the Bash shell.
2. **Hit `808` when stuck.** The tool compiles the latest console output and asks the AI, “What is the likely issue here, and what steps should I take to fix it?”
3. **Review the answer.** The suggestion panel highlights diagnoses, validation steps, and code blocks with kubectl commands.
4. **Execute with `r`.** If you trust the recommendation, press `r` to run the first extracted command. You can also copy/edit it manually.
5. **Iterate.** Because the shell history is preserved, subsequent AI calls incorporate results from the previous steps without extra work.

> 💡 **Tip:** The sample `brokenDeploy.yaml` file contains multiple issues (bad port, missing secrets, etc.). Apply it to a test cluster and use AIKubeHelper to walk through the remediation process.

---

## Keyboard & Mouse Shortcuts

| Shortcut | Scope | Action |
| -------- | ----- | ------ |
| `Enter` | Input box | Run typed shell command (or trigger AI when value is `808`). |
| `Ctrl+C` | Focused pane | Copy selected text; falls back to entire buffer. |
| `Ctrl+A` | Focused pane | Select all text. |
| `Ctrl+V` | Global | Paste clipboard contents into the input box. |
| `Esc` | Global | Clear any text selection. |
| `Tab` / `Shift+Tab` | Global | Cycle focus between shell, input, and suggestion panes. |
| `r` | Global | Extract and run the first command from the suggestion pane. |
| `q` | Global | Quit the app. |

Mouse dragging inside the shell or suggestion panels also creates text selections you can copy.

---

## Working with Different Models or Prompts

* Change the `MODEL` constant near the top of `kubeHelp2.py` to switch models.
* Edit the system prompt in `get_ai_suggestion` if you prefer a different troubleshooting tone (e.g., SRE-style RCA, more verbose explanations, etc.).
* Increase `BUFFER_LINES` for more context or reduce it to save tokens.

---

## Roadmap Ideas

* Seamless support for Anthropic, Azure OpenAI, or self-hosted LLM endpoints.
* Built-in "dry-run" mode that simulates commands before execution.
* Automatic summarization of long kubectl outputs.
* Templated runbooks for recurring incident archetypes.

Contributions and feature suggestions are welcome—open an issue or submit a PR describing the behavior you need for your team’s incident workflow.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
| ------- | ------------ | --- |
| `OPENAI_API_KEY not set` appears in the suggestion pane. | Missing environment variable. | Add it to `.env` or export it before launching. |
| `Paste failed` notification. | Clipboard tools (`xclip`, `wl-copy`, `pbpaste`) unavailable. | Install the relevant utility or rely on the internal clipboard buffer. |
| The `r` shortcut does nothing. | No command detected in the AI response. | Manually copy the desired line or adjust `extract_command` to fit your team's prompt style. |
| High token usage or slow responses. | Large context history or verbose prompt. | Lower `BUFFER_LINES` or switch to a faster/cheaper model. |

---

## License

This repository does not currently include an explicit license. Please contact the author before using it in production or redistributing modified versions.


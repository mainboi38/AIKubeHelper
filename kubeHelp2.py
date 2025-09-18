import os
import pty
import select
import asyncio
import re
from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog
from textual.containers import Vertical
from textual import events

from dotenv import load_dotenv
import openai

# --- Load API key from .env if available ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- CONFIG ---
MODEL = "gpt-4.1-mini"
BUFFER_LINES = 20
# ---------------


class SelectableRichLog(RichLog):
    """Extended RichLog with text selection and copy functionality"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_focus = True  # Make it focusable for keyboard events
        self.selection_start = None
        self.selection_end = None
        self.selecting = False
        self.lines_cache = []
    
    def on_mount(self) -> None:
        super().on_mount()
        self.update_lines_cache()
    
    def update_lines_cache(self):
        """Update internal cache of lines for selection"""
        try:
            text = self.export_text()
            self.lines_cache = text.splitlines() if text else []
        except:
            self.lines_cache = []
    
    def write(self, content, **kwargs):
        """Override write to update cache"""
        result = super().write(content, **kwargs)
        self.update_lines_cache()
        return result
    
    def clear(self):
        """Override clear to reset selection"""
        super().clear()
        self.selection_start = None
        self.selection_end = None
        self.selecting = False
        self.lines_cache = []
    
    async def on_click(self, event) -> None:
        """Handle mouse clicks for text selection"""
        if not self.lines_cache:
            return
            
        # Calculate line and column from click position
        line = min(event.y, len(self.lines_cache) - 1) if self.lines_cache else 0
        col = event.x
        
        if event.button == 1:  # Left click
            self.selection_start = (line, col)
            self.selection_end = None
            self.selecting = True
    
    async def on_mouse_move(self, event) -> None:
        """Handle mouse movement for text selection"""
        if self.selecting and self.selection_start:
            line = min(event.y, len(self.lines_cache) - 1) if self.lines_cache else 0
            col = event.x
            self.selection_end = (line, col)
    
    async def on_mouse_up(self, event) -> None:
        """Handle mouse release to end selection"""
        if self.selecting:
            self.selecting = False
    
    def get_selected_text(self) -> str:
        """Get currently selected text"""
        if not self.selection_start or not self.selection_end or not self.lines_cache:
            return ""
        
        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end
        
        # Ensure start comes before end
        if start_line > end_line or (start_line == end_line and start_col > end_col):
            start_line, start_col, end_line, end_col = end_line, end_col, start_line, start_col
        
        selected_lines = []
        
        if start_line == end_line:
            # Single line selection
            if start_line < len(self.lines_cache):
                line = self.lines_cache[start_line]
                selected_lines.append(line[start_col:end_col])
        else:
            # Multi-line selection
            for i in range(start_line, min(end_line + 1, len(self.lines_cache))):
                line = self.lines_cache[i]
                if i == start_line:
                    selected_lines.append(line[start_col:])
                elif i == end_line:
                    selected_lines.append(line[:end_col])
                else:
                    selected_lines.append(line)
        
        return "\n".join(selected_lines)
    
    async def key_ctrl_c(self) -> None:
        """Copy selected text or all text to clipboard"""
        try:
            # First try to get selected text
            selected_text = self.get_selected_text()
            
            if selected_text.strip():
                self.app.copy_to_clipboard(selected_text)
                self.app.notify(f"Copied selection ({len(selected_text)} chars)")
            else:
                # Fall back to copying all text
                text = self.export_text()
                if text.strip():
                    self.app.copy_to_clipboard(text)
                    self.app.notify("Copied all text to clipboard!")
                else:
                    self.app.notify("No text to copy!")
        except Exception as e:
            self.app.notify(f"Copy failed: {e}")
    
    async def key_ctrl_a(self) -> None:
        """Select all text"""
        if self.lines_cache:
            self.selection_start = (0, 0)
            last_line = len(self.lines_cache) - 1
            last_col = len(self.lines_cache[last_line]) if self.lines_cache else 0
            self.selection_end = (last_line, last_col)
            self.app.notify("Selected all text")
    
    async def key_escape(self) -> None:
        """Clear selection"""
        self.selection_start = None
        self.selection_end = None
        self.selecting = False


class KubeAITUI(App):
    CSS = """
    Vertical {
        height: 100%;
    }
    RichLog.shell {
        height: 55%;
        border: solid green;
    }
    RichLog.shell:focus {
        border: solid #00ff00;
    }
    Input {
        height: 3;
        border: solid yellow;
    }
    Input:focus {
        border: solid #ffff00;
    }
    RichLog.suggestions {
        height: 40%;
        border: solid cyan;
    }
    RichLog.suggestions:focus {
        border: solid #00ffff;
    }
    """

    BINDINGS = [
        ("ctrl+c", "copy_focused", "Copy"),
        ("ctrl+a", "select_all_focused", "Select All"),
        ("ctrl+v", "paste_to_input", "Paste"),
        ("escape", "clear_selection", "Clear Selection"),
        ("q", "quit", "Quit"),
        ("r", "run_ai_command", "Run AI Command"),
        ("tab", "focus_next", "Next Focus"),
        ("shift+tab", "focus_previous", "Previous Focus"),
    ]

    def __init__(self):
        super().__init__()
        self.history = []
        self.clipboard_content = ""
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.execvp("bash", ["bash"])  # child: run shell

    def compose(self) -> ComposeResult:
        with Vertical():
            self.shell_panel = SelectableRichLog(classes="shell", wrap=False, highlight=False)
            self.input_box = Input(placeholder="Type a command and press Enter… (Ctrl+V to paste)")
            self.suggestion_panel = SelectableRichLog(classes="suggestions", wrap=True, highlight=False)
            yield self.shell_panel
            yield self.input_box
            yield self.suggestion_panel

    async def on_mount(self) -> None:
        self.set_interval(0.1, self.read_shell)
        if not openai.api_key:
            self.suggestion_panel.write("[ERROR] OPENAI_API_KEY not set. Put it in .env or export it.")
        
        # Set initial focus to input
        self.input_box.focus()

    def read_shell(self):
        """Read data from shell and update panel."""
        r, _, _ = select.select([self.fd], [], [], 0)
        if self.fd in r:
            output = os.read(self.fd, 1024).decode(errors="ignore")
            if output:
                self.shell_panel.write(output, scroll_end=True)
                for line in output.splitlines():
                    self.history.append(line)
                self.history[:] = self.history[-BUFFER_LINES:]

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle typed commands."""
        cmd = event.value.strip()
        self.input_box.value = ""

        if cmd == "808":
            await self.get_ai_suggestion()
        else:
            # Clear old output before running new command
            self.shell_panel.clear()
            os.write(self.fd, (cmd + "\n").encode())

    async def on_key(self, event):
        """Handle global hotkeys."""
        key = event.key.lower()

        # Don't interfere with input field typing
        if self.input_box.has_focus and key not in ["q", "ctrl+c", "ctrl+v", "tab", "shift+tab"]:
            return

        if key == "q":
            self.exit()
            return

        if key == "r":
            await self.action_run_ai_command()
            return

    async def action_copy_focused(self) -> None:
        """Copy content from the currently focused panel."""
        focused = self.focused
        if isinstance(focused, SelectableRichLog):
            await focused.key_ctrl_c()
        elif focused == self.input_box:
            # Copy input box content
            text = self.input_box.value
            if text:
                self.copy_to_clipboard(text)
                self.notify("Input copied to clipboard!")

    async def action_select_all_focused(self) -> None:
        """Select all text in the currently focused panel."""
        focused = self.focused
        if isinstance(focused, SelectableRichLog):
            await focused.key_ctrl_a()

    async def action_clear_selection(self) -> None:
        """Clear selection in all panels."""
        if isinstance(self.shell_panel, SelectableRichLog):
            await self.shell_panel.key_escape()
        if isinstance(self.suggestion_panel, SelectableRichLog):
            await self.suggestion_panel.key_escape()

    async def action_paste_to_input(self) -> None:
        """Paste clipboard content to input box."""
        try:
            # Try to get clipboard content (this might vary by system)
            import subprocess
            
            # Try different clipboard commands based on the system
            try:
                # Linux (X11)
                result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                      capture_output=True, text=True, timeout=1)
                if result.returncode == 0:
                    clipboard_text = result.stdout
                else:
                    raise subprocess.CalledProcessError(1, 'xclip')
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    # Linux (Wayland)
                    result = subprocess.run(['wl-paste'], 
                                          capture_output=True, text=True, timeout=1)
                    if result.returncode == 0:
                        clipboard_text = result.stdout
                    else:
                        raise subprocess.CalledProcessError(1, 'wl-paste')
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        # macOS
                        result = subprocess.run(['pbpaste'], 
                                              capture_output=True, text=True, timeout=1)
                        clipboard_text = result.stdout
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Fallback to internal clipboard
                        clipboard_text = self.clipboard_content

            if clipboard_text:
                # Clean up the text (remove newlines for single line paste)
                clipboard_text = clipboard_text.strip().replace('\n', ' ')
                self.input_box.value = clipboard_text
                self.input_box.focus()
                self.notify("Pasted from clipboard!")
            else:
                self.notify("Clipboard is empty!")
                
        except Exception as e:
            self.notify(f"Paste failed: {e}")

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to system clipboard."""
        try:
            import subprocess
            
            # Try different clipboard commands based on the system
            try:
                # Linux (X11)
                subprocess.run(['xclip', '-selection', 'clipboard'], 
                             input=text, text=True, check=True, timeout=1)
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    # Linux (Wayland)
                    subprocess.run(['wl-copy'], 
                                 input=text, text=True, check=True, timeout=1)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        # macOS
                        subprocess.run(['pbcopy'], 
                                     input=text, text=True, check=True, timeout=1)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Fallback to internal storage
                        self.clipboard_content = text
                        
        except Exception:
            # Fallback to internal storage
            self.clipboard_content = text

    async def action_run_ai_command(self) -> None:
        """Extract and run command from AI suggestions."""
        cmd = self.extract_command(self.suggestion_panel.export_text())
        if cmd:
            self.shell_panel.write(f"\n[AI RUN] {cmd}\n")
            os.write(self.fd, (cmd + "\n").encode())
        else:
            self.shell_panel.write("\n[AI RUN] No command found.\n")

    async def get_ai_suggestion(self):
        context = "\n".join(self.history)
        try:
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a Kubernetes troubleshooting expert.provide clear, step-by-step instructions to identify and fix the issue. Be concise, accurate, and include necessary kubectl or system commands inside code blocks. If the problem is unclear, list possible root causes and suggest diagnostic steps."},
                    {"role": "user", "content": f"Terminal Output:\n\n```shell\n{context}\n```\n\nWhat is the likely issue here, and what exact steps should I take to fix it?"}
                ]
            )
            suggestion = response.choices[0].message.content.strip()
        except Exception as e:
            suggestion = f"[AI ERROR] {e}"

        self.suggestion_panel.clear()
        self.suggestion_panel.write(suggestion, scroll_end=True)

    def extract_command(self, text: str) -> str | None:
        """Extract command from AI suggestion text."""
        match = re.search(r"```(?:bash)?\n(.+?)\n```", text, re.S)
        if match:
            return match.group(1).strip()
        for line in text.splitlines():
            if line.strip().startswith("$"):
                return line.strip().lstrip("$").strip()
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return None


if __name__ == "__main__":
    app = KubeAITUI()
    app.run()
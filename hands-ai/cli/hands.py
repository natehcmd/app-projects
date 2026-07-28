#!/usr/bin/env python3
"""
Hands AI CLI — Route AI requests from your terminal.
Talks to the Hands AI daemon on port 7721.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

DAEMON_URL = "http://127.0.0.1:7721"
DAEMON_TIMEOUT = 5
console = Console()


# ── Daemon helpers ───────────────────────────────────────────────────────────

def daemon_running() -> bool:
    try:
        r = requests.get(f"{DAEMON_URL}/health", timeout=DAEMON_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def start_daemon_bg():
    """Start the Hands AI daemon in the background."""
    agent_dir = Path(__file__).resolve().parent.parent / "agent"
    log_path = Path.home() / ".hands" / "daemon.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a") as log:
        # Prefer venv python for the daemon
        venv_python = agent_dir / ".venv" / "bin" / "python3"
        python_bin = str(venv_python) if venv_python.exists() else sys.executable

        proc = subprocess.Popen(
            [
                python_bin,
                "-m", "uvicorn",
                "main:app",
                "--host", "127.0.0.1",
                "--port", "7721",
            ],
            cwd=str(agent_dir),
            stdout=log,
            stderr=log,
            start_new_session=True,
        )

    console.print(f"[dim]Starting Hands AI daemon (pid {proc.pid})...[/dim]")

    # Wait up to 8 seconds
    for _ in range(16):
        time.sleep(0.5)
        if daemon_running():
            console.print("[green]Daemon started.[/green]")
            return True

    console.print("[red]Daemon failed to start. Check ~/.hands/daemon.log[/red]")
    return False


def ensure_daemon():
    """Make sure daemon is running, start it if not."""
    if not daemon_running():
        console.print("[yellow]Hands AI daemon not running — starting it...[/yellow]")
        if not start_daemon_bg():
            sys.exit(1)


def api_get(path: str) -> dict:
    try:
        r = requests.get(f"{DAEMON_URL}{path}", timeout=DAEMON_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        console.print("[red]Cannot reach Hands AI daemon. Run: hands start[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]API error: {e}[/red]")
        sys.exit(1)


def api_post(path: str, data: dict) -> dict:
    try:
        r = requests.post(f"{DAEMON_URL}{path}", json=data, timeout=DAEMON_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.ConnectionError:
        console.print("[red]Cannot reach Hands AI daemon. Run: hands start[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]API error: {e}[/red]")
        sys.exit(1)


def stream_chat(messages: list[dict]) -> str:
    """Stream a chat request, printing tokens as they arrive. Returns full response."""
    try:
        with requests.post(
            f"{DAEMON_URL}/chat",
            json={"message": messages[-1]["content"], "stream": True, "history": messages[:-1]},
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            full = []
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    payload = line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        token = chunk.get("token", "")
                        if token:
                            console.print(token, end="", highlight=False)
                            full.append(token)
                    except json.JSONDecodeError:
                        continue
            console.print()  # newline after response
            return "".join(full)
    except requests.ConnectionError:
        console.print("[red]Cannot reach Hands AI daemon.[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return ""


def full_chat(messages: list[dict]) -> str:
    """Send a non-streaming chat request. Returns full response."""
    try:
        r = requests.post(
            f"{DAEMON_URL}/chat",
            json={"message": messages[-1]["content"], "stream": False, "history": messages[:-1]},
            timeout=120,
        )
        r.raise_for_status()
        response = r.json().get("response", "")
        if response:
            console.print(response, highlight=False)
        return response
    except requests.ConnectionError:
        console.print("[red]Cannot reach Hands AI daemon.[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return ""


# ── CLI root ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Hands AI — Local AI Orchestration. Routes requests to Ollama, Claude, or OpenAI."""
    pass


# ── hands chat ────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("message", nargs=-1)
@click.option("--no-stream", is_flag=True, default=False, help="Return full response at once")
def chat(message, no_stream):
    """Chat with the active AI model. No args = interactive REPL mode."""
    ensure_daemon()

    if message:
        # Single shot
        user_text = " ".join(message)
        messages = [{"role": "user", "content": user_text}]
        console.print()
        if no_stream:
            full_chat(messages)
        else:
            stream_chat(messages)
    else:
        # Interactive REPL
        health = api_get("/health")
        console.print(Panel(
            f"[bold cyan]Hands AI[/bold cyan] interactive mode\n"
            f"Model: [green]{health.get('active_provider', '?')} / {health.get('active_model', '?')}[/green]\n"
            f"[dim]Ctrl+C or type 'exit' to quit[/dim]",
            border_style="cyan",
        ))

        conversation: list[dict] = []

        while True:
            try:
                user_input = console.input("[bold cyan]You>[/bold cyan] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/dim]")
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "bye"):
                console.print("[dim]Goodbye.[/dim]")
                break
            if user_input.lower() == "/clear":
                conversation = []
                console.print("[dim]Conversation cleared.[/dim]")
                continue
            if user_input.lower() == "/model":
                h = api_get("/health")
                console.print(f"[green]{h.get('active_provider')} / {h.get('active_model')}[/green]")
                continue

            conversation.append({"role": "user", "content": user_input})
            console.print("[bold green]Hands AI>[/bold green] ", end="")
            response = full_chat(conversation) if no_stream else stream_chat(conversation)
            if response:
                conversation.append({"role": "assistant", "content": response})


# ── hands model ───────────────────────────────────────────────────────────────

@cli.group()
def model():
    """Manage AI models."""
    pass


@model.command("list")
def model_list():
    """List all available models across all providers."""
    ensure_daemon()
    data = api_get("/models")
    health = api_get("/health")
    active_provider = health.get("active_provider")
    active_model = health.get("active_model")

    models = data.get("models", [])

    table = Table(title="Available Models", border_style="cyan", show_lines=False)
    table.add_column("", width=2)
    table.add_column("Provider", style="dim")
    table.add_column("Model ID")
    table.add_column("Available", justify="center")

    # Group by provider
    by_provider: dict[str, list] = {}
    for m in models:
        p = m["provider"]
        by_provider.setdefault(p, []).append(m)

    provider_order = ["ollama", "claude", "openai"]
    provider_labels = {"ollama": "Local (Ollama)", "claude": "Anthropic Claude", "openai": "OpenAI / Codex"}

    for p in provider_order:
        if p not in by_provider:
            continue
        for m in by_provider[p]:
            is_active = (m["provider"] == active_provider and m["id"] == active_model)
            marker = "[bold cyan]*[/bold cyan]" if is_active else " "
            avail = "[green]●[/green]" if m.get("available") else "[dim]○[/dim]"
            table.add_row(marker, provider_labels.get(p, p), m["id"], avail)

    console.print(table)
    console.print("[dim]* = active  ● = available  ○ = unavailable[/dim]")


@model.command("set")
@click.argument("model_id")
def model_set(model_id):
    """Switch active model. E.g.: hands model set claude-sonnet-4-6"""
    ensure_daemon()

    # Try to infer provider from model_id
    data = api_get("/models")
    models = data.get("models", [])

    provider = None
    for m in models:
        if m["id"] == model_id or m["id"].endswith(f"/{model_id}") or model_id.endswith(m["id"]):
            provider = m["provider"]
            break

    # Manual prefix detection as fallback
    if not provider:
        if any(model_id.startswith(p) for p in ["claude-", "claude/"]):
            provider = "claude"
        elif any(model_id.startswith(p) for p in ["gpt-", "o3", "o4", "openai/"]):
            provider = "openai"
        else:
            provider = "ollama"

    with console.status(f"Switching to [cyan]{model_id}[/cyan]..."):
        result = api_post("/model/set", {"provider": provider, "model": model_id})

    if result.get("ok"):
        console.print(f"[green]Active model:[/green] {provider} / {model_id}")
    else:
        console.print(f"[red]Failed to set model: {result}[/red]")


@model.command("show")
def model_show():
    """Show the currently active provider and model."""
    ensure_daemon()
    health = api_get("/health")
    console.print(
        f"[bold]Active:[/bold] [cyan]{health.get('active_provider', '?')}[/cyan] / "
        f"[green]{health.get('active_model', '?')}[/green]"
    )


# ── hands status ──────────────────────────────────────────────────────────────

@cli.command()
def status():
    """Show daemon status, active model, and provider availability."""
    if not daemon_running():
        console.print("[red]Hands AI daemon is not running.[/red]")
        console.print("[dim]Start it with: hands start[/dim]")
        return

    health = api_get("/health")
    providers = health.get("providers", {})

    console.print(Panel(
        f"[bold green]Hands AI daemon is running[/bold green]\n\n"
        f"Active provider: [cyan]{health.get('active_provider', '?')}[/cyan]\n"
        f"Active model:    [cyan]{health.get('active_model', '?')}[/cyan]\n\n"
        f"[bold]Providers:[/bold]\n"
        + "\n".join(
            f"  {'[green]●[/green]' if avail else '[dim]○[/dim]'} {name}"
            for name, avail in providers.items()
        ),
        title="Hands AI Status",
        border_style="cyan",
    ))


# ── hands start / stop ─────────────────────────────────────────────────────────

@cli.command()
def start():
    """Start the Hands AI daemon in the background."""
    if daemon_running():
        console.print("[green]Daemon is already running.[/green]")
        return
    start_daemon_bg()


@cli.command()
def stop():
    """Stop the Hands AI daemon."""
    pid_file = Path.home() / ".hands" / "daemon.pid"

    # Try to find process by port
    try:
        result = subprocess.run(
            ["lsof", "-ti", "tcp:7721"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().split()
        if pids:
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
            console.print("[green]Daemon stopped.[/green]")
        else:
            console.print("[yellow]No daemon process found on port 7721.[/yellow]")
    except Exception as e:
        console.print(f"[red]Could not stop daemon: {e}[/red]")


# ── hands config ──────────────────────────────────────────────────────────────

@cli.group()
def config():
    """Manage Hands AI configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value. Keys: anthropic-key, openai-key, ollama-host, provider, model"""
    ensure_daemon()

    key_map = {
        "anthropic-key": "anthropic_api_key",
        "openai-key": "openai_api_key",
        "ollama-host": "ollama_host",
        "provider": "active_provider",
        "model": "active_model",
    }

    internal_key = key_map.get(key, key)
    result = api_post("/config", {internal_key: value})

    if result.get("ok"):
        if "key" in key:
            console.print(f"[green]API key saved.[/green]")
        else:
            console.print(f"[green]{key} = {value}[/green]")
    else:
        console.print(f"[red]Failed: {result}[/red]")


@config.command("show")
def config_show():
    """Show current configuration (API keys are masked)."""
    ensure_daemon()
    cfg = api_get("/config")

    table = Table(border_style="dim", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    for k, v in cfg.items():
        table.add_row(k, str(v) if v else "[dim](not set)[/dim]")

    console.print(table)


# ── hands claude / codex passthroughs ─────────────────────────────────────────

@cli.command(name="claude", context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def claude_passthrough(args):
    """Pass commands directly to the claude CLI."""
    try:
        os.execvp("claude", ["claude"] + list(args))
    except FileNotFoundError:
        console.print("[red]claude CLI not found. Install it with: npm i -g @anthropic-ai/claude-code[/red]")
        sys.exit(1)


@cli.command(name="codex", context_settings={"ignore_unknown_options": True})
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def codex_passthrough(args):
    """Pass commands directly to the openai or codex CLI."""
    for bin_name in ["codex", "openai"]:
        try:
            os.execvp(bin_name, [bin_name] + list(args))
        except FileNotFoundError:
            continue
    console.print("[red]Neither 'codex' nor 'openai' CLI found.[/red]")
    sys.exit(1)


# ── entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()

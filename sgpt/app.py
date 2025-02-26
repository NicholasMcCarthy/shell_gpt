# To allow users to use arrow keys in the REPL.
import readline  # noqa: F401
import sys
import os 
import typer
from click import BadArgumentUsage, MissingParameter
from click.types import Choice

from sgpt.config import cfg
from sgpt.handlers.chat_handler import ChatHandler
from sgpt.handlers.default_handler import DefaultHandler
from sgpt.handlers.repl_handler import ReplHandler
from sgpt.role import DefaultRoles, SystemRole
from sgpt.utils import get_edited_prompt, install_shell_integration, run_command


def main(
    prompt: str = typer.Argument(
        None,
        show_default=False,
        help="The prompt to generate completions for.",
    ),
    model: str = typer.Option(
        cfg.get("DEFAULT_MODEL"),
        help="Large language model to use.",
    ),
    temperature: float = typer.Option(
        0.1,
        min=0.0,
        max=2.0,
        help="Randomness of generated output.",
    ),
    top_probability: float = typer.Option(
        1.0,
        min=0.1,
        max=1.0,
        help="Limits highest probable tokens (words).",
    ),
    shell: bool = typer.Option(
        False,
        "--shell",
        "-s",
        help="Generate and execute shell commands.",
        rich_help_panel="Assistance Options",
    ),
    describe_shell: bool = typer.Option(
        False,
        "--describe-shell",
        "-d",
        help="Describe a shell command.",
        rich_help_panel="Assistance Options",
    ),
    code: bool = typer.Option(
        False,
        help="Generate only code.",
        rich_help_panel="Assistance Options",
    ),
    editor: bool = typer.Option(
        False,
        help="Open $EDITOR to provide a prompt.",
    ),
    cache: bool = typer.Option(
        True,
        help="Cache completion results.",
    ),
    chat: str = typer.Option(
        None,
        help="Follow conversation with id, " 'use "temp" for quick session.',
        rich_help_panel="Chat Options",
    ),
    repl: str = typer.Option(
        None,
        help="Start a REPL (Read–eval–print loop) session.",
        rich_help_panel="Chat Options",
    ),
    show_chat: str = typer.Option(
        None,
        '--show-chat', 
        '-sc',
        help="Show all messages from provided chat id.",
        callback=ChatHandler.show_messages_callback,
        rich_help_panel="Chat Options",
    ),
    list_chats: bool = typer.Option(
        False,
        '--list-chat', 
        '-lc',
        help="List all existing chat ids.",
        callback=ChatHandler.list_ids,
        rich_help_panel="Chat Options",
    ),
    
    last_chat: bool = typer.Option(
        False,
        '--last-chat', 
        '-last',
        help="Use most recent chat id.",
        rich_help_panel="Chat Options",
    ),
    role: str = typer.Option(
        None,
        '--role', 
        '-r',
        help="System role for GPT model.",
        rich_help_panel="Role Options",
    ),
    create_role: str = typer.Option(
        None,
        help="Create role.",
        callback=SystemRole.create,
        rich_help_panel="Role Options",
    ),
    show_role: str = typer.Option(
        None,
        help="Show role.",
        callback=SystemRole.show,
        rich_help_panel="Role Options",
    ),
    list_roles: bool = typer.Option(
        False,
        help="List roles.",
        callback=SystemRole.list,
        rich_help_panel="Role Options",
    ),
    install_integration: bool = typer.Option(
        False,
        help="Install shell integration (ZSH and Bash only)",
        callback=install_shell_integration,
        hidden=True,  # Hiding since should be used only once.
    ),
) -> None:
    stdin_passed = not sys.stdin.isatty()

    if stdin_passed and not repl:
        prompt = f"{sys.stdin.read()}\n\n{prompt or ''}"
    
    if not prompt and not editor and not repl:
        raise MissingParameter(param_hint="PROMPT", param_type="string")

    if sum((shell, describe_shell, code)) > 1:
        raise BadArgumentUsage(
            "Only one of --shell, --describe-shell, and --code options can be used at a time."
        )   

    if chat and repl:
        raise BadArgumentUsage("--chat and --repl options cannot be used together.")

    if editor and stdin_passed:
        raise BadArgumentUsage("--editor option cannot be used with stdin input.")

    if editor:
        prompt = get_edited_prompt()

    role_class = (
        DefaultRoles.check_get(shell, describe_shell, code)
        if not role
        else SystemRole.get(role)
    )

    if repl:
        # Will be in infinite loop here until user exits with Ctrl+C.
        ReplHandler(repl, role_class).handle(
            prompt,
            model=model,
            temperature=temperature,
            top_probability=top_probability,
            chat_id=repl,
            caching=cache,
        )

    if chat:
        full_completion = ChatHandler(chat, role_class).handle(
            prompt,
            model=model,
            temperature=temperature,
            top_probability=top_probability,
            chat_id=chat,
            caching=cache,
        )
    else:

        if cfg.get('CHAT_LOG_ALL') == "true":
                
            # get the filenames of the most recent files in the chat_cache 
            chat_ids = os.listdir(cfg.get('CHAT_CACHE_PATH'))            
            # Filter chat_ids to include only filenames in the format '<int>'
            chat_ids = [int(chat_id) for chat_id in chat_ids if chat_id.isdigit()]
            # Get the highest value numeric chat_id and increment it
            highest_chat_id = max(chat_ids)
            new_chat = str(highest_chat_id + 1)

            if last_chat:
                chat = str(highest_chat_id)
            else:
                chat = str(highest_chat_id + 1)
                
            full_completion = ChatHandler(chat, role_class).handle(
                prompt,
                model=model,
                temperature=temperature,
                top_probability=top_probability,
                chat_id=chat,
                caching=cache,
            )
        else:
            
            full_completion = DefaultHandler(role_class).handle(
                prompt,
                model=model,
                temperature=temperature,
                top_probability=top_probability,
                caching=cache,
            )

    while shell and not stdin_passed:
        option = typer.prompt(
            text="[E]xecute, [D]escribe, [A]bort",
            type=Choice(("e", "d", "a", "y"), case_sensitive=False),
            default="e" if cfg.get("DEFAULT_EXECUTE_SHELL_CMD") == "true" else "a",
            show_choices=False,
            show_default=False,
        )
        if option in ("e", "y"):
            # "y" option is for keeping compatibility with old version.
            run_command(full_completion)
        elif option == "d":
            DefaultHandler(DefaultRoles.DESCRIBE_SHELL.get_role()).handle(
                full_completion,
                model=model,
                temperature=temperature,
                top_probability=top_probability,
                caching=cache,
            )
            continue
        break


def entry_point() -> None:
    # Python package entry point defined in setup.py
    typer.run(main)


if __name__ == "__main__":
    entry_point()

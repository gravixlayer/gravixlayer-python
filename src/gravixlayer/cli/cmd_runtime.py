"""Runtime subcommands — 100% parity with the SDK's RuntimeResource API."""

import argparse
import json
import sys
from typing import List

from .client_factory import make_client
from .formatters import print_json, print_error


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_create(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        env_vars = json.loads(args.env_vars) if args.env_vars else None
        metadata = json.loads(args.metadata) if args.metadata else None
        internet = None
        if args.internet_access is not None:
            internet = args.internet_access.lower() in ("true", "1", "yes")

        rt = client.runtime.create(
            provider=args.provider,
            region=args.runtime_region,
            template=args.template,
            timeout=args.runtime_timeout,
            env_vars=env_vars,
            metadata=metadata,
            internet_access=internet,
            agent_id=args.agent_id,
        )
        if args.json:
            print_json(rt)
        else:
            print_json(rt)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_list(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.list(limit=args.limit, offset=args.offset)
        if args.json:
            print_json({"runtimes": result.runtimes, "total": result.total})
        else:
            print_json({"runtimes": result.runtimes, "total": result.total})
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_get(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        rt = client.runtime.get(args.runtime_id)
        if args.json:
            print_json(rt)
        else:
            print_json(rt)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_kill(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.kill(args.runtime_id)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_connect(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.connect(args.runtime_id)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- Configuration ----------------------------------------------------------

def _cmd_set_timeout(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.set_timeout(args.runtime_id, args.seconds)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_metrics(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        m = client.runtime.get_metrics(args.runtime_id)
        if args.json:
            print_json(m)
        else:
            print_json(m)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_host_url(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.get_host_url(args.runtime_id, args.port)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- File operations --------------------------------------------------------

def _cmd_read_file(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.read_file(args.runtime_id, args.path)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_write_file(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        content = args.content
        if args.from_file:
            with open(args.from_file, "r") as f:
                content = f.read()
        if content is None:
            if not sys.stdin.isatty():
                content = sys.stdin.read()
            else:
                print_error("Content required via --content, --from-file, or stdin pipe.")
        result = client.runtime.write_file(args.runtime_id, args.path, content)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_list_files(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.list_files(args.runtime_id, args.path)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_delete_file(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.delete_file(args.runtime_id, args.path)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_mkdir(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.make_directory(args.runtime_id, args.path)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_upload(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        with open(args.local_path, "rb") as f:
            result = client.runtime.upload_file(args.runtime_id, file=f, path=args.remote_path)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_download(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        data = client.runtime.download_file(args.runtime_id, args.path)
        if args.output:
            with open(args.output, "wb") as f:
                f.write(data)
            print(f"Downloaded: {args.path} -> {args.output}")
        else:
            sys.stdout.buffer.write(data)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_write(args: argparse.Namespace) -> None:
    """Multipart write — single file."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        if args.from_file:
            with open(args.from_file, "rb") as f:
                data = f.read()
        elif args.content:
            data = args.content
        elif not sys.stdin.isatty():
            data = sys.stdin.buffer.read()
        else:
            print_error("Content required via --content, --from-file, or stdin pipe.")
            return

        mode = int(args.mode, 8) if args.mode else None
        result = client.runtime.write(
            args.runtime_id, args.path, data, user=args.user, mode=mode,
        )
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- Command execution ------------------------------------------------------

def _cmd_run_cmd(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        env = json.loads(args.env) if args.env else None
        result = client.runtime.run_cmd(
            args.runtime_id,
            command=args.command,
            args=args.cmd_args or None,
            working_dir=args.working_dir,
            environment=env,
            timeout=args.cmd_timeout,
        )
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except SystemExit:
        raise
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- Code execution ---------------------------------------------------------

def _cmd_run_code(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        code = args.code
        if args.file:
            with open(args.file, "r") as f:
                code = f.read()
        if code is None:
            if not sys.stdin.isatty():
                code = sys.stdin.read()
            else:
                print_error("Code required via positional arg, --file, or stdin pipe.")
                return

        env = json.loads(args.env) if args.env else None
        result = client.runtime.run_code(
            args.runtime_id,
            code=code,
            language=args.language,
            context_id=args.context_id,
            environment=env,
            timeout=args.code_timeout,
        )
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except SystemExit:
        raise
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_create_context(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.create_code_context(
            args.runtime_id, language=args.language, cwd=args.cwd,
        )
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_get_context(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.get_code_context(args.runtime_id, args.context_id)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_delete_context(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.delete_code_context(args.runtime_id, args.context_id)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- SSH --------------------------------------------------------------------

def _cmd_ssh_enable(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.enable_ssh(args.runtime_id, regenerate_keys=args.regenerate_keys)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_ssh_disable(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        client.runtime.disable_ssh(args.runtime_id)
        if args.json:
            print_json({"runtime_id": args.runtime_id, "ssh_disabled": True})
        else:
            print_json({"runtime_id": args.runtime_id, "ssh_disabled": True})
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_ssh_status(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.ssh_status(args.runtime_id)
        if args.json:
            print_json(result)
        else:
            print_json(result)
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- State management -------------------------------------------------------

def _cmd_pause(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        client.runtime.pause(args.runtime_id)
        if args.json:
            print_json({"runtime_id": args.runtime_id, "paused": True})
        else:
            print_json({"runtime_id": args.runtime_id, "paused": True})
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_resume(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        client.runtime.resume(args.runtime_id)
        if args.json:
            print_json({"runtime_id": args.runtime_id, "resumed": True})
        else:
            print_json({"runtime_id": args.runtime_id, "resumed": True})
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# -- Runtime templates (listing) --------------------------------------------

def _cmd_templates_list(args: argparse.Namespace) -> None:
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.runtime.templates.list(limit=args.limit, offset=args.offset)
        if args.json:
            print_json({"templates": result.templates, "limit": result.limit, "offset": result.offset})
        else:
            print_json({"templates": result.templates, "limit": result.limit, "offset": result.offset})
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Parser registration
# ---------------------------------------------------------------------------

def register_runtime_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register `gravixlayer runtime ...` subcommands."""
    runtime_parser = subparsers.add_parser("runtime", help="Manage cloud runtimes")
    rt_sub = runtime_parser.add_subparsers(dest="runtime_command", required=True)

    # -- create -------------------------------------------------------------
    p = rt_sub.add_parser("create", help="Create a new runtime")
    p.add_argument("--template", "-t", default="python-base-v1", help="Template name or ID (default: python-base-v1)")
    p.add_argument("--provider", help="Cloud provider (overrides client default)")
    p.add_argument("--runtime-region", help="Cloud region (overrides client default)")
    p.add_argument("--runtime-timeout", type=int, help="Timeout in seconds")
    p.add_argument("--env-vars", help="Environment variables as JSON object")
    p.add_argument("--metadata", help="Metadata tags as JSON object")
    p.add_argument("--internet-access", help="Allow internet access (true/false)")
    p.add_argument("--agent-id", help="Agent ID to associate")
    p.set_defaults(func=_cmd_create)

    # -- list ---------------------------------------------------------------
    p = rt_sub.add_parser("list", help="List all runtimes")
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p.set_defaults(func=_cmd_list)

    # -- get ----------------------------------------------------------------
    p = rt_sub.add_parser("get", help="Get runtime details")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_get)

    # -- kill ---------------------------------------------------------------
    p = rt_sub.add_parser("kill", help="Terminate a runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_kill)

    # -- connect ------------------------------------------------------------
    p = rt_sub.add_parser("connect", help="Connect to an existing runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_connect)

    # -- set-timeout --------------------------------------------------------
    p = rt_sub.add_parser("set-timeout", help="Update runtime timeout")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("seconds", type=int, help="Timeout in seconds")
    p.set_defaults(func=_cmd_set_timeout)

    # -- metrics ------------------------------------------------------------
    p = rt_sub.add_parser("metrics", help="Get runtime resource metrics")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_metrics)

    # -- host-url -----------------------------------------------------------
    p = rt_sub.add_parser("host-url", help="Get public URL for a port")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("port", type=int, help="Port number")
    p.set_defaults(func=_cmd_host_url)

    # -- File operations ----------------------------------------------------
    p = rt_sub.add_parser("read-file", help="Read a file from the runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="File path inside the runtime")
    p.set_defaults(func=_cmd_read_file)

    p = rt_sub.add_parser("write-file", help="Write content to a file")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="File path inside the runtime")
    p.add_argument("--content", "-c", help="File content (string)")
    p.add_argument("--from-file", "-f", help="Read content from a local file")
    p.set_defaults(func=_cmd_write_file)

    p = rt_sub.add_parser("list-files", help="List files in a directory")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", nargs="?", default="/home/user", help="Directory path (default: /home/user)")
    p.set_defaults(func=_cmd_list_files)

    p = rt_sub.add_parser("delete-file", help="Delete a file or directory")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="Path to delete")
    p.set_defaults(func=_cmd_delete_file)

    p = rt_sub.add_parser("mkdir", help="Create a directory")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="Directory path to create")
    p.set_defaults(func=_cmd_mkdir)

    p = rt_sub.add_parser("upload", help="Upload a local file to the runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("local_path", help="Local file path")
    p.add_argument("--remote-path", help="Destination path in the runtime")
    p.set_defaults(func=_cmd_upload)

    p = rt_sub.add_parser("download", help="Download a file from the runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="Remote file path")
    p.add_argument("--output", "-o", help="Local output file (default: stdout)")
    p.set_defaults(func=_cmd_download)

    p = rt_sub.add_parser("write", help="Write file via multipart upload (binary-safe)")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("path", help="Destination path")
    p.add_argument("--content", "-c", help="File content (string)")
    p.add_argument("--from-file", "-f", help="Read content from a local file")
    p.add_argument("--user", help="File owner username")
    p.add_argument("--mode", help="File permissions in octal (e.g. 0755)")
    p.set_defaults(func=_cmd_write)

    # -- Command execution --------------------------------------------------
    p = rt_sub.add_parser("run-cmd", help="Execute a shell command")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("command", help="Command to execute")
    p.add_argument("cmd_args", nargs=argparse.REMAINDER, help="Additional command arguments")
    p.add_argument("--working-dir", "-w", help="Working directory")
    p.add_argument("--env", help="Environment variables as JSON object")
    p.add_argument("--cmd-timeout", type=int, help="Timeout in seconds")
    p.set_defaults(func=_cmd_run_cmd)

    # -- Code execution -----------------------------------------------------
    p = rt_sub.add_parser("run-code", help="Execute code via Jupyter kernel")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("code", nargs="?", help="Code to execute (or use --file / stdin)")
    p.add_argument("--file", help="Read code from a local file")
    p.add_argument("--language", "-l", default="python", help="Language (default: python)")
    p.add_argument("--context-id", help="Execution context ID for state persistence")
    p.add_argument("--env", help="Environment variables as JSON object")
    p.add_argument("--code-timeout", type=int, help="Timeout in seconds")
    p.set_defaults(func=_cmd_run_code)

    # -- Code contexts ------------------------------------------------------
    p = rt_sub.add_parser("create-context", help="Create a code execution context")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("--language", "-l", default="python", help="Language (default: python)")
    p.add_argument("--cwd", help="Working directory for the context")
    p.set_defaults(func=_cmd_create_context)

    p = rt_sub.add_parser("get-context", help="Get code execution context info")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("context_id", help="Context ID")
    p.set_defaults(func=_cmd_get_context)

    p = rt_sub.add_parser("delete-context", help="Delete a code execution context")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("context_id", help="Context ID")
    p.set_defaults(func=_cmd_delete_context)

    # -- SSH ----------------------------------------------------------------
    p = rt_sub.add_parser("ssh-enable", help="Enable SSH access")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.add_argument("--regenerate-keys", action="store_true", help="Regenerate SSH keys")
    p.set_defaults(func=_cmd_ssh_enable)

    p = rt_sub.add_parser("ssh-disable", help="Disable SSH access")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_ssh_disable)

    p = rt_sub.add_parser("ssh-status", help="Get SSH status")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_ssh_status)

    # -- State management ---------------------------------------------------
    p = rt_sub.add_parser("pause", help="Pause a running runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_pause)

    p = rt_sub.add_parser("resume", help="Resume a paused runtime")
    p.add_argument("runtime_id", help="Runtime UUID")
    p.set_defaults(func=_cmd_resume)

    # -- Runtime templates --------------------------------------------------
    p = rt_sub.add_parser("templates", help="List available runtime templates")
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p.set_defaults(func=_cmd_templates_list)

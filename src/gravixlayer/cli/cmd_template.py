"""Template subcommands — 100% parity with the SDK's Templates API."""

import argparse
import json
import sys
import time
from typing import Optional

from .client_factory import make_client
from .formatters import print_json, print_table, print_error, print_kv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_template_builder(args: argparse.Namespace):
    """Construct a TemplateBuilder from CLI flags."""
    from ..types.templates import TemplateBuilder

    builder = TemplateBuilder(name=args.name, description=args.description or "")

    if args.template_id:
        builder.template_id(args.template_id)
    if args.from_image:
        builder.from_image(args.from_image)
    if args.dockerfile:
        with open(args.dockerfile, "r") as f:
            builder.dockerfile(f.read())

    if args.vcpu:
        builder.vcpu(args.vcpu)
    if args.memory:
        builder.memory(args.memory)
    if args.disk:
        builder.disk(args.disk)
    if args.start_cmd:
        builder.start_cmd(args.start_cmd)
    if args.ready_cmd:
        builder.ready_cmd(args.ready_cmd, timeout_secs=args.ready_timeout or 60)

    if args.env:
        for pair in args.env:
            key, _, value = pair.partition("=")
            if not key:
                print_error(f"Invalid --env format: {pair!r}. Use KEY=VALUE.")
            builder.env(key, value)
    if args.tags:
        for pair in args.tags:
            key, _, value = pair.partition("=")
            if not key:
                print_error(f"Invalid --tag format: {pair!r}. Use KEY=VALUE.")
            builder.tags({key: value})

    if args.run:
        for cmd in args.run:
            builder.run(cmd)
    if args.pip_install:
        builder.pip_install(*args.pip_install)
    if args.npm_install:
        builder.npm_install(*args.npm_install)
    if args.apt_install:
        builder.apt_install(*args.apt_install)
    if args.bun_install:
        builder.bun_install(*args.bun_install)
    if args.git_clone:
        builder.git_clone(args.git_clone)
    if args.copy_file:
        for pair in args.copy_file:
            parts = pair.split(":", 1)
            if len(parts) != 2:
                print_error(f"Invalid --copy-file format: {pair!r}. Use LOCAL:REMOTE.")
            builder.copy_file(parts[0], parts[1])
    if args.copy_dir:
        for pair in args.copy_dir:
            parts = pair.split(":", 1)
            if len(parts) != 2:
                print_error(f"Invalid --copy-dir format: {pair!r}. Use LOCAL:REMOTE.")
            builder.copy_dir(parts[0], parts[1])
    if args.mkdirs:
        for d in args.mkdirs:
            builder.mkdir(d)

    return builder


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_build(args: argparse.Namespace) -> None:
    """Start an asynchronous template build."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        builder = _build_template_builder(args)
        result = client.templates.build(builder)
        if args.json:
            print_json(result)
        else:
            print_kv({
                "build_id": result.build_id,
                "template_id": result.template_id,
                "status": result.status,
                "message": result.message,
            })
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_build_wait(args: argparse.Namespace) -> None:
    """Start a build and wait for completion."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        builder = _build_template_builder(args)

        def _on_status(entry):
            if not args.json:
                sys.stderr.write(f"[build] {entry.message}\n")

        result = client.templates.build_and_wait(
            builder,
            poll_interval_secs=args.poll_interval,
            timeout_secs=args.build_timeout,
            on_status=_on_status,
        )
        if args.json:
            print_json(result)
        else:
            print_kv({
                "build_id": result.build_id,
                "template_id": result.template_id,
                "status": result.status,
                "phase": result.phase,
                "progress": f"{result.progress_percent}%",
                "started_at": result.started_at,
                "completed_at": result.completed_at,
            })
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_build_status(args: argparse.Namespace) -> None:
    """Get build status."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.templates.get_build_status(args.build_id)
        if args.json:
            print_json(result)
        else:
            print_kv({
                "build_id": result.build_id,
                "template_id": result.template_id,
                "status": result.status,
                "phase": result.phase,
                "progress": f"{result.progress_percent}%",
                "error": result.error,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
            })
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_list(args: argparse.Namespace) -> None:
    """List templates."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.templates.list(
            limit=args.limit, offset=args.offset, project_id=args.project_id,
        )
        if args.json:
            print_json({"templates": result.templates, "limit": result.limit, "offset": result.offset})
        else:
            rows = []
            for t in result.templates:
                rows.append({
                    "id": t.id,
                    "name": t.name,
                    "vcpu": str(t.vcpu_count),
                    "memory_mb": str(t.memory_mb),
                    "disk_mb": str(t.disk_size_mb),
                    "visibility": t.visibility,
                    "created_at": t.created_at,
                })
            print_table(rows, ["id", "name", "vcpu", "memory_mb", "disk_mb", "visibility", "created_at"])
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_get(args: argparse.Namespace) -> None:
    """Get template details."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.templates.get(args.template_id)
        if args.json:
            print_json(result)
        else:
            print_kv({
                "id": result.id,
                "name": result.name,
                "description": result.description,
                "vcpu_count": result.vcpu_count,
                "memory_mb": result.memory_mb,
                "disk_size_mb": result.disk_size_mb,
                "visibility": result.visibility,
                "provider": result.provider,
                "region": result.region,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            })
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_snapshot(args: argparse.Namespace) -> None:
    """Get template snapshot info."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.templates.get_snapshot(args.template_id)
        if args.json:
            print_json(result)
        else:
            print_kv({
                "template_id": result.template_id,
                "name": result.name,
                "description": result.description,
                "has_snapshot": result.has_snapshot,
                "vcpu_count": result.vcpu_count,
                "memory_mb": result.memory_mb,
                "created_at": result.created_at,
                "envd_version": result.envd_version,
                "snapshot_size_bytes": result.snapshot_size_bytes,
            })
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


def _cmd_delete(args: argparse.Namespace) -> None:
    """Delete a template."""
    client = make_client(args.api_key, args.base_url, args.cloud, args.region, args.timeout)
    try:
        result = client.templates.delete(args.template_id)
        if args.json:
            print_json(result)
        else:
            print(f"Template {args.template_id} deleted.")
    except Exception as exc:
        print_error(str(exc))
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Shared builder flags (used by build and build-wait)
# ---------------------------------------------------------------------------

def _add_builder_args(parser: argparse.ArgumentParser) -> None:
    """Add TemplateBuilder flags to a subcommand parser."""
    parser.add_argument("name", help="Template name")
    parser.add_argument("--description", default="", help="Template description")
    parser.add_argument("--template-id", help="Custom template ID (auto-generated by default)")
    parser.add_argument("--from-image", help="Base Docker image (e.g. python:3.11-slim)")
    parser.add_argument("--dockerfile", help="Path to a Dockerfile to use as the base image")
    parser.add_argument("--vcpu", type=int, help="Number of vCPUs (default: 2)")
    parser.add_argument("--memory", type=int, help="Memory in MB (default: 512)")
    parser.add_argument("--disk", type=int, help="Disk size in MB (default: 4096)")
    parser.add_argument("--start-cmd", help="Command to run after VM starts")
    parser.add_argument("--ready-cmd", help="Readiness check command (must exit 0)")
    parser.add_argument("--ready-timeout", type=int, help="Ready command timeout in seconds (default: 60)")
    parser.add_argument("--env", action="append", metavar="KEY=VALUE", help="Environment variable (repeatable)")
    parser.add_argument("--tag", dest="tags", action="append", metavar="KEY=VALUE", help="Metadata tag (repeatable)")
    parser.add_argument("--run", action="append", metavar="CMD", help="Shell command build step (repeatable)")
    parser.add_argument("--pip-install", nargs="+", metavar="PKG", help="Python packages to install")
    parser.add_argument("--npm-install", nargs="+", metavar="PKG", help="Node.js packages to install")
    parser.add_argument("--apt-install", nargs="+", metavar="PKG", help="System packages to install")
    parser.add_argument("--bun-install", nargs="+", metavar="PKG", help="Bun packages to install")
    parser.add_argument("--git-clone", metavar="URL", help="Git repository to clone")
    parser.add_argument("--copy-file", action="append", metavar="LOCAL:REMOTE", help="Copy local file into VM (repeatable)")
    parser.add_argument("--copy-dir", action="append", metavar="LOCAL:REMOTE", help="Copy local directory into VM (repeatable)")
    parser.add_argument("--mkdir", dest="mkdirs", action="append", metavar="PATH", help="Create directory in VM (repeatable)")


# ---------------------------------------------------------------------------
# Parser registration
# ---------------------------------------------------------------------------

def register_template_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register `gravixlayer template ...` subcommands."""
    tmpl_parser = subparsers.add_parser("template", help="Manage templates and builds")
    tmpl_sub = tmpl_parser.add_subparsers(dest="template_command", required=True)

    # -- build (async) ------------------------------------------------------
    p = tmpl_sub.add_parser("build", help="Start an asynchronous template build")
    _add_builder_args(p)
    p.set_defaults(func=_cmd_build)

    # -- build-wait ---------------------------------------------------------
    p = tmpl_sub.add_parser("build-wait", help="Build a template and wait for completion")
    _add_builder_args(p)
    p.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between status polls (default: 5)")
    p.add_argument("--build-timeout", type=int, default=600, help="Max seconds to wait (default: 600)")
    p.set_defaults(func=_cmd_build_wait)

    # -- build-status -------------------------------------------------------
    p = tmpl_sub.add_parser("build-status", help="Get build status")
    p.add_argument("build_id", help="Build ID")
    p.set_defaults(func=_cmd_build_status)

    # -- list ---------------------------------------------------------------
    p = tmpl_sub.add_parser("list", help="List templates")
    p.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    p.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p.add_argument("--project-id", help="Filter by project ID")
    p.set_defaults(func=_cmd_list)

    # -- get ----------------------------------------------------------------
    p = tmpl_sub.add_parser("get", help="Get template details")
    p.add_argument("template_id", help="Template UUID")
    p.set_defaults(func=_cmd_get)

    # -- snapshot -----------------------------------------------------------
    p = tmpl_sub.add_parser("snapshot", help="Get template snapshot info")
    p.add_argument("template_id", help="Template UUID")
    p.set_defaults(func=_cmd_snapshot)

    # -- delete -------------------------------------------------------------
    p = tmpl_sub.add_parser("delete", help="Delete a template")
    p.add_argument("template_id", help="Template UUID")
    p.set_defaults(func=_cmd_delete)

"""Administración local de tenants y claves."""

import argparse
import asyncio
import sys
import uuid

from ragmur.auth.service import create_tenant, issue_key, revoke_key
from ragmur.core.config import get_settings
from ragmur.db.session import create_engine, create_session_factory


async def run(args: argparse.Namespace) -> str:
    """Ejecuta un comando y devuelve su resultado."""
    settings = get_settings()
    if args.command == "reindex":
        from ragmur.ingestion.maintenance import reindex

        indexed, failed = await reindex(settings, document_id=args.document, tenant_id=args.tenant)
        if failed:
            raise ValueError(f"Reindexed {indexed} documents; {failed} failed")
        return f"Reindexed {indexed} documents"
    if args.command == "delete-tenant":
        from ragmur.ingestion.maintenance import delete_tenant

        count = await delete_tenant(settings, args.tenant_id)
        return f"Deleted tenant with {count} documents"
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as session:
            if args.command == "create-tenant":
                tenant = await create_tenant(session, args.name)
                return str(tenant.id)
            if args.command == "issue-key":
                return await issue_key(
                    session,
                    args.tenant_id,
                    args.name,
                    settings.api_key_hmac_secret.get_secret_value(),
                )
            if not await revoke_key(session, args.key_id):
                raise ValueError("Active key not found")
            return "Key revoked"
    finally:
        await engine.dispose()


def main() -> None:
    """Procesa los argumentos de administración."""
    parser = argparse.ArgumentParser(prog="ragmur")
    commands = parser.add_subparsers(dest="command", required=True)
    tenant = commands.add_parser("create-tenant")
    tenant.add_argument("name")
    issue = commands.add_parser("issue-key")
    issue.add_argument("tenant_id", type=uuid.UUID)
    issue.add_argument("--name")
    revoke = commands.add_parser("revoke-key")
    revoke.add_argument("key_id")
    reindex_command = commands.add_parser("reindex")
    scope = reindex_command.add_mutually_exclusive_group(required=True)
    scope.add_argument("--document", type=uuid.UUID)
    scope.add_argument("--tenant", type=uuid.UUID)
    scope.add_argument("--all", action="store_true")
    delete_command = commands.add_parser("delete-tenant")
    delete_command.add_argument("tenant_id", type=uuid.UUID)
    try:
        result = asyncio.run(run(parser.parse_args()))
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    except Exception:
        parser.exit(1, "Command failed; check the configuration and service dependencies\n")
    sys.stdout.write(result + "\n")


if __name__ == "__main__":
    main()

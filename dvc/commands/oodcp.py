"""CLI commands for OOD-CP dataset and version management.

Provides ``dvc oodcp`` command group with subcommands for CRUD
operations on DataSets, DataFiles, and DataVersions.
"""

from typing import TYPE_CHECKING

from dvc.cli.command import CmdBase
from dvc.log import logger

if TYPE_CHECKING:
    pass

logger = logger.getChild(__name__)


class CmdOodcpDatasetList(CmdBase):
    """List all OOD-CP datasets."""

    def run(self):
        from dvc.ui import ui

        datasets = self.repo.oodcp.datarepo.list_datasets()
        if not datasets:
            ui.write("No datasets found.")
            return 0

        for ds in datasets:
            files = self.repo.oodcp.datarepo.list_datafiles(ds.uuid)
            ui.write(
                f"  {ds.name}  "
                f"({len(files)} file{'s' if len(files) != 1 else ''})  "
                f"[{ds.status.value}]"
            )
        return 0


class CmdOodcpDatasetCreate(CmdBase):
    """Create a new OOD-CP dataset."""

    def run(self):
        from dvc.ui import ui

        ds = self.repo.oodcp.dataset_factory.create(
            name=self.args.name,
            description=self.args.description or "",
            project=self.args.project or "",
            owner=self.args.owner or "",
        )
        self.repo.oodcp.datarepo.add_dataset(ds)
        ui.write(f"Created dataset '{ds.name}' ({ds.uuid})")
        return 0


class CmdOodcpDatasetShow(CmdBase):
    """Show details for an OOD-CP dataset."""

    def run(self):
        from dvc.ui import ui

        ds = self.repo.oodcp.datarepo.get_dataset_by_name(self.args.name)
        if ds is None:
            ui.error_write(f"Dataset '{self.args.name}' not found.")
            return 1

        ui.write(f"Name:        {ds.name}")
        ui.write(f"UUID:        {ds.uuid}")
        ui.write(f"Description: {ds.description}")
        ui.write(f"Project:     {ds.project}")
        ui.write(f"Owner:       {ds.owner}")
        ui.write(f"Status:      {ds.status.value}")

        files = self.repo.oodcp.datarepo.list_datafiles(ds.uuid)
        ui.write(f"Files:       {len(files)}")
        for f in files:
            latest = self.repo.oodcp.datarepo.get_latest_dataversion(
                f.uuid
            )
            ver_str = f"v{latest.version_number}" if latest else "no versions"
            ui.write(f"  - {f.name} ({ver_str})")
        return 0


class CmdOodcpFileList(CmdBase):
    """List files in an OOD-CP dataset."""

    def run(self):
        from dvc.ui import ui

        ds = self.repo.oodcp.datarepo.get_dataset_by_name(
            self.args.dataset
        )
        if ds is None:
            ui.error_write(
                f"Dataset '{self.args.dataset}' not found."
            )
            return 1

        files = self.repo.oodcp.datarepo.list_datafiles(ds.uuid)
        if not files:
            ui.write(f"No files in dataset '{self.args.dataset}'.")
            return 0

        for f in files:
            versions = self.repo.oodcp.datarepo.list_dataversions(f.uuid)
            ui.write(
                f"  {f.name}  "
                f"({len(versions)} version{'s' if len(versions) != 1 else ''})  "
                f"[{f.status.value}]"
            )
        return 0


class CmdOodcpFileAdd(CmdBase):
    """Add a file to an OOD-CP dataset."""

    def run(self):
        from dvc.ui import ui

        ds = self.repo.oodcp.datarepo.get_dataset_by_name(
            self.args.dataset
        )
        if ds is None:
            ui.error_write(
                f"Dataset '{self.args.dataset}' not found."
            )
            return 1

        df = self.repo.oodcp.datafile_factory.create(
            dataset_uuid=ds.uuid,
            name=self.args.name,
            description=self.args.description or "",
            owner=self.args.owner or "",
        )
        self.repo.oodcp.datarepo.add_datafile(df)
        ui.write(
            f"Added file '{df.name}' to dataset '{ds.name}' ({df.uuid})"
        )
        return 0


class CmdOodcpVersionList(CmdBase):
    """List versions of an OOD-CP file."""

    def run(self):
        from dvc.ui import ui

        ds = self.repo.oodcp.datarepo.get_dataset_by_name(
            self.args.dataset
        )
        if ds is None:
            ui.error_write(
                f"Dataset '{self.args.dataset}' not found."
            )
            return 1

        df = self.repo.oodcp.datarepo.get_datafile_by_name(
            ds.uuid, self.args.file
        )
        if df is None:
            ui.error_write(
                f"File '{self.args.file}' not found "
                f"in dataset '{self.args.dataset}'."
            )
            return 1

        versions = self.repo.oodcp.datarepo.list_dataversions(df.uuid)
        if not versions:
            ui.write(f"No versions for '{self.args.file}'.")
            return 0

        for v in versions:
            hash_short = v.dvc_hash[:8] if v.dvc_hash else "none"
            ui.write(
                f"  v{v.version_number}  "
                f"hash:{hash_short}  "
                f"[{v.status.value}]  "
                f"{v.storage_type.value}"
            )
        return 0


def add_parser(subparsers, parent_parser):
    """Register ``dvc oodcp`` command group with subcommands."""
    OODCP_HELP = "Manage OOD-CP datasets, files, and versions."

    oodcp_parser = subparsers.add_parser(
        "oodcp",
        parents=[parent_parser],
        help=OODCP_HELP,
        formatter_class=parent_parser.formatter_class,
    )

    oodcp_subparsers = oodcp_parser.add_subparsers(
        dest="cmd",
        help="Use `dvc oodcp CMD --help` for command-specific help.",
    )

    # -- dataset list --
    ds_list_parser = oodcp_subparsers.add_parser(
        "list",
        parents=[parent_parser],
        help="List all datasets.",
    )
    ds_list_parser.set_defaults(func=CmdOodcpDatasetList)

    # -- dataset create --
    ds_create_parser = oodcp_subparsers.add_parser(
        "create",
        parents=[parent_parser],
        help="Create a new dataset.",
    )
    ds_create_parser.add_argument("name", help="Dataset name.")
    ds_create_parser.add_argument(
        "-d", "--description", help="Dataset description."
    )
    ds_create_parser.add_argument(
        "-p", "--project", help="Project name."
    )
    ds_create_parser.add_argument(
        "-o", "--owner", help="Owner name."
    )
    ds_create_parser.set_defaults(func=CmdOodcpDatasetCreate)

    # -- dataset show --
    ds_show_parser = oodcp_subparsers.add_parser(
        "show",
        parents=[parent_parser],
        help="Show dataset details.",
    )
    ds_show_parser.add_argument("name", help="Dataset name.")
    ds_show_parser.set_defaults(func=CmdOodcpDatasetShow)

    # -- file list --
    file_list_parser = oodcp_subparsers.add_parser(
        "files",
        parents=[parent_parser],
        help="List files in a dataset.",
    )
    file_list_parser.add_argument("dataset", help="Dataset name.")
    file_list_parser.set_defaults(func=CmdOodcpFileList)

    # -- file add --
    file_add_parser = oodcp_subparsers.add_parser(
        "add-file",
        parents=[parent_parser],
        help="Add a file to a dataset.",
    )
    file_add_parser.add_argument("dataset", help="Dataset name.")
    file_add_parser.add_argument("name", help="File name.")
    file_add_parser.add_argument(
        "-d", "--description", help="File description."
    )
    file_add_parser.add_argument(
        "-o", "--owner", help="Owner name."
    )
    file_add_parser.set_defaults(func=CmdOodcpFileAdd)

    # -- version list --
    ver_list_parser = oodcp_subparsers.add_parser(
        "versions",
        parents=[parent_parser],
        help="List versions of a file.",
    )
    ver_list_parser.add_argument("dataset", help="Dataset name.")
    ver_list_parser.add_argument("file", help="File name.")
    ver_list_parser.set_defaults(func=CmdOodcpVersionList)

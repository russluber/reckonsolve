"""Small Windows file primitives for the journal location protocol.

Sharing modes fence legacy SQLite connections too; the lease alone cannot do
that. A persistent read-only attribute precedes retirement, covering process
interruption even when committed WAL pages still exist beside the old file.
"""

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from uuid import uuid4

# Named Win32 flags keep the storage protocol readable without hiding SDK calls.
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_WRITE_ATTRIBUTES = 0x100
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
OPEN_ALWAYS = 4
FILE_FLAG_WRITE_THROUGH = 0x80000000
LOCKFILE_FAIL_IMMEDIATELY = 1
LOCKFILE_EXCLUSIVE_LOCK = 2


class LocationError(RuntimeError):
    """Location/coordination failure; never permission to create another journal."""


class LocationBusyError(LocationError):
    """Another runtime or native writable file handle prevents movement."""


def _kernel():
    if os.name != "nt":
        raise LocationError(
            "Journal relocation requires Windows and a local NTFS folder."
        )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
    kernel.FlushFileBuffers.restype = wintypes.BOOL
    kernel.WriteFile.argtypes = (
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    )
    kernel.WriteFile.restype = wintypes.BOOL
    kernel.SetEndOfFile.argtypes = (wintypes.HANDLE,)
    kernel.SetEndOfFile.restype = wintypes.BOOL
    kernel.SetFileAttributesW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    kernel.SetFileAttributesW.restype = wintypes.BOOL
    kernel.MoveFileExW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
    kernel.MoveFileExW.restype = wintypes.BOOL
    return kernel


def _checked(result) -> None:
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


class RuntimeLease:
    """Nonblocking shared ordinary access, exclusive relocation/recovery access."""

    def __init__(self, root: Path, *, exclusive: bool = False) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.kernel = _kernel()
        self.handle = self.kernel.CreateFileW(
            str(root / "journal-access.lock"),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_ALWAYS,
            0,
            None,
        )
        if self.handle == wintypes.HANDLE(-1).value:
            raise LocationError("The journal access lease could not be opened.")
        lock = self.kernel.LockFileEx
        lock.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_Overlapped),
        )
        lock.restype = wintypes.BOOL
        self.overlapped = _Overlapped()
        if not lock(
            self.handle,
            LOCKFILE_FAIL_IMMEDIATELY | (LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0),
            0,
            1,
            0,
            ctypes.byref(self.overlapped),
        ):
            self.close()
            raise LocationBusyError(
                "Close other Reckonsolve windows and CLI commands, then try again."
            )

    def close(self) -> None:
        if self.handle is not None:
            _checked(self.kernel.CloseHandle(self.handle))
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class FileFence:
    """Deny new writers and refuse existing writers without force-closing them."""

    def __init__(self, path: Path, *, attributes_only: bool = False) -> None:
        self.path = path
        self.kernel = _kernel()
        access = GENERIC_READ | (
            FILE_WRITE_ATTRIBUTES if attributes_only else GENERIC_WRITE
        )
        self.handle = self.kernel.CreateFileW(
            str(path),
            access,
            FILE_SHARE_READ,
            None,
            OPEN_EXISTING,
            FILE_FLAG_WRITE_THROUGH,
            None,
        )  # write-through
        if self.handle == wintypes.HANDLE(-1).value:
            error = ctypes.get_last_error()
            self.handle = None
            if error in (32, 33):
                raise LocationBusyError(
                    "The journal is open in another program. Close it and try again."
                )
            raise LocationError(
                f"The journal file could not be accessed: {path}. {ctypes.WinError(error)}"
            )
        try:
            self.identity = file_identity(path)
        except BaseException:
            self.close()
            raise

    def protect(self) -> None:
        attributes = self.path.stat().st_file_attributes
        _checked(
            self.kernel.SetFileAttributesW(str(self.path), (attributes & ~0x80) | 1)
        )
        _checked(self.kernel.FlushFileBuffers(self.handle))

        if not self.path.stat().st_file_attributes & 1:
            raise LocationError(
                "The original journal's persistent write protection could not be verified."
            )

    def write_notice(self, data: bytes) -> None:
        # This existing handle remains writable after setting READONLY. Do not
        # close/reopen it or remove the pathname, even momentarily.
        written = wintypes.DWORD()
        _checked(
            self.kernel.WriteFile(
                self.handle, data, len(data), ctypes.byref(written), None
            )
        )
        if written.value != len(data):
            raise LocationError(
                "The old-location notice was only partially written. Recovery is required."
            )
        _checked(self.kernel.FlushFileBuffers(self.handle))
        # Keep the same pathname/file identity, but release the old body after
        # the notice is durable and two complete SQLite copies were verified.
        _checked(self.kernel.SetEndOfFile(self.handle))
        _checked(self.kernel.FlushFileBuffers(self.handle))

    def close(self) -> None:
        if self.handle is not None:
            _checked(self.kernel.CloseHandle(self.handle))
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def file_identity(path: Path) -> tuple[int, int]:
    status = path.stat()
    if status.st_nlink != 1:
        raise LocationError(
            "A hard-linked journal cannot be moved. Choose an ordinary local folder."
        )
    return status.st_dev, status.st_ino


def validate_journal_file(path: Path) -> None:
    if path.lstat().st_file_attributes & 0x400:
        raise LocationError("A linked journal cannot be selected as the active file.")
    file_identity(path)


def validate_local_folder(path: Path) -> Path:
    kernel = _kernel()
    original = path.absolute()
    if original.drive.startswith("\\\\"):
        raise LocationError(
            "Network and extended device paths are not supported. Choose a local folder."
        )
    for part in (original, *original.parents):
        if part.exists() and part.lstat().st_file_attributes & (
            0x400 | 0x1000 | 0x40000 | 0x400000
        ):
            raise LocationError(
                "Choose a local folder without links, cloud storage or offline files."
            )
    folder = original.resolve(strict=True)
    if not folder.is_dir() or folder == Path(folder.anchor):
        raise LocationError("Choose a folder on a local fixed drive.")
    for key, value in os.environ.items():
        if (
            key.casefold().startswith("onedrive")
            and value
            and folder.is_relative_to(Path(value).resolve())
        ):
            raise LocationError(
                "Choose a folder outside OneDrive or another synchronization service."
            )
    volume = ctypes.create_unicode_buffer(1024)
    kernel.GetVolumePathNameW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    )
    kernel.GetVolumePathNameW.restype = wintypes.BOOL
    _checked(kernel.GetVolumePathNameW(str(folder), volume, len(volume)))
    kernel.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel.GetDriveTypeW.restype = wintypes.UINT
    filesystem = ctypes.create_unicode_buffer(32)
    kernel.GetVolumeInformationW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    )
    kernel.GetVolumeInformationW.restype = wintypes.BOOL
    _checked(
        kernel.GetVolumeInformationW(
            volume, None, 0, None, None, None, filesystem, len(filesystem)
        )
    )
    if kernel.GetDriveTypeW(volume) != 3 or filesystem.value.upper() != "NTFS":
        raise LocationError(
            "Choose an unsynchronized folder on a local fixed NTFS drive."
        )
    return folder


def atomic_json(path: Path, value: dict, *, replace: bool = True) -> None:
    """Flush content, then install same-volume metadata without a missing path."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(value, sort_keys=True) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        _checked(
            _kernel().MoveFileExW(str(temporary), str(path), (1 if replace else 0) | 8)
        )
    finally:
        temporary.unlink(missing_ok=True)

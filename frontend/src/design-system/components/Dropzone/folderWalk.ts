/**
 * Recursive folder walk for drag-and-drop (Product Experience phase, Phase 3
 * — "the UI should naturally encourage folder upload"). Standard, widely
 * supported (Chromium/WebKit/Firefox) `DataTransferItem.webkitGetAsEntry()`
 * API — no new dependency. `readEntries()` is paginated by spec (a single
 * call is not guaranteed to return every entry in a large directory), so
 * each directory reader is drained in a loop until it returns empty.
 *
 * Falls back to the flat `DataTransfer.files` list (no recursion) if the
 * browser doesn't support `webkitGetAsEntry` at all.
 */

interface FileSystemEntryLike {
  readonly isFile: boolean;
  readonly isDirectory: boolean;
  file: (success: (file: File) => void, error: (err: unknown) => void) => void;
  createReader: () => {
    readEntries: (
      success: (entries: FileSystemEntryLike[]) => void,
      error: (err: unknown) => void,
    ) => void;
  };
}

function readEntryAsFile(entry: FileSystemEntryLike): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file(resolve, reject);
  });
}

async function readAllDirectoryEntries(
  reader: ReturnType<FileSystemEntryLike['createReader']>,
): Promise<FileSystemEntryLike[]> {
  const all: FileSystemEntryLike[] = [];
  // readEntries() may return a partial batch even when more entries remain —
  // keep calling until it returns an empty array, per the File and Directory
  // Entries API spec.
  for (;;) {
    const batch = await new Promise<FileSystemEntryLike[]>((resolve, reject) => {
      reader.readEntries(resolve, reject);
    });
    if (batch.length === 0) break;
    all.push(...batch);
  }
  return all;
}

async function walkEntry(entry: FileSystemEntryLike): Promise<File[]> {
  if (entry.isFile) {
    const file = await readEntryAsFile(entry);
    return [file];
  }
  if (entry.isDirectory) {
    const entries = await readAllDirectoryEntries(entry.createReader());
    const nested = await Promise.all(entries.map((child) => walkEntry(child)));
    return nested.flat();
  }
  return [];
}

/** Recursively resolves every file dropped, including files nested in dropped folders. */
export async function readAllFilesFromDataTransfer(dataTransfer: DataTransfer): Promise<File[]> {
  const items = Array.from(dataTransfer.items);
  const supportsEntries = items.length > 0 && typeof items[0].webkitGetAsEntry === 'function';

  if (!supportsEntries) {
    return Array.from(dataTransfer.files);
  }

  const entries = items
    .map((item) => item.webkitGetAsEntry() as FileSystemEntryLike | null)
    .filter((entry): entry is FileSystemEntryLike => entry !== null);

  const results = await Promise.all(entries.map((entry) => walkEntry(entry)));
  return results.flat();
}

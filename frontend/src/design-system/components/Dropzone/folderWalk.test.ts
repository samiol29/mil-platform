import { describe, expect, it } from 'vitest';

import { readAllFilesFromDataTransfer } from './folderWalk';

interface MockEntry {
  isFile: boolean;
  isDirectory: boolean;
  file?: (success: (file: File) => void) => void;
  createReader?: () => { readEntries: (success: (entries: MockEntry[]) => void) => void };
}

function fileEntry(name: string): MockEntry {
  return {
    isFile: true,
    isDirectory: false,
    file: (success) => {
      success(new File(['content'], name));
    },
  };
}

function directoryEntry(children: MockEntry[]): MockEntry {
  // Simulates the spec's pagination quirk: `readEntries()` returns entries in
  // two batches, then an empty array to signal completion.
  let call = 0;
  return {
    isFile: false,
    isDirectory: true,
    createReader: () => ({
      readEntries: (success) => {
        call += 1;
        if (call === 1) success(children.slice(0, Math.ceil(children.length / 2)));
        else if (call === 2) success(children.slice(Math.ceil(children.length / 2)));
        else success([]);
      },
    }),
  };
}

function makeDataTransfer(entries: MockEntry[]): DataTransfer {
  return {
    items: entries.map((entry) => ({
      webkitGetAsEntry: () => entry,
    })),
    files: [],
  } as unknown as DataTransfer;
}

describe('readAllFilesFromDataTransfer', () => {
  it('resolves flat dropped files', async () => {
    const dataTransfer = makeDataTransfer([fileEntry('a.pdf'), fileEntry('b.pdf')]);
    const files = await readAllFilesFromDataTransfer(dataTransfer);
    expect(files.map((f) => f.name).sort()).toEqual(['a.pdf', 'b.pdf']);
  });

  it('recursively walks a dropped folder, including nested subfolders, draining paginated readEntries()', async () => {
    const nested = directoryEntry([fileEntry('nested-1.pdf'), fileEntry('nested-2.pdf')]);
    const topLevel = directoryEntry([fileEntry('top.pdf'), nested]);
    const dataTransfer = makeDataTransfer([topLevel]);

    const files = await readAllFilesFromDataTransfer(dataTransfer);
    expect(files.map((f) => f.name).sort()).toEqual(['nested-1.pdf', 'nested-2.pdf', 'top.pdf']);
  });

  it('falls back to the flat file list when webkitGetAsEntry is unsupported', async () => {
    const flatFile = new File(['x'], 'legacy.pdf');
    const dataTransfer = {
      items: [{}], // an item present, but lacking `webkitGetAsEntry` (older browser)
      files: [flatFile],
    } as unknown as DataTransfer;

    const files = await readAllFilesFromDataTransfer(dataTransfer);
    expect(files).toEqual([flatFile]);
  });
});

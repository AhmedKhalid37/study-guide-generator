// Shared folder presentation helpers. Folder color is an optional, non-secret
// hex string stored in library/folders.json. These presets are the swatches
// offered when creating/recoloring a folder; they mirror the backend defaults.

export const FOLDER_PRESET_COLORS = [
  "#F59E0B", // amber
  "#60A5FA", // blue
  "#A855F7", // purple
  "#34D399", // green
  "#F472B6" // pink
];

export const DEFAULT_FOLDER_COLOR = "#9098A8";

export function folderColor(folder) {
  return folder?.color || DEFAULT_FOLDER_COLOR;
}

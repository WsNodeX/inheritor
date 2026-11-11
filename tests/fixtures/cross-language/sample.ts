// TODO: wire this into the build script
export function unguarded(): void {}

// TODO: remove after the migration completes (tracked in #412)
export function guarded(): void {}

/* FIXME: no owner */
export const blocked = 1;

export const asLineComment = "// TODO: this is a string, not a comment";
export const asBlockComment = `/* TODO: this is a template literal */`;
export const asUrl = "https://example.com//not-a-comment";

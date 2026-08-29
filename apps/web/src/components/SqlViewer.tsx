export function SqlViewer({ sql }: { sql: string }) {
  return (
    <pre className="mt-1 overflow-x-auto rounded-md bg-neutral-900 p-3 text-xs text-neutral-100">
      <code className="font-mono">{sql}</code>
    </pre>
  );
}

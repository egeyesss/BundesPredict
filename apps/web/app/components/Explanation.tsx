import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * The agent's explanation, rendered as markdown — models bold the key shifts
 * (`**home win 55% → 47%**`) and occasionally use lists, so plain text showed
 * literal asterisks. remark-gfm covers tables: the prompt discourages them,
 * but a model that emits one anyway should render, not leak raw pipes.
 * Styling is inlined per element (no typography plugin).
 */
export default function Explanation({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-zinc-900 dark:text-zinc-50">
              {children}
            </strong>
          ),
          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li>{children}</li>,
          h1: ({ children }) => <p className="font-semibold">{children}</p>,
          h2: ({ children }) => <p className="font-semibold">{children}</p>,
          h3: ({ children }) => <p className="font-semibold">{children}</p>,
          code: ({ children }) => (
            <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[0.85em] dark:bg-zinc-800">
              {children}
            </code>
          ),
          a: ({ children }) => <span>{children}</span>,
          table: ({ children }) => (
            <table className="my-1 border-collapse text-xs">{children}</table>
          ),
          th: ({ children }) => (
            <th className="border border-zinc-200 px-2 py-1 text-left font-semibold dark:border-zinc-700">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-zinc-200 px-2 py-1 dark:border-zinc-700">
              {children}
            </td>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

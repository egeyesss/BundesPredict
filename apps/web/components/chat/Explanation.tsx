import Markdown from "react-markdown";

const count = (text: string, marker: string) => text.split(marker).length - 1;

function openRuns(text: string) {
  return { bold: count(text, "**") % 2 === 1, italic: count(text.replaceAll("**", ""), "*") % 2 === 1 };
}

/**
 * The typewriter reveals the answer a few characters at a time, so an opened `**` can be on
 * screen before its partner. Closing it here keeps stray asterisks out of the text mid-typing.
 */
export function closeOpenEmphasis(partial: string): string {
  let text = partial;
  let open = openRuns(text);
  if (open.bold && text.endsWith("**")) text = text.slice(0, -2);
  else if (!open.bold && open.italic && text.endsWith("*")) text = text.slice(0, -1);
  open = openRuns(text);
  return `${text}${open.italic ? "*" : ""}${open.bold ? "**" : ""}`;
}

/** The agent's explanation: the model writes light markdown (bold, paragraphs), never raw html. */
export function Explanation({ text }: { text: string }) {
  return (
    <div className="grid max-w-[65ch] gap-3 text-bp-text/90 [&_strong]:font-semibold [&_strong]:text-bp-text [&>p]:m-0 [&_ol]:m-0 [&_ol]:list-decimal [&_ol]:pl-5 [&_ul]:m-0 [&_ul]:list-disc [&_ul]:pl-5">
      <Markdown>{text}</Markdown>
    </div>
  );
}

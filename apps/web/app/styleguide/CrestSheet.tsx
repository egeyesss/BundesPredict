import { ClubCrest } from "@/components/brand/ClubCrest";
import { crestManifest } from "@/lib/brand";

const SIZES = [20, 32, 48, 96] as const;
const WIDE_LOGOS = new Set(["FCU", "RBL", "SCP", "HSV"]);

function note(code: string): string {
  if (crestManifest[code].dark) return "mostly black: renders as-is, flagged dark in the manifest";
  if (WIDE_LOGOS.has(code)) return "wide logo: reads small at 20px, keep the name beside it";
  return "clear at every size";
}

export function CrestSheet() {
  const codes = Object.keys(crestManifest);

  return (
    <div
      role="group"
      aria-label="Crests at every size"
      tabIndex={0}
      className="overflow-x-auto rounded-lg border border-bp-border bg-bp-surface-1"
    >
      <table className="w-full min-w-[640px] border-collapse text-left">
        <thead>
          <tr className="border-b border-bp-border font-mono text-[11px] tracking-wider text-bp-text-muted uppercase">
            <th scope="col" className="p-3 font-medium">Club</th>
            {SIZES.map((size) => (
              <th key={size} scope="col" className="p-3 font-medium">{size}px</th>
            ))}
            <th scope="col" className="p-3 font-medium">Note</th>
          </tr>
        </thead>
        <tbody>
          {codes.map((code) => {
            const team = { name: crestManifest[code].name, code };
            return (
              <tr key={code} data-crest-row className="border-b border-bp-border last:border-b-0">
                <th scope="row" className="p-3 font-display text-base font-semibold whitespace-nowrap">
                  {team.name}
                  <span className="block font-mono text-[11px] font-normal text-bp-text-muted">{code}</span>
                </th>
                {SIZES.map((size) => (
                  <td key={size} className="p-3">
                    <ClubCrest team={team} size={size} />
                  </td>
                ))}
                <td className="p-3 text-xs text-bp-text-muted">{note(code)}</td>
              </tr>
            );
          })}
          <tr className="border-t border-bp-border">
            <th scope="row" className="p-3 font-display text-base font-semibold whitespace-nowrap">
              Missing asset
              <span className="block font-mono text-[11px] font-normal text-bp-text-muted">e.g. a newly promoted club</span>
            </th>
            {SIZES.map((size) => (
              <td key={size} className="p-3">
                <ClubCrest team={{ name: "Newly promoted club", code: "NEW", crest: null }} size={size} />
              </td>
            ))}
            <td className="p-3 text-xs text-bp-text-muted">kit chip with the 3-letter code until the SVG is added</td>
          </tr>
          <tr className="border-t border-bp-border">
            <th scope="row" className="p-3 font-display text-base font-semibold whitespace-nowrap">
              Club colours
              <span className="block font-mono text-[11px] font-normal text-bp-text-muted">Dortmund chip</span>
            </th>
            {SIZES.map((size) => (
              <td key={size} className="p-3">
                <ClubCrest team={{ name: "Dortmund", code: "BVB", crest: null }} size={size} />
              </td>
            ))}
            <td className="p-3 text-xs text-bp-text-muted">chip uses the manifest colours when the code is known</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

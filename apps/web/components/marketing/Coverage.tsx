import { ClubCrest } from "@/components/brand/ClubCrest";
import { LeagueMark } from "@/components/brand/LeagueMark";
import { crestManifest } from "@/lib/brand";

import { Section, SectionHead } from "./Section";

const SHORT_NAMES: Record<string, string> = {
  FCB: "Bayern",
  BVB: "Dortmund",
  B04: "Leverkusen",
  RBL: "Leipzig",
  SGE: "Frankfurt",
  VFB: "Stuttgart",
  SCF: "Freiburg",
  BMG: "Gladbach",
  M05: "Mainz",
  TSG: "Hoffenheim",
  SVW: "Bremen",
  FCA: "Augsburg",
  FCU: "Union Berlin",
  KOE: "Köln",
  HSV: "Hamburg",
  S04: "Schalke",
  SCP: "Paderborn",
  SVE: "Elversberg",
};

export function Coverage() {
  const clubs = Object.entries(crestManifest).map(([code, entry]) => ({ code, name: entry.name, shortName: SHORT_NAMES[code] ?? entry.name }));
  return (
    <Section id="cover" name="Coverage">
      <div className="flex flex-wrap items-center gap-x-[18px] gap-y-3.5">
        <LeagueMark placement="coverage" size={64} />
        <SectionHead id="cover" eyebrow="What we cover" title={`All ${clubs.length} clubs, every matchday`} />
      </div>
      <ul aria-label="Clubs" className="m-0 grid list-none grid-cols-3 gap-x-3 gap-y-[18px] p-0 min-[481px]:grid-cols-6 min-[861px]:grid-cols-9">
        {clubs.map((club) => (
          <li key={club.code} className="grid justify-items-center gap-2">
            <ClubCrest team={{ name: club.name, code: club.code }} size={48} />
            <span aria-hidden="true" className="text-center font-mono text-[11px] text-bp-text-muted">{club.shortName}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

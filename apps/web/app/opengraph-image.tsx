import { ImageResponse } from "next/og";

import { buildPitch, projectPitch } from "@/components/marketing/pitch";
import { DISPLAY_FONT, loadDisplayFont } from "@/lib/brand-image";

export const alt = "BundesPredict: Bundesliga win probabilities, adjusted for the news";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PITCH_CAMERA = { width: 1200 * 1.5, height: 630 * 1.2, elapsedSeconds: 0, drifting: false };

export default async function Image() {
  const font = await loadDisplayFont();
  const glyphs = buildPitch().lines.filter((point) => !point.spot);

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", position: "relative", background: "#0A0A0B", overflow: "hidden" }}>
        {glyphs.map((point, index) => {
          const { x, y, scale } = projectPitch(point, PITCH_CAMERA);
          return (
            <span
              key={index}
              style={{ position: "absolute", left: x - 100, top: y - 40, fontSize: 13 * scale, color: `rgba(34, 197, 94, ${Math.min(0.5, 0.3 * scale)})` }}
            >
              {point.glyph}
            </span>
          );
        })}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            background: "linear-gradient(90deg, #0A0A0B 0%, rgba(10,10,11,0.88) 48%, rgba(10,10,11,0.1) 100%)",
          }}
        />
        <div style={{ position: "absolute", left: 72, top: 150, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontFamily: DISPLAY_FONT.name, fontWeight: 700, fontSize: 170, lineHeight: 1 }}>
            <span style={{ color: "#F4F4F5" }}>Bundes</span>
            <span style={{ color: "#D20515" }}>Predict</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", marginTop: 36, fontSize: 34, lineHeight: 1.3, color: "#D4D4D8" }}>
            <span>Win, draw and loss probabilities for every</span>
            <span>Bundesliga fixture. Bring the news.</span>
          </div>
          <div style={{ display: "flex", marginTop: 56, fontSize: 24, color: "#A1A1AA" }}>bundespredict.egeyesilyurt.ca</div>
        </div>
      </div>
    ),
    { ...size, fonts: [{ name: DISPLAY_FONT.name, data: font, style: DISPLAY_FONT.style, weight: DISPLAY_FONT.weight }] },
  );
}

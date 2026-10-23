import { ImageResponse } from "next/og";

import { DISPLAY_FONT, loadDisplayFont } from "@/lib/brand-image";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default async function AppleIcon() {
  const font = await loadDisplayFont();
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0A0A0B",
          fontFamily: DISPLAY_FONT.name,
          fontWeight: 700,
          fontSize: 118,
          lineHeight: 1,
        }}
      >
        <span style={{ color: "#F4F4F5" }}>B</span>
        <span style={{ color: "#D20515" }}>P</span>
      </div>
    ),
    { ...size, fonts: [{ name: DISPLAY_FONT.name, data: font, style: DISPLAY_FONT.style, weight: DISPLAY_FONT.weight }] },
  );
}

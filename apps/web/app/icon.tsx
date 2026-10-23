import { ImageResponse } from "next/og";

import { DISPLAY_FONT, loadDisplayFont } from "@/lib/brand-image";

export const size = { width: 48, height: 48 };
export const contentType = "image/png";

export default async function Icon() {
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
          borderRadius: 11,
          fontFamily: DISPLAY_FONT.name,
          fontWeight: 700,
          fontSize: 32,
          lineHeight: 1,
        }}
      >
        <span style={{ color: "#F4F4F5" }}>B</span>
        <span style={{ color: "#FF2B3A" }}>P</span>
      </div>
    ),
    { ...size, fonts: [{ name: DISPLAY_FONT.name, data: font, style: DISPLAY_FONT.style, weight: DISPLAY_FONT.weight }] },
  );
}

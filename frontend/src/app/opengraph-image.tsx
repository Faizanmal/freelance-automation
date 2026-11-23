import { ImageResponse } from "next/og";

export const alt = "Signal Desk — freelance opportunity intelligence";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: 76,
          color: "#f7faf9",
          background: "radial-gradient(circle at 82% 16%, #17343b 0%, #101923 40%, #0b1118 100%)",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", width: 650 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, color: "#73dfc3", fontSize: 23, fontWeight: 700, letterSpacing: 4 }}>
            <div style={{ width: 14, height: 14, borderRadius: 7, background: "#73dfc3" }} />
            <div>SIGNAL DESK</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", marginTop: 54, fontSize: 58, lineHeight: 1.08, fontWeight: 700, letterSpacing: -2 }}>
            <div>Find freelance work</div>
            <div style={{ color: "#73dfc3" }}>with less noise.</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", marginTop: 27, fontSize: 25, lineHeight: 1.4, color: "#c5d0d0" }}>
            <div>Public listings, ranked for your rules.</div>
            <div>You pitch on the original post.</div>
          </div>
          <div style={{ marginTop: 42, fontSize: 16, color: "#8fa3a5", letterSpacing: 1 }}>
            NO AUTO-APPLY · NO PAY-TO-RANK
          </div>
        </div>
        <div style={{ width: 340, display: "flex", flexDirection: "column", gap: 16, padding: 25, borderRadius: 22, background: "rgba(255,255,255,0.055)", border: "1px solid rgba(115,223,195,0.24)" }}>
          <div style={{ color: "#8fa3a5", fontSize: 14, letterSpacing: 2, marginBottom: 4 }}>YOUR DISCOVERY DESK</div>
          {["Hunt Rules", "Ranked leads", "Original listing"].map((item, index) => (
            <div key={item} style={{ display: "flex", alignItems: "center", gap: 15, padding: "17px 15px", borderRadius: 12, background: index === 1 ? "rgba(115,223,195,0.12)" : "rgba(255,255,255,0.045)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <div style={{ width: 28, height: 28, borderRadius: 14, display: "flex", alignItems: "center", justifyContent: "center", background: index === 1 ? "#73dfc3" : "#27383e", color: index === 1 ? "#0b1118" : "#c5d0d0", fontSize: 14, fontWeight: 700 }}>{index + 1}</div>
              <div style={{ fontSize: 19, fontWeight: 600 }}>{item}</div>
            </div>
          ))}
          <div style={{ marginTop: 2, color: "#8fa3a5", fontSize: 13 }}>SOURCE DETAILS STAY VISIBLE</div>
        </div>
      </div>
    ),
    { ...size },
  );
}

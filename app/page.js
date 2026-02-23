export default function Home() {
  return (
    <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#1A1A1D", color: "#fff", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Que hacemos</h1>
        <p style={{ color: "#A0A0A0", marginBottom: "1.5rem" }}>Eventos en Lima</p>
        <a href="/index.html" style={{ color: "#8B5CF6", textDecoration: "underline" }}>Ver calendario</a>
        <span style={{ margin: "0 0.5rem", color: "#666" }}>|</span>
        <a href="/blog.html" style={{ color: "#8B5CF6", textDecoration: "underline" }}>Blog</a>
      </div>
    </main>
  );
}

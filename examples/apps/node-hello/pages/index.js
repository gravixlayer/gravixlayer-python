/**
 * Node.js Next.js — Hello World
 *
 * Root page: renders a JSON-style greeting.
 *
 * Run locally:
 *   npm install && npm run build && npm start
 *   Open http://localhost:8080
 */

export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <h1>Hello, World!</h1>
    </main>
  );
}

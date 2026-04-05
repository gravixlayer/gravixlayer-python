/**
 * GET /api/health
 *
 * Health check endpoint for readiness probes.
 * Returns: { "status": "healthy" }
 */

export default function handler(req, res) {
  res.status(200).json({ status: "healthy" });
}

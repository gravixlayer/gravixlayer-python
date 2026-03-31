/**
 * GET /api
 *
 * Root API endpoint returning a greeting.
 * Returns: { "message": "Hello, World!" }
 */

export default function handler(req, res) {
  res.status(200).json({ message: "Hello, World!" });
}

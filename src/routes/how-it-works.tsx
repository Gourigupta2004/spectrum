import { createFileRoute, Navigate } from "@tanstack/react-router";

/** Retired in favour of /about; kept as a redirect so old links keep working. */
export const Route = createFileRoute("/how-it-works")({
  component: () => <Navigate to="/about" replace />,
});

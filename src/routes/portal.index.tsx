import { createFileRoute, Navigate } from "@tanstack/react-router";

export const Route = createFileRoute("/portal/")({
  component: () => <Navigate to="/portal/workspace" replace />,
});

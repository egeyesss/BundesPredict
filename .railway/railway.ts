import { defineRailway, project, service } from "railway/iac";

export const partial = "backend";

export default defineRailway(() => {
  const backend = service("backend", {
    build: { builder: "DOCKERFILE", dockerfilePath: "infra/Dockerfile.backend" },
    preDeploy: "python apps/backend/manage.py migrate --noinput",
    healthcheck: "/api/v1/health",
    deploy: { restartPolicyType: "ON_FAILURE" },
  });

  return project("bundespredict", {
    variables: { managed: false },
    resources: [backend],
  });
});

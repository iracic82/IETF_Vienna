// IETF lab — sandbox provisioning.
//
// Single GCP project per learner (Instruqt provisions automatically when
// google.project is declared). One small GCE VM runs the docker-compose
// stack from ../sandbox/.
//
// SANDBOX_SLUG comes from random_id and is injected into every container.

resource "random_id" "sandbox_slug" {
  byte_length = 4   // 8 hex chars
}

resource "google" "project" {
  apis = [
    "compute.googleapis.com",
    "aiplatform.googleapis.com",    // Vertex AI
  ]
}

// ── Instruqt secrets (configured in the track's Secrets tab) ─────────
// These three are pre-provisioned per the screenshot:
//   DEMO_AWS_ACCESS_KEY_ID
//   DEMO_AWS_SECRET_ACCESS_KEY
//   DEMO_HOSTED_ZONE_ID
//
// They're scoped to the Route 53 zone workshop.highvelocitynetworking.com
// with permissions limited to change-resource-record-sets.

resource "secret" "aws_access_key_id" {
  reference = "DEMO_AWS_ACCESS_KEY_ID"
}

resource "secret" "aws_secret_access_key" {
  reference = "DEMO_AWS_SECRET_ACCESS_KEY"
}

resource "secret" "hosted_zone_id" {
  reference = "DEMO_HOSTED_ZONE_ID"
}

resource "container" "sandbox" {
  image {
    name = "ghcr.io/highvelocitynetworking/ietf-vienna-ietf-runner:latest"
  }

  // Mounts the repo + docker-in-docker. The runner image is responsible
  // for invoking sandbox/bootstrap.sh.
  command = ["/opt/lab/bootstrap.sh"]

  environment = {
    LAB                            = "ietf"
    SANDBOX_SLUG                   = resource.random_id.sandbox_slug.hex
    ZONE                           = "workshop.highvelocitynetworking.com"
    GOOGLE_CLOUD_PROJECT           = resource.google.project.id
    VERTEX_LOCATION                = "us-east5"
    GOOGLE_APPLICATION_CREDENTIALS = "/var/run/secrets/gcp-sa.json"
    AWS_DEFAULT_REGION             = "us-east-1"
    AWS_ACCESS_KEY_ID              = resource.secret.aws_access_key_id.value
    AWS_SECRET_ACCESS_KEY          = resource.secret.aws_secret_access_key.value
    HOSTED_ZONE_ID                 = resource.secret.hosted_zone_id.value
  }

  port {
    local  = 3000   // agentgateway public ingress
    remote = 3000
  }

  port {
    local  = 8080   // DNS-AID Explorer
    remote = 8080
  }

  port {
    local  = 15000  // agentgateway admin UI
    remote = 15000
  }
}

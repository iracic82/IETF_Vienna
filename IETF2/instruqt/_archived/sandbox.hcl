// IETF2 lab — bigger sandbox (14 containers). Same shape as IETF, more memory.

resource "random_id" "sandbox_slug" {
  byte_length = 4
}

resource "google" "project" {
  apis = [
    "compute.googleapis.com",
    "aiplatform.googleapis.com",
  ]
}

// Instruqt secrets (Route53 zone management ONLY).
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
    name = "ghcr.io/highvelocitynetworking/ietf-vienna-ietf2-runner:latest"
  }

  command = ["/opt/lab/bootstrap.sh"]

  resources {
    cpu    = 2000   // 2 vCPU
    memory = 4096   // 4 GB
  }

  environment = {
    LAB                            = "ietf2"
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

  port { local = 3000  remote = 3000 }
  port { local = 8080  remote = 8080 }
  port { local = 15000 remote = 15000 }
}

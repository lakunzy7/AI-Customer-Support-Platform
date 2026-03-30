# AI Platform secrets policy
path "secret/data/ai-platform/*" {
  capabilities = ["read"]
}

path "secret/metadata/ai-platform/*" {
  capabilities = ["list"]
}

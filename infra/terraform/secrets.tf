resource "aws_secretsmanager_secret" "api_keys" {
  name        = "${var.project_name}/${var.environment}/api-keys"
  description = "API keys for ClinGuide (Anthropic, OpenAI, Cohere, Pinecone)"
}

# Populate the secret values via AWS console or CLI after apply:
#   aws secretsmanager put-secret-value \
#     --secret-id clinguide/dev/api-keys \
#     --secret-string '{"CLINGUIDE_ANTHROPIC_API_KEY":"...","CLINGUIDE_OPENAI_API_KEY":"...","CLINGUIDE_COHERE_API_KEY":"...","CLINGUIDE_PINECONE_API_KEY":"..."}'

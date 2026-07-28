#!/bin/bash
# Safe Local Ollama Setup
# This script sets up a local environment for running LLM coding agents for free,
# as discussed in the "Claude Code local" reel.

echo "Setting up local Ollama environment for open source coding models..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null
then
    echo "Ollama is not installed. Please install it from https://ollama.com/download"
    echo "Or run: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

echo "Ollama is installed."

# Model to pull for coding (e.g., qwen2.5-coder or codellama)
MODEL_NAME="qwen2.5-coder:7b"

echo "Pulling $MODEL_NAME..."
ollama pull $MODEL_NAME

echo "Model pulled successfully."
echo "You can now run your local coding agent against this model."
echo "Example: ollama run $MODEL_NAME"

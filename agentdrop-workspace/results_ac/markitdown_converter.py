#!/usr/bin/env python3
"""
MarkItDown Local Converter
This script demonstrates how to safely convert local documents (PDFs, Word, Excel)
into clean Markdown using Microsoft's MarkItDown library.
This reduces token usage when feeding documents to LLMs.
"""
import os
import sys

try:
    from markitdown import MarkItDown
except ImportError:
    print("Please install markitdown: pip install markitdown")
    sys.exit(1)

def convert_to_markdown(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Converting {file_path} to Markdown...")
    md = MarkItDown()
    try:
        result = md.convert(file_path)
        
        base_name = os.path.splitext(file_path)[0]
        output_path = f"{base_name}.md"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.text_content)
            
        print(f"Successfully converted to {output_path}")
    except Exception as e:
        print(f"Error converting file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python markitdown_converter.py <file_to_convert>")
        sys.exit(1)
        
    convert_to_markdown(sys.argv[1])

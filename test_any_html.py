#!/usr/bin/env python3
"""
Test the HTML parser with any HTML file

Usage:
    python test_any_html.py <html_file_path>

Example:
    python test_any_html.py debug_html/debug_1234567890.html
"""

import sys
from html_parser import BhulekhaHTMLParser

if len(sys.argv) < 2:
    print("Usage: python test_any_html.py <html_file_path>")
    print("\nExample: python test_any_html.py debug_html/debug_1234567890.html")
    sys.exit(1)

html_file = sys.argv[1]

try:
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
except FileNotFoundError:
    print(f"❌ Error: File not found: {html_file}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error reading file: {e}")
    sys.exit(1)

print(f"Testing HTML parser with: {html_file}\n")
print("=" * 80)

parser = BhulekhaHTMLParser(html_content)
print("\n" + "=" * 80)
print("\n📍 LOCATION EXTRACTION TEST\n")

location_data = parser._extract_location_info()

print("\nResults:")
print("-" * 80)
for key, value in location_data.items():
    status = "✅" if value and value != "Not found" else "❌"
    print(f"  {status} {key:20s}: {value}")

print("\n" + "=" * 80)
print("\n📊 FULL EXTRACTION TEST\n")

extraction_data, confidence = parser.extract_khatiyan_details()

print(f"\n🎯 Confidence: {confidence}")
print("\nAll Extracted Fields:")
print("-" * 80)
for key, value in extraction_data.items():
    if key != 'plots':  # Skip detailed plots list
        status = "✅" if value and value not in ["Not found", "Extraction failed"] else "❌"
        print(f"  {status} {key:20s}: {str(value)[:60]}")

print("\n" + "=" * 80)

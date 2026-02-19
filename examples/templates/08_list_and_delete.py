#!/usr/bin/env python3
"""
List and delete templates.

Demonstrates how to list all templates in your account, get details
for a specific template, and delete templates by ID.
"""

import os
import sys

from gravixlayer import GravixLayer

client = GravixLayer(
    api_key=os.environ["GRAVIXLAYER_API_KEY"],
    cloud=os.environ.get("GRAVIXLAYER_CLOUD", "azure"),
    region=os.environ.get("GRAVIXLAYER_REGION", "eastus2"),
)

# -- List all templates -----------------------------------------------------

print("--- List Templates ---")
response = client.templates.list()
print(f"Total templates: {len(response.templates)}\n")

for t in response.templates:
    print(f"  {t.id}: {t.name}  ({t.vcpu_count} vCPU, {t.memory_mb}MB RAM)")

# -- Get details for a specific template ------------------------------------

if response.templates:
    template_id = response.templates[0].id
    print(f"\n--- Template Details: {template_id} ---")
    info = client.templates.get(template_id)
    print(f"  Name:        {info.name}")
    print(f"  Description: {info.description}")
    print(f"  vCPU:        {info.vcpu_count}")
    print(f"  Memory:      {info.memory_mb}MB")
    print(f"  Disk:        {info.disk_size_mb}MB")
    print(f"  Visibility:  {info.visibility}")
    print(f"  Created:     {info.created_at}")

# -- Delete a template (uncomment to use) -----------------------------------
#
# template_id = "your-template-id"
# result = client.templates.delete(template_id)
# print(f"Deleted: {result.deleted}  (template_id={result.template_id})")
